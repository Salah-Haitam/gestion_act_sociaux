"""
Renfort LLM de l'assistant (optionnel).

Principe de conception, a retenir pour la soutenance :

  Le LLM ne repond JAMAIS a la question. Il traduit seulement la phrase de
  l'administrateur en un « plan de requete » structure (intention + entites).
  C'est ensuite le code Django qui execute la requete SQL et met en forme le
  resultat. Trois consequences :

  1. Aucun chiffre ne peut etre invente : les montants et les effectifs
     viennent tous de l'ORM.
  2. Aucune donnee nominative ne sort du serveur : on n'envoie que la question
     de l'admin et la liste des libelles de services et de departements.
  3. Sans clef d'API, ou en cas de panne reseau, l'assistant retombe sur son
     moteur a regles sans perte de fonctionnalite.

Tout ce que le modele renvoie est revalide contre la base avant d'etre utilise
(voir `_valider`) : un service invente est ignore, pas propage.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date

from django.conf import settings

from .models import Activitee, Personnel

journal = logging.getLogger(__name__)

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

INTENTIONS_VALIDES = {
    "non_beneficiaires", "jamais_rien", "beneficiaires", "priorisation",
    "montant", "budget", "couverture", "classement", "effectif", "services",
    "employe", "salutation", "aide", "inconnu",
}

GABARIT_SYSTEME = """Tu es un analyseur de requetes pour une plateforme RH de gestion des \
actions sociales (Marsa Maroc). Tu traduis la question d'un administrateur en plan de requete JSON.

REGLES ABSOLUES :
- Tu ne reponds jamais a la question et tu n'inventes aucun chiffre.
- Tu n'inventes jamais un service, un departement ou une annee qui n'est pas cite.
- Si la question est vague ou hors sujet, renvoie "inconnu" avec une confiance basse.

Services disponibles (valeurs exactes) : {services}
Departements (valeurs exactes) : {departements}
Annees presentes en base : {annees}
Annee courante : {annee_courante}

Champs du personnel : matricule, nom, prenom, sexe, departement, date_recrutement, nb_enfants.

Intentions possibles :
- "non_beneficiaires" : qui n'a PAS beneficie d'un service precis (les oublies)
- "jamais_rien" : qui n'a jamais rien recu, tous services confondus
- "beneficiaires" : qui a beneficie d'un service
- "priorisation" : qui devrait etre servi en priorite (merite, prochain, recommande)
- "montant" : combien a ete verse / depense
- "budget" : etat des enveloppes, reste a consommer
- "couverture" : taux ou pourcentage d'employes servis
- "classement" : quel service est le plus / le moins dote
- "effectif" : combien d'employes
- "services" : quels services existent
- "employe" : historique d'une personne precise
- "salutation" : bonjour, merci, au revoir
- "aide" : que sais-tu faire
- "inconnu" : sinon

Le contexte de la conversation precedente est fourni : utilise-le pour resoudre les \
questions elliptiques ("et en 2023 ?", "et pour les femmes ?"). Si la question ne \
mentionne pas une entite, laisse-la a null : le serveur completera lui-meme depuis le contexte.

Reponds UNIQUEMENT par un objet JSON :
{{"intention": "...", "service": null, "annee": null, "departement": null, \
"sexe": null, "employe": null, "confiance": 0.0}}
- "service" et "departement" : la valeur EXACTE de la liste, sinon null
- "annee" : entier a 4 chiffres, sinon null
- "sexe" : "H", "F" ou null
- "employe" : matricule ou nom de famille cite, sinon null
- "confiance" : 0.0 a 1.0"""


def disponible() -> bool:
    return bool(getattr(settings, "LLM_ACTIF", False))


def _appeler_groq(question: str, contexte: dict) -> dict | None:
    """Appel HTTP a Groq. Renvoie le JSON brut du modele, ou None en cas d'echec."""
    services = list(Activitee.objects.values_list("service", flat=True))
    departements = sorted(
        Personnel.objects.order_by().values_list("departement", flat=True).distinct()
    )
    annees = _annees_connues()

    systeme = GABARIT_SYSTEME.format(
        services=json.dumps(services, ensure_ascii=False),
        departements=json.dumps(departements, ensure_ascii=False),
        annees=annees,
        annee_courante=date.today().year,
    )
    resume_contexte = {
        c: contexte.get(c) for c in ("service", "annee", "departement", "sexe", "intention")
        if contexte.get(c)
    }
    utilisateur = question
    if resume_contexte:
        utilisateur = (
            f"Contexte de la conversation : {json.dumps(resume_contexte, ensure_ascii=False)}\n"
            f"Question : {question}"
        )

    corps = json.dumps(
        {
            "model": settings.GROQ_MODELE,
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": utilisateur},
            ],
            "temperature": 0,
            "max_tokens": 250,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    requete = urllib.request.Request(
        URL_GROQ,
        data=corps,
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
            # Sans User-Agent explicite, Cloudflare renvoie une erreur 1010.
            "User-Agent": "gestion-sociaux/1.0",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=settings.GROQ_TIMEOUT) as reponse:
            charge = json.load(reponse)
        return json.loads(charge["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as erreur:
        journal.warning("LLM indisponible (HTTP %s) : repli sur les regles.", erreur.code)
    except Exception as erreur:  # reseau, timeout, JSON invalide...
        journal.warning("LLM indisponible (%s) : repli sur les regles.", type(erreur).__name__)
    return None


def _annees_connues() -> list[int]:
    from .models import Transaction

    return sorted(
        Transaction.objects.order_by().values_list("annee", flat=True).distinct(), reverse=True
    )


def _valider(brut: dict) -> dict:
    """
    Ne conserve que ce qui existe reellement en base.

    C'est le garde-fou central : une valeur inventee par le modele est ecartee
    ici et n'atteint jamais la couche de requetes.
    """
    plan = {
        "intention": None,
        "service": None,
        "annee": None,
        "departement": None,
        "sexe": None,
        "employe": None,
        "confiance": 0.0,
    }
    if not isinstance(brut, dict):
        return plan

    intention = brut.get("intention")
    if isinstance(intention, str) and intention in INTENTIONS_VALIDES:
        plan["intention"] = None if intention == "inconnu" else intention

    service = brut.get("service")
    if isinstance(service, str) and service:
        plan["service"] = Activitee.objects.filter(service__iexact=service.strip()).first()

    departement = brut.get("departement")
    if isinstance(departement, str) and departement:
        existe = (
            Personnel.objects.filter(departement__iexact=departement.strip())
            .values_list("departement", flat=True)
            .first()
        )
        plan["departement"] = existe

    annee = brut.get("annee")
    if isinstance(annee, (int, float)) and 1990 <= int(annee) <= date.today().year + 1:
        plan["annee"] = int(annee)

    sexe = brut.get("sexe")
    if isinstance(sexe, str) and sexe.upper() in ("H", "F"):
        plan["sexe"] = sexe.upper()

    employe = brut.get("employe")
    if isinstance(employe, str) and employe.strip():
        plan["employe"] = employe.strip()

    confiance = brut.get("confiance")
    if isinstance(confiance, (int, float)):
        plan["confiance"] = max(0.0, min(1.0, float(confiance)))

    return plan


def analyser(question: str, contexte: dict | None = None) -> dict | None:
    """
    Traduit la question en plan de requete valide, ou None si le LLM est
    indisponible (pas de clef, panne reseau, reponse inexploitable).
    """
    if not disponible():
        return None
    try:
        brut = _appeler_groq(question, contexte or {})
    except Exception as erreur:
        # Le renfort LLM est un bonus : il ne doit JAMAIS faire tomber
        # l'assistant, quelle que soit la nature de la panne.
        journal.warning("Analyse LLM impossible (%s) : repli sur les regles.", type(erreur).__name__)
        return None
    return _valider(brut) if brut is not None else None
