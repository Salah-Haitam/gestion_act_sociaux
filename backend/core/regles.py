"""
Regles d'attribution des actions sociales.

Un seul endroit decide si un employe a droit a un service. Le serializer s'en
sert pour refuser une ecriture, l'endpoint de verification pour prevenir
l'administrateur avant la saisie : les deux ne peuvent pas diverger.

Trois regles, portees par `Activitee.regle_attribution` :

  ANNUELLE  une fois par an et par employe.
  UNIQUE    une seule fois dans la carriere.
  ROTATION  une seule fois par tour. Un employe n'est eligible que s'il compte
            le MINIMUM d'attributions observe sur l'effectif. Autrement dit
            personne ne repart tant qu'un collegue n'est jamais parti ; quand
            tout le monde a ete servi une fois, un deuxieme tour s'ouvre.
"""

from django.db.models import Count, Min, Q

from .models import Activitee, Personnel, Transaction


def _historique(personnel, activitee, exclure=None):
    lignes = Transaction.objects.filter(matricule=personnel, id_activitee=activitee)
    return lignes.exclude(pk=exclure) if exclure else lignes


def _attributions_par_employe(activitee, exclure=None):
    """Nombre d'attributions de ce service, employe par employe."""
    condition = Q(transactions__id_activitee=activitee)
    if exclure:
        condition &= ~Q(transactions__pk=exclure)
    return Personnel.objects.annotate(nb=Count("transactions", filter=condition, distinct=True))


def etat_attribution(personnel, activitee, annee=None, exclure=None) -> dict:
    """
    Evalue le droit d'un employe a un service et explique la decision.

    Renvoie un dictionnaire directement exploitable par l'API et l'interface :
    `autorise`, `message`, `historique`, plus l'etat du tour pour ROTATION.
    """
    historique = _historique(personnel, activitee, exclure)
    deja = historique.count()
    nom = f"{personnel.nom} {personnel.prenom}"
    etat = {
        "regle": activitee.regle_attribution,
        "regle_libelle": activitee.get_regle_attribution_display(),
        "nb_attributions": deja,
        "historique": historique.order_by("annee"),
        "autorise": True,
        "avertissement": False,
        "message": "",
        "tour": None,
    }

    # --- UNIQUE : une seule fois, definitivement -------------------------
    if activitee.regle_attribution == Activitee.UNIQUE:
        if deja:
            precedente = historique.first()
            etat.update(
                autorise=False,
                message=(
                    f"{nom} a deja beneficie du service « {activitee.service} » "
                    f"en {precedente.annee}. Ce service n'est accorde qu'une seule fois."
                ),
            )
        else:
            etat["message"] = f"{nom} n'a jamais beneficie de ce service."
        return etat

    # --- ROTATION : un nouveau tour quand tout le monde a ete servi ------
    if activitee.regle_attribution == Activitee.ROTATION:
        agregat = _attributions_par_employe(activitee, exclure).aggregate(m=Min("nb"))
        minimum = agregat["m"] or 0
        en_retard = _attributions_par_employe(activitee, exclure).filter(nb__lt=deja).count()
        etat["tour"] = {
            "tour_en_cours": minimum + 1,
            "minimum": minimum,
            "en_attente": en_retard,
        }

        if deja > minimum:
            etat.update(
                autorise=False,
                message=(
                    f"{nom} a deja beneficie du service « {activitee.service} » "
                    f"{deja} fois. Un nouveau depart n'est possible que lorsque tout le "
                    f"personnel aura ete servi au moins {deja} fois : "
                    f"{en_retard} employe(s) sont encore en attente."
                ),
            )
        elif deja:
            etat["message"] = (
                f"Tour {minimum + 1} : tout le personnel a deja beneficie {minimum} fois "
                f"de « {activitee.service} ». {nom} est de nouveau eligible."
            )
        else:
            etat["message"] = f"{nom} n'a jamais beneficie de ce service."
        return etat

    # --- ANNUELLE : une fois par an --------------------------------------
    if annee:
        cette_annee = historique.filter(annee=annee).first()
        if cette_annee:
            etat.update(
                autorise=False,
                message=(
                    f"{nom} a deja beneficie du service « {activitee.service} » "
                    f"en {annee} (transaction n°{cette_annee.id_transaction})."
                ),
            )
            return etat
    if deja:
        annees = ", ".join(str(t.annee) for t in historique.order_by("annee"))
        etat.update(
            avertissement=True,
            message=(
                f"Attention : {nom} a deja beneficie de ce service les annees "
                f"precedentes ({annees}). L'attribution reste autorisee."
            ),
        )
    else:
        etat["message"] = f"{nom} n'a jamais beneficie de ce service."
    return etat


def controler_attribution(personnel, activitee, annee=None, exclure=None):
    """Message d'erreur si l'attribution est interdite, None sinon."""
    etat = etat_attribution(personnel, activitee, annee, exclure)
    return None if etat["autorise"] else f"REFUS : {etat['message']}"
