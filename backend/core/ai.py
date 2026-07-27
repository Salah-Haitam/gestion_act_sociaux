"""
Partie IA de la plateforme.

Trois briques :
  1. `scorer_beneficiaires`  - priorisation equitable des employes pour un service.
  2. `clusteriser`           - segmentation K-Means du personnel en profils.
  3. `repondre`              - assistant admin en langage naturel.

L'assistant fonctionne d'abord avec un moteur a regles, deterministe et hors
ligne. Quand une clef d'API est configuree, un LLM vient en renfort UNIQUEMENT
pour comprendre les tournures que les regles ratent (voir `core/llm.py`) : il
ne produit jamais de chiffre et ne voit aucune donnee nominative.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

import numpy as np
from django.db.models import Count, Q, Sum

from . import llm
from .models import Activitee, Personnel, Transaction

# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------


def sans_accents(texte: str) -> str:
    """Normalise une chaine : minuscules, sans accents (pour comparer du texte FR)."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte.lower().strip()


def _normaliser(valeurs: list[float]) -> list[float]:
    """Ramene une serie dans [0, 1] (min-max). Serie constante -> 0."""
    if not valeurs:
        return []
    mini, maxi = min(valeurs), max(valeurs)
    if maxi - mini < 1e-9:
        return [0.0 for _ in valeurs]
    return [(v - mini) / (maxi - mini) for v in valeurs]


# Familles de services : le poids des criteres depend de la nature de l'aide.
MOTS_FAMILLE = {
    "famille": ("scolaire", "enfant", "naissance", "colonie", "creche", "rentree"),
    "exceptionnel": ("hajj", "omra", "pelerinage", "mariage", "logement"),
    "urgence": ("deces", "maladie", "hospitalisation", "funeraire", "secours"),
}


def _famille_service(service: str) -> str:
    s = sans_accents(service)
    for famille, mots in MOTS_FAMILLE.items():
        if any(mot in s for mot in mots):
            return famille
    return "standard"


# Ponderations des criteres du score d'equite, par famille de service.
# jamais    : l'employe n'a jamais beneficie de CE service  (coeur du sujet)
# rarete    : il a recu peu d'aides toutes categories confondues
# montant   : il a percu un faible montant cumule
# anciennete: il est dans l'entreprise depuis longtemps
# enfants   : charge familiale
PONDERATIONS = {
    "standard":     {"jamais": 0.40, "rarete": 0.20, "montant": 0.12, "anciennete": 0.16, "enfants": 0.12},
    "famille":      {"jamais": 0.35, "rarete": 0.15, "montant": 0.10, "anciennete": 0.10, "enfants": 0.30},
    "exceptionnel": {"jamais": 0.45, "rarete": 0.15, "montant": 0.10, "anciennete": 0.25, "enfants": 0.05},
    "urgence":      {"jamais": 0.40, "rarete": 0.20, "montant": 0.15, "anciennete": 0.10, "enfants": 0.15},
}


# --------------------------------------------------------------------------
# 1. Recommandation / priorisation
# --------------------------------------------------------------------------


def scorer_beneficiaires(activitee: Activitee, annee: int | None = None, limite: int | None = None):
    """
    Calcule un score d'equite (0-100) pour chaque employe vis-a-vis d'un service.

    Plus le score est eleve, plus l'employe merite d'etre servi en priorite :
    il n'a jamais recu ce service, recoit peu d'aides en general, a de
    l'anciennete et/ou une charge familiale importante.
    """
    annee = annee or date.today().year
    ponderation = PONDERATIONS[_famille_service(activitee.service)]

    employes = list(
        Personnel.objects.annotate(
            nb_aides=Count("transactions", distinct=True),
            total_percu=Sum("transactions__montantTR"),
            deja_ce_service=Count(
                "transactions",
                filter=Q(transactions__id_activitee=activitee),
                distinct=True,
            ),
            deja_ce_service_annee=Count(
                "transactions",
                filter=Q(transactions__id_activitee=activitee, transactions__annee=annee),
                distinct=True,
            ),
        )
    )
    if not employes:
        return []

    anciennetes = _normaliser([float(e.anciennete) for e in employes])
    enfants = _normaliser([float(e.nb_enfants) for e in employes])
    nb_aides = _normaliser([float(e.nb_aides) for e in employes])
    montants = _normaliser([float(e.total_percu or 0) for e in employes])

    # Pour un service en rotation, la reference n'est pas « n'a jamais recu »
    # mais « est au minimum d'attributions » : au deuxieme tour, tout le monde
    # a deja recu une fois, et c'est normal.
    rotation = activitee.regle_attribution == Activitee.ROTATION
    minimum = min(e.deja_ce_service for e in employes) if rotation else 0

    resultats = []
    for i, emp in enumerate(employes):
        jamais_service = emp.deja_ce_service == 0
        deja_cette_annee = emp.deja_ce_service_annee > 0
        au_minimum = emp.deja_ce_service == minimum
        # Critere « prioritaire au titre du service lui-meme ».
        prioritaire = au_minimum if rotation else jamais_service

        score = 100.0 * (
            ponderation["jamais"] * (1.0 if prioritaire else 0.0)
            + ponderation["rarete"] * (1.0 - nb_aides[i])
            + ponderation["montant"] * (1.0 - montants[i])
            + ponderation["anciennete"] * anciennetes[i]
            + ponderation["enfants"] * enfants[i]
        )

        # Un employe non eligible reste dans le classement, mais son score est
        # fortement penalise pour qu'il n'apparaisse jamais en tete.
        if activitee.regle_attribution == Activitee.UNIQUE:
            eligible = jamais_service
        elif rotation:
            eligible = au_minimum
        else:
            eligible = not deja_cette_annee
        if not eligible:
            score *= 0.1

        justifications = []
        if jamais_service:
            justifications.append(f"N'a jamais beneficie de « {activitee.service} »")
        elif rotation and au_minimum:
            justifications.append(
                f"Tour {minimum + 1} : au minimum d'attributions ({minimum}) pour ce service"
            )
        if emp.nb_aides == 0:
            justifications.append("Aucune aide sociale recue a ce jour")
        elif nb_aides[i] <= 0.25:
            justifications.append(f"Peu servi ({emp.nb_aides} aide(s) au total)")
        if anciennetes[i] >= 0.6:
            justifications.append(f"Anciennete elevee ({emp.anciennete} ans)")
        if enfants[i] >= 0.6:
            justifications.append(f"Charge familiale ({emp.nb_enfants} enfants)")
        if not eligible:
            if rotation:
                justifications.append(
                    f"Deja parti {emp.deja_ce_service} fois : doit attendre que tout le "
                    f"personnel ait ete servi autant"
                )
            else:
                justifications.append("Deja servi pour ce service : non eligible")

        resultats.append(
            {
                "matricule": emp.matricule,
                "nom": emp.nom,
                "prenom": emp.prenom,
                "departement": emp.departement,
                "anciennete": emp.anciennete,
                "nb_enfants": emp.nb_enfants,
                "nb_aides_total": emp.nb_aides,
                "total_percu": Decimal(emp.total_percu or 0),
                "jamais_beneficie": jamais_service,
                "eligible": eligible,
                "score": round(score, 2),
                "justifications": justifications,
            }
        )

    resultats.sort(key=lambda r: (-r["score"], r["nom"], r["prenom"]))
    for rang, r in enumerate(resultats, start=1):
        r["rang"] = rang
    return resultats[:limite] if limite else resultats


# --------------------------------------------------------------------------
# 2. Clustering K-Means
# --------------------------------------------------------------------------


def clusteriser(n_clusters: int = 4):
    """
    Segmente le personnel en profils similaires
    (anciennete, nb enfants, nombre d'aides recues, montant cumule)
    pour analyser l'equite de distribution entre groupes.
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    employes = list(
        Personnel.objects.annotate(
            nb_aides=Count("transactions", distinct=True),
            total_percu=Sum("transactions__montantTR"),
        )
    )
    if len(employes) < n_clusters or n_clusters < 2:
        return {
            "erreur": "Pas assez d'employes pour le nombre de groupes demande.",
            "clusters": [],
            "employes": [],
        }

    X = np.array(
        [
            [
                float(e.anciennete),
                float(e.nb_enfants),
                float(e.nb_aides),
                float(e.total_percu or 0),
            ]
            for e in employes
        ],
        dtype=float,
    )
    X_scaled = StandardScaler().fit_transform(X)
    modele = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    labels = modele.fit_predict(X_scaled)

    detail_employes = [
        {
            "matricule": e.matricule,
            "nom": e.nom,
            "prenom": e.prenom,
            "departement": e.departement,
            "anciennete": e.anciennete,
            "nb_enfants": e.nb_enfants,
            "nb_aides": e.nb_aides,
            "total_percu": Decimal(e.total_percu or 0),
            "cluster": int(labels[i]),
        }
        for i, e in enumerate(employes)
    ]

    clusters = []
    for k in range(n_clusters):
        membres = X[labels == k]
        aides_moy = float(membres[:, 2].mean())
        montant_moy = float(membres[:, 3].mean())
        clusters.append(
            {
                "cluster": k,
                "effectif": int(membres.shape[0]),
                "anciennete_moyenne": round(float(membres[:, 0].mean()), 1),
                "enfants_moyen": round(float(membres[:, 1].mean()), 1),
                "aides_moyennes": round(aides_moy, 2),
                "montant_moyen": round(montant_moy, 2),
            }
        )

    # Etiquetage lisible : on compare chaque groupe a la moyenne generale.
    aides_globales = float(X[:, 2].mean())
    for c in clusters:
        if c["aides_moyennes"] <= aides_globales * 0.5:
            c["profil"] = "Sous-servis - a prioriser"
        elif c["aides_moyennes"] >= aides_globales * 1.5:
            c["profil"] = "Bien servis"
        elif c["anciennete_moyenne"] >= float(X[:, 0].mean()):
            c["profil"] = "Anciens, servis normalement"
        else:
            c["profil"] = "Recents, servis normalement"

    clusters.sort(key=lambda c: c["aides_moyennes"])
    return {"clusters": clusters, "employes": detail_employes, "n_clusters": n_clusters}


# --------------------------------------------------------------------------
# 3. Assistant admin en langage naturel (regles + contexte de conversation)
# --------------------------------------------------------------------------
#
# L'assistant fonctionne sans clef d'API ni acces reseau. Il procede en quatre
# temps : normalisation de la question, extraction des entites (service, annee,
# departement, employe) avec repli sur le contexte de la conversation,
# detection de l'intention, puis execution de la requete ORM correspondante.

# Abreviations et raccourcis du langage courant, developpes avant l'analyse.
ABREVIATIONS = {
    "bjr": "bonjour", "bsr": "bonsoir", "slt": "salut", "cc": "salut",
    "mrc": "merci", "thx": "merci", "stp": "", "svp": "", "pls": "",
    "pk": "pourquoi", "pcq": "parce que", "cb": "combien", "bcp": "beaucoup",
    "jms": "jamais", "qqn": "quelqu un", "qq": "quelques", "nb": "nombre",
    "dpt": "departement", "dep": "departement", "srv": "service",
    "mtn": "maintenant", "auj": "aujourd hui", "tt": "tout", "ts": "tous",
    "ki": "qui", "koi": "quoi", "montant": "montant", "stats": "statistiques",
    "moy": "moyenne", "emp": "employe", "empl": "employe", "perso": "personnel",
}

# Mots trop generiques pour identifier un service a eux seuls : « aide » figure
# dans quatre libelles differents.
MOTS_GENERIQUES = {
    "aide", "aides", "prime", "primes", "au", "aux", "de", "des", "du", "la",
    "le", "les", "un", "une", "et", "en", "pour", "exceptionnelle", "service",
}

SALUTATIONS = {"bonjour", "bonsoir", "salut", "hello", "hi", "coucou", "yo"}
REMERCIEMENTS = {"merci", "thanks", "nickel", "parfait", "super", "genial", "ok"}
CONGES = {"au revoir", "bonne journee", "a bientot", "bye", "ciao", "adieu"}

MARQUEURS_NEGATION = (
    "n a pas", "na pas", "n ont pas", "nont pas", "pas beneficie", "pas encore",
    "jamais", "non servi", "non servis", "oublie", "oublies", "sans aide",
    "rien recu", "rien eu", "aucune aide", "exclus", "laisses de cote",
    "pas recu", "pas eu", "pas touche", "prive", "manque",
)

# Formulations qui portent sur TOUTES les aides, pas sur un service precis :
# elles interdisent de reprendre le service du contexte de la conversation.
MARQUEURS_GLOBAUX = (
    "rien recu", "rien eu", "rien touche", "rien du tout", "jamais rien",
    "aucune aide", "aucun service", "aucune action", "aucune prestation",
)

# Formulations qui demandent explicitement la liste des beneficiaires.
MARQUEURS_BENEFICIAIRES = (
    "qui a", "qui ont", "qui en a", "qui sont", "beneficiaire", "beneficie",
    "liste", "qui a recu", "qui a eu", "qui a touche",
)


# Criteres que l'admin peut demander mais qui n'existent PAS dans la table
# personnel : mieux vaut le dire que de repondre a cote.
CRITERES_ABSENTS = {
    "la situation familiale": ("marie", "maries", "celibataire", "celibataires", "divorce"),
    "le salaire": ("salaire", "salaires", "remuneration", "grade", "echelon"),
    "l'age": ("age", "ages", "jeune", "jeunes", "vieux", "senior", "seniors"),
}

# Le sexe, lui, EST enregistre : on le filtre au lieu de le signaler absent.
MARQUEURS_SEXE = {
    "H": ("homme", "hommes", "masculin", "masculins", "messieurs", "employes masculins"),
    "F": ("femme", "femmes", "feminin", "feminines", "dames", "employees"),
}


def _mad(valeur) -> str:
    """Formate un montant en dirhams : 457 575.75 MAD (espace comme separateur)."""
    return f"{Decimal(valeur or 0):,.2f}".replace(",", " ") + " MAD"


def _mot_proche(q: str, *racines, seuil: float = 0.8) -> bool:
    """
    Vrai si un mot de la question ressemble a l'une des racines.

    Complete la recherche par sous-chaine pour tolerer les fautes de frappe :
    « benificier » est reconnu comme « beneficie ».
    """
    for mot in q.split():
        if len(mot) < 4:
            continue
        for racine in racines:
            if racine in mot or mot in racine:
                return True
            if SequenceMatcher(None, racine, mot).ratio() >= seuil:
                return True
    return False


def _criteres_indisponibles(q: str) -> list[str]:
    """Criteres evoques par la question mais absents du modele de donnees."""
    mots = set(q.split())
    absents = [nom for nom, marqueurs in CRITERES_ABSENTS.items() if mots & set(marqueurs)]
    # « 40 ans » designe l'age (absent), sauf quand il qualifie l'anciennete,
    # qui est elle calculable a partir de la date de recrutement.
    if "ans" in mots and "anciennete" not in q and "l'age" not in absents:
        absents.append("l'age")
    return absents


def _preparer(question: str) -> str:
    """Minuscules, sans accents, sans ponctuation, abreviations developpees."""
    q = sans_accents(question)
    q = re.sub(r"[^a-z0-9]+", " ", q)
    mots = [ABREVIATIONS.get(m, m) for m in q.split()]
    return " ".join(m for m in mots if m).strip()


def _mots_significatifs(libelle: str) -> list[str]:
    """Mots d'un libelle de service qui permettent reellement de le distinguer."""
    nettoye = re.sub(r"[^a-z0-9]+", " ", sans_accents(libelle))
    return [m for m in nettoye.split() if len(m) > 3 and m not in MOTS_GENERIQUES]


def _trouver_service(q: str):
    """
    Repere le service evoque, en tolerant les fautes de frappe.

    Renvoie (service, ambigus) : `ambigus` liste les services a egalite quand
    la question ne permet pas de trancher (ex. « aide » seul).
    """
    mots_q = [m for m in q.split() if len(m) > 3]
    scores = []
    for activitee in Activitee.objects.all():
        libelle = re.sub(r"[^a-z0-9]+", " ", sans_accents(activitee.service)).strip()
        if libelle and libelle in q:
            scores.append((activitee, 10.0))
            continue
        significatifs = _mots_significatifs(activitee.service)
        if not significatifs:
            continue
        touches = 0.0
        for mot in significatifs:
            if mot in mots_q:
                touches += 1.0
            # Mot colle a un autre : « dehajj », « duhajj », « lemariage ».
            elif any(len(mq) > len(mot) and mot in mq for mq in mots_q):
                touches += 0.9
            elif any(SequenceMatcher(None, mot, mq).ratio() >= 0.82 for mq in mots_q):
                touches += 0.85  # tolerance aux fautes : « scolair », « pelerinag »
        # Un seul mot vraiment discriminant suffit (« hajj », « logement ») :
        # les mots generiques ont deja ete ecartes de `significatifs`.
        ratio = touches / len(significatifs)
        if touches >= 0.85:
            scores.append((activitee, ratio))

    if not scores:
        return None, []
    scores.sort(key=lambda couple: -couple[1])
    meilleur, note = scores[0]
    exaequo = [a for a, n in scores if abs(n - note) < 0.01]
    return (meilleur, []) if len(exaequo) == 1 else (None, exaequo)


def _trouver_annee(q: str):
    """
    Repere l'annee citee. Renvoie (annee, corrigee).

    Une saisie malformee (« 20025 ») n'est acceptee que si la suppression d'un
    chiffre mene a UNE SEULE annee reellement presente en base. En cas
    d'ambiguite on prefere ne rien deviner.
    """
    exactes = re.findall(r"\b(19\d{2}|20\d{2})\b", q)
    if exactes:
        return int(exactes[0]), False

    malformes = re.findall(r"\b\d{5,6}\b", q)
    if not malformes:
        return None, False
    connues = set(
        Transaction.objects.order_by().values_list("annee", flat=True).distinct()
    )
    for brut in malformes:
        candidats = {int(brut[:i] + brut[i + 1:]) for i in range(len(brut))}
        possibles = sorted(candidats & connues)
        if len(possibles) == 1:
            return possibles[0], True
    return None, False


def _trouver_sexe(q: str):
    """Repere « les hommes » / « les femmes » dans la question."""
    mots = set(q.split())
    for code, marqueurs in MARQUEURS_SEXE.items():
        if mots & set(marqueurs):
            return code
    return None


def _trouver_departement(q: str):
    for departement in Personnel.objects.order_by().values_list("departement", flat=True).distinct():
        nettoye = re.sub(r"[^a-z0-9]+", " ", sans_accents(departement)).strip()
        significatifs = [m for m in nettoye.split() if len(m) > 4]
        if nettoye in q or (significatifs and all(m in q for m in significatifs)):
            return departement
    return None


def _trouver_employe(q: str):
    """
    Retrouve un employe cite par son matricule ou par son nom.

    Renvoie (employe, homonymes) : `homonymes` est renseigne quand plusieurs
    employes portent le nom cite et que le prenom ne permet pas de trancher.
    """
    matricules = re.findall(r"\b(mm\s?\d{2,6})\b", q)
    if matricules:
        employe = Personnel.objects.filter(
            matricule__iexact=matricules[0].replace(" ", "").upper()
        ).first()
        if employe:
            return employe, []

    mots = set(q.split())
    candidats = []
    for employe in Personnel.objects.all():
        nom = sans_accents(employe.nom).replace(" ", "")
        prenom = sans_accents(employe.prenom)
        if nom in mots or (len(nom) > 4 and nom in q.replace(" ", "")):
            candidats.append((employe, prenom in mots))

    if not candidats:
        return None, []
    exacts = [e for e, prenom_cite in candidats if prenom_cite]
    if exacts:
        return exacts[0], []
    if len(candidats) == 1:
        return candidats[0][0], []
    return None, [e for e, _ in candidats]


def _contient(q: str, *motifs) -> bool:
    return any(motif in q for motif in motifs)


def _reponse(type_, texte, colonnes=None, donnees=None, contexte=None, moteur="regles"):
    return {
        "type": type_,
        "reponse": texte,
        "colonnes": colonnes or [],
        "donnees": donnees or [],
        "contexte": contexte or {},
        # Indique si la comprehension a ete assuree par les regles seules ou
        # avec le renfort du LLM. Affiche dans l'interface, utile en demo.
        "moteur": moteur,
    }


def _exemples() -> str:
    services = ", ".join(Activitee.objects.values_list("service", flat=True)[:8])
    return (
        "Voici ce que je sais faire :\n"
        "  • Qui n'a pas beneficie de l'aide scolaire en 2024 ?\n"
        "  • Qui n'a jamais rien recu a la maintenance ?\n"
        "  • Qui a beneficie du Hajj ?\n"
        "  • Combien a coute l'aide au mariage en 2025 ?\n"
        "  • Quel service est le moins distribue ?\n"
        "  • Quel est le taux de couverture du Hajj ?\n"
        "  • Qui devrait etre prioritaire pour l'aide au mariage ?\n"
        "  • Qu'a recu Alaoui ? (ou un matricule : MM0012)\n"
        "  • Quel est l'etat du budget ?\n"
        f"Services disponibles : {services}."
    )


def _detecter_intention(q: str, service_cite: bool, negation: bool) -> str | None:
    """Traduit la question en une intention nommee, ou None si rien n'est reconnu."""
    if negation:
        return "non_beneficiaires" if service_cite else "jamais_rien"
    if _contient(q, "priorit", "recommand", "suggere", "suggestion", "qui devrait",
                 "proposer", "propose", "conseil", "a servir", "prochain"):
        return "priorisation"
    if _contient(q, "quels services", "liste des services", "quelles activites",
                 "services disponibles", "types d aide", "quelles aides"):
        return "services"
    if _contient(q, "quel service", "quelle activite", "le plus", "le moins",
                 "classement", "top des", "plus cher", "moins cher",
                 "plus distribue", "moins distribue", "plus coute"):
        return "classement"
    if _contient(q, "couverture", "taux", "proportion", "pourcentage", "part des"):
        return "couverture"
    if _contient(q, "combien d employe", "combien de personne", "effectif",
                 "nombre d employe", "taille du personnel"):
        return "effectif"
    if _contient(q, "budget", "enveloppe", "reste t il", "restant", "depassement", "alloue"):
        return "budget"
    if _contient(q, "montant", "combien", "cout", "coute", "depense", "total",
                 "somme", "verse", "distribue", "paye"):
        return "montant"
    if _contient(q, *MARQUEURS_BENEFICIAIRES) or _mot_proche(q, "beneficiaire", "beneficie"):
        return "beneficiaires"
    return None


def repondre(question: str, contexte: dict | None = None, utiliser_llm: bool = True) -> dict:
    """
    Analyse une question en francais et renvoie une reponse structuree.

    `contexte` porte le fil de la conversation ({service_id, annee, departement,
    intention}). Il permet deux choses :
      - completer une question incomplete (« et pour la maintenance ? ») ;
      - rejouer la derniere intention quand la question ne fait qu'apporter une
        nouvelle entite (« et en 2023 ? »).
    L'API reste sans etat : c'est le client qui reposte le contexte.
    """
    contexte = contexte or {}
    q = _preparer(question)
    if not q:
        return _reponse("aide", _exemples(), contexte=contexte)

    mots = q.split()
    courte = len(mots) <= 4

    # --- 1. Politesse et meta-questions ----------------------------------
    if mots[0] in SALUTATIONS or (courte and set(mots) & SALUTATIONS):
        return _reponse(
            "message",
            "Bonjour. Je suis l'assistant de gestion des actions sociales.\n" + _exemples(),
            contexte=contexte,
        )
    if courte and set(mots) & REMERCIEMENTS and not _contient(q, "budget", "combien"):
        return _reponse("message", "Avec plaisir. Une autre question ?", contexte=contexte)
    if _contient(q, *CONGES):
        return _reponse("message", "Bonne journee.", contexte=contexte)
    if _contient(q, "que peux tu", "que sais tu", "qui es tu", "comment ca marche",
                 "aide moi", "m aider", "help", "exemples", "que faire"):
        return _reponse("aide", _exemples(), contexte=contexte)

    # --- 2. Extraction des entites ---------------------------------------
    service, ambigus = _trouver_service(q)
    if ambigus:
        return _reponse(
            "message",
            "De quel service parlez-vous ? Plusieurs correspondent : "
            + ", ".join(a.service for a in ambigus)
            + ".",
            contexte=contexte,
        )

    employe, homonymes = _trouver_employe(q)
    if homonymes:
        return _reponse(
            "message",
            "Plusieurs employes portent ce nom : "
            + ", ".join(f"{e.nom} {e.prenom} ({e.matricule})" for e in homonymes)
            + ". Precisez le prenom ou le matricule.",
            contexte=contexte,
        )

    service_cite = service is not None
    annee, annee_corrigee = _trouver_annee(q)
    annee_citee = annee is not None
    departement = _trouver_departement(q)
    departement_cite = departement is not None
    sexe = _trouver_sexe(q)
    negation = _contient(q, *MARQUEURS_NEGATION)
    # Une question portant sur TOUTES les aides ne doit pas heriter du service
    # dont on parlait juste avant.
    portee_globale = _contient(q, *MARQUEURS_GLOBAUX)

    # --- 3. Intention, avec repli sur celle du tour precedent -------------
    intention = _detecter_intention(q, service_cite, negation)
    intention_certaine = intention is not None  # issue d'un mot-clef explicite
    # « et en 2023 ? », « et a la maintenance ? » : la question n'apporte qu'une
    # entite nouvelle, on rejoue donc la derniere intention connue.
    elliptique = intention is None and (annee_citee or departement_cite or service_cite)
    if elliptique and contexte.get("intention"):
        intention = contexte["intention"]
        intention_certaine = True
    if intention is None and service_cite:
        intention = "beneficiaires"  # deduction faible : le LLM peut la corriger

    # --- 3 bis. Renfort LLM ----------------------------------------------
    # Les regles restent maitresses des entites (elles font une correspondance
    # exacte avec la base). Le LLM n'intervient que la ou elles sont muettes ou
    # peu sures : c'est lui qui comprend « ceux qui meritent le hajj » ou
    # « combien on a claque ». Sans clef, cette section est simplement ignoree.
    moteur = "regles"
    if utiliser_llm and llm.disponible():
        plan = llm.analyser(question, contexte)
        if plan:
            apports = []
            if plan["intention"] and not intention_certaine and plan["confiance"] >= 0.5:
                if plan["intention"] != intention:
                    apports.append("intention")
                intention = plan["intention"]
            if service is None and plan["service"] is not None:
                service = plan["service"]
                service_cite = True
                apports.append("service")
            if annee is None and plan["annee"] is not None:
                annee = plan["annee"]
                annee_citee = True
                apports.append("annee")
            if departement is None and plan["departement"]:
                departement = plan["departement"]
                apports.append("departement")
            if sexe is None and plan["sexe"]:
                sexe = plan["sexe"]
                apports.append("sexe")
            if employe is None and plan["employe"]:
                trouve, _ = _trouver_employe(_preparer(plan["employe"]))
                if trouve:
                    employe = trouve
                    apports.append("employe")
            if apports:
                moteur = "llm"

    def _rep(type_, texte, colonnes=None, donnees=None, contexte=None):
        """Reponse portant l'origine de la comprehension (regles ou llm)."""
        return _reponse(type_, texte, colonnes, donnees, contexte, moteur)

    # --- 4. Completion par le contexte -----------------------------------
    suppose = []  # ce qui a ete repris du contexte, annonce dans la reponse
    if service is None and contexte.get("service_id") and not portee_globale:
        service = Activitee.objects.filter(pk=contexte["service_id"]).first()
        if service:
            suppose.append(f"service « {service.service} »")
    if annee is None and contexte.get("annee") and (courte or elliptique):
        annee = contexte["annee"]
        suppose.append(f"annee {annee}")
    if departement is None and contexte.get("departement") and (courte or elliptique):
        departement = contexte["departement"]
        suppose.append(f"departement {departement}")
    if sexe is None and contexte.get("sexe") and (courte or elliptique):
        sexe = contexte["sexe"]
        suppose.append("hommes" if sexe == "H" else "femmes")

    # Sans service, ces intentions se rabattent sur leur variante globale.
    if intention == "non_beneficiaires" and service is None:
        intention = "jamais_rien"
    if intention == "jamais_rien" and service is not None and not portee_globale:
        intention = "non_beneficiaires"

    nouveau_contexte = {
        "service_id": service.id_activitee if service else None,
        "service": service.service if service else None,
        "annee": annee,
        "departement": departement,
        "sexe": sexe,
        "intention": intention,
    }
    # Avertissements places en tete de reponse : ils disent ce que l'assistant
    # n'a PAS pu prendre en compte, pour qu'un resultat ne soit jamais lu comme
    # la reponse a une question qu'il n'a pas traitee.
    avertissements = []
    if annee_corrigee:
        avertissements.append(f"J'ai interprete l'annee saisie comme {annee}.")
    absents = _criteres_indisponibles(q)
    if absents:
        avertissements.append(
            "Le fichier du personnel ne contient pas "
            + " ni ".join(absents)
            + " : ce critere n'a pas pu etre applique. Les champs disponibles sont "
            "le matricule, le nom, le sexe, le departement, la date de recrutement "
            "et le nombre d'enfants."
        )
    entete = ("⚠ " + "\n⚠ ".join(avertissements) + "\n") if avertissements else ""

    prefixe = entete + (f"({', '.join(suppose)}) " if suppose else "")
    hors_service = [s for s in suppose if not s.startswith("service")]
    prefixe_hors_service = entete + (f"({', '.join(hors_service)}) " if hors_service else "")
    suffixe_annee = f" en {annee}" if annee else ""
    suffixe_dep = f" au departement {departement}" if departement else ""
    suffixe_sexe = (" (hommes)" if sexe == "H" else " (femmes)") if sexe else ""
    effectif = Personnel.objects.count()

    def _employes_filtres(base):
        """Applique les filtres transverses (departement, sexe) sur du personnel."""
        if departement:
            base = base.filter(departement__iexact=departement)
        if sexe:
            base = base.filter(sexe=sexe)
        return base

    def _transactions_filtrees(base):
        """Memes filtres, mais sur des transactions (via l'employe)."""
        if departement:
            base = base.filter(matricule__departement__iexact=departement)
        if sexe:
            base = base.filter(matricule__sexe=sexe)
        return base

    # --- 5. Historique d'un employe (prioritaire sur tout le reste) -------
    if employe:
        lignes = employe.transactions.select_related("id_activitee").order_by("-annee")
        if annee_citee:
            lignes = lignes.filter(annee=annee)
        nouveau_contexte["intention"] = "employe"
        if not lignes.exists():
            return _rep(
                "liste",
                f"{employe.nom} {employe.prenom} ({employe.matricule}) n'a beneficie "
                f"d'aucune action sociale{suffixe_annee}. C'est un profil prioritaire.",
                contexte=nouveau_contexte,
            )
        total = sum((t.montantTR for t in lignes), Decimal("0"))
        return _rep(
            "liste",
            f"{employe.nom} {employe.prenom} ({employe.matricule}, {employe.departement}) "
            f"a beneficie de {lignes.count()} action(s) sociale(s){suffixe_annee}, "
            f"pour un total de {_mad(total)}.",
            ["service", "annee", "montantTR", "date_transaction"],
            [
                {
                    "service": t.id_activitee.service,
                    "annee": t.annee,
                    "montantTR": t.montantTR,
                    "date_transaction": t.date_transaction,
                }
                for t in lignes
            ],
            nouveau_contexte,
        )

    # --- 6. Non-beneficiaires d'un service (le coeur du sujet) -----------
    if intention == "non_beneficiaires":
        deja = Transaction.objects.filter(id_activitee=service)
        if annee:
            deja = deja.filter(annee=annee)
        oublies = _employes_filtres(
            Personnel.objects.exclude(matricule__in=deja.values("matricule"))
        )
        return _rep(
            "liste",
            f"{prefixe}{oublies.count()} employe(s) n'ont pas beneficie du service "
            f"« {service.service} »{suffixe_annee}{suffixe_dep}{suffixe_sexe}.",
            ["matricule", "nom", "prenom", "sexe", "departement", "nb_enfants"],
            list(oublies.values("matricule", "nom", "prenom", "sexe", "departement", "nb_enfants")[:200]),
            nouveau_contexte,
        )

    # --- 7. Employes n'ayant jamais rien recu ----------------------------
    if intention == "jamais_rien":
        oublies = _employes_filtres(Personnel.objects.filter(transactions__isnull=True))
        return _rep(
            "liste",
            f"{prefixe_hors_service}{oublies.count()} employe(s) n'ont jamais beneficie "
            f"d'aucune action sociale{suffixe_dep}{suffixe_sexe}.",
            ["matricule", "nom", "prenom", "sexe", "departement", "nb_enfants"],
            list(oublies.values("matricule", "nom", "prenom", "sexe", "departement", "nb_enfants")[:200]),
            nouveau_contexte,
        )

    # --- 8. Priorisation --------------------------------------------------
    if intention == "priorisation":
        if not service:
            return _rep(
                "message",
                "Pour quel service dois-je etablir la priorisation ? "
                + ", ".join(Activitee.objects.values_list("service", flat=True)),
                contexte=nouveau_contexte,
            )
        classement = scorer_beneficiaires(service, annee=annee, limite=None)
        if departement:
            classement = [r for r in classement if r["departement"] == departement]
        if sexe:
            eligibles_sexe = set(
                Personnel.objects.filter(sexe=sexe).values_list("matricule", flat=True)
            )
            classement = [r for r in classement if r["matricule"] in eligibles_sexe]
        classement = [r for r in classement if r["eligible"]][:15]
        return _rep(
            "liste",
            f"{prefixe}Top {len(classement)} des employes prioritaires pour "
            f"« {service.service} »{suffixe_dep}{suffixe_sexe}, par score d'equite.",
            ["rang", "matricule", "nom", "prenom", "departement", "score"],
            [
                {c: ligne[c] for c in ("rang", "matricule", "nom", "prenom", "departement", "score")}
                for ligne in classement
            ],
            nouveau_contexte,
        )

    # --- 9. Classement des services ---------------------------------------
    if intention == "classement":
        base = Transaction.objects.all()
        if annee:
            base = base.filter(annee=annee)
        lignes = []
        for activitee in Activitee.objects.all():
            sous_ensemble = base.filter(id_activitee=activitee)
            beneficiaires = sous_ensemble.values("matricule").distinct().count()
            lignes.append(
                {
                    "service": activitee.service,
                    "montant_total": sous_ensemble.aggregate(s=Sum("montantTR"))["s"] or Decimal("0"),
                    "beneficiaires": beneficiaires,
                    "taux_couverture": round(beneficiaires / effectif * 100, 1) if effectif else 0,
                }
            )
        croissant = _contient(q, "le moins", "moins cher", "moins distribue", "plus faible")
        lignes.sort(key=lambda l: l["montant_total"], reverse=not croissant)
        extreme = lignes[0]
        sens = "le moins dote" if croissant else "le plus dote"
        return _rep(
            "liste",
            f"{prefixe_hors_service}Le service {sens}{suffixe_annee} est "
            f"« {extreme['service']} » ({_mad(extreme['montant_total'])}, "
            f"{extreme['beneficiaires']} beneficiaires).",
            ["service", "montant_total", "beneficiaires", "taux_couverture"],
            lignes,
            nouveau_contexte,
        )

    # --- 10. Taux de couverture -------------------------------------------
    if intention == "couverture":
        lignes = []
        for activitee in [service] if service else Activitee.objects.all():
            base = Transaction.objects.filter(id_activitee=activitee)
            if annee:
                base = base.filter(annee=annee)
            servis = base.values("matricule").distinct().count()
            lignes.append(
                {
                    "service": activitee.service,
                    "beneficiaires": servis,
                    "non_beneficiaires": effectif - servis,
                    "taux_couverture": round(servis / effectif * 100, 1) if effectif else 0,
                }
            )
        lignes.sort(key=lambda l: l["taux_couverture"])
        texte = (
            f"{prefixe}Taux de couverture de « {lignes[0]['service']} »{suffixe_annee} : "
            f"{lignes[0]['taux_couverture']} % ({lignes[0]['beneficiaires']} employes sur {effectif})."
            if service
            else f"{prefixe_hors_service}Taux de couverture par service{suffixe_annee}, "
            "du plus faible au plus eleve."
        )
        return _rep(
            "liste",
            texte,
            ["service", "beneficiaires", "non_beneficiaires", "taux_couverture"],
            lignes,
            nouveau_contexte,
        )

    # --- 11. Effectif ------------------------------------------------------
    if intention == "effectif":
        return _rep(
            "valeur",
            f"{prefixe_hors_service}L'effectif enregistre est de "
            f"{_employes_filtres(Personnel.objects.all()).count()} "
            f"employe(s){suffixe_dep}{suffixe_sexe}.",
            contexte=nouveau_contexte,
        )

    # --- 12. Budget --------------------------------------------------------
    if intention == "budget":
        lignes = []
        for activitee in [service] if service else Activitee.objects.all():
            base = activitee.transactions.all()
            if annee:
                base = base.filter(annee=annee)
            consomme = base.aggregate(s=Sum("montantTR"))["s"] or Decimal("0")
            alloue = activitee.budget_alloue or Decimal("0")
            lignes.append(
                {
                    "service": activitee.service,
                    "budget_alloue": alloue,
                    "consomme": consomme,
                    "restant": alloue - consomme,
                    "taux": round(float(consomme / alloue) * 100, 1) if alloue > 0 else None,
                }
            )
        depasses = [l for l in lignes if l["taux"] is not None and l["taux"] >= 100]
        alerte = (
            f" Attention : {len(depasses)} service(s) en depassement ("
            + ", ".join(l["service"] for l in depasses)
            + ")."
            if depasses
            else ""
        )
        return _rep(
            "liste",
            f"{prefixe}Suivi budgetaire{suffixe_annee}.{alerte}",
            ["service", "budget_alloue", "consomme", "restant", "taux"],
            lignes,
            nouveau_contexte,
        )

    # --- 13. Montants ------------------------------------------------------
    if intention == "montant":
        base = _transactions_filtrees(Transaction.objects.all())
        if service:
            base = base.filter(id_activitee=service)
        if annee:
            base = base.filter(annee=annee)
        total = base.aggregate(s=Sum("montantTR"))["s"] or Decimal("0")
        libelle = f"« {service.service} »" if service else "tous services confondus"
        return _rep(
            "valeur",
            f"{prefixe}Montant total distribue pour {libelle}"
            f"{suffixe_annee}{suffixe_dep}{suffixe_sexe} : "
            f"{_mad(total)} ({base.count()} transactions).",
            contexte=nouveau_contexte,
        )

    # --- 14. Catalogue des services ---------------------------------------
    if intention == "services":
        lignes = [
            {
                "service": a.service,
                "montantSC": a.montantSC,
                "budget_alloue": a.budget_alloue,
                "regle": a.get_regle_attribution_display(),
            }
            for a in Activitee.objects.all()
        ]
        return _rep(
            "liste",
            f"{len(lignes)} actions sociales sont proposees.",
            ["service", "montantSC", "budget_alloue", "regle"],
            lignes,
            nouveau_contexte,
        )

    # --- 15. Beneficiaires d'un service -----------------------------------
    if intention == "beneficiaires" and service:
        base = _transactions_filtrees(
            Transaction.objects.filter(id_activitee=service).select_related("matricule")
        )
        if annee:
            base = base.filter(annee=annee)
        return _rep(
            "liste",
            f"{prefixe}{base.values('matricule').distinct().count()} beneficiaire(s) du service "
            f"« {service.service} »{suffixe_annee}{suffixe_dep}{suffixe_sexe}, "
            f"pour {base.count()} versement(s).",
            ["matricule", "nom", "prenom", "sexe", "departement", "montantTR", "annee"],
            [
                {
                    "matricule": t.matricule_id,
                    "nom": t.matricule.nom,
                    "prenom": t.matricule.prenom,
                    "sexe": t.matricule.sexe_libelle,
                    "departement": t.matricule.departement,
                    "montantTR": t.montantTR,
                    "annee": t.annee,
                }
                for t in base[:200]
            ],
            nouveau_contexte,
        )

    # --- 16. Repli : on rappelle le sujet en cours et on propose la suite --
    if contexte.get("service"):
        return _rep(
            "aide",
            entete
            + f"Je n'ai pas compris. Nous parlions de « {contexte['service']} »"
            + (f" pour {contexte['annee']}" if contexte.get("annee") else "")
            + ". Vous pouvez demander : qui n'en a pas beneficie, qui en a beneficie, "
            "le montant total, le taux de couverture, ou les employes prioritaires.",
            contexte=contexte,
        )
    return _rep("aide", entete + "Je n'ai pas compris.\n" + _exemples(), contexte=nouveau_contexte)
