"""API REST de la plateforme de gestion des actions sociales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import ai, exports
from .filters import ActiviteeFilter, PersonnelFilter, TransactionFilter
from .models import Activitee, Personnel, Transaction
from .serializers import (
    ActiviteeSerializer,
    PersonnelSerializer,
    TransactionSerializer,
    UtilisateurSerializer,
)

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))


# ==========================================================================
# Authentification
# ==========================================================================


class ConnexionView(TokenObtainPairView):
    """POST /api/auth/login/ -> {access, refresh, utilisateur}"""

    permission_classes = []

    def post(self, request, *args, **kwargs):
        reponse = super().post(request, *args, **kwargs)
        if reponse.status_code == 200:
            from django.contrib.auth import get_user_model

            utilisateur = (
                get_user_model().objects.filter(username=request.data.get("username")).first()
            )
            if utilisateur:
                reponse.data["utilisateur"] = UtilisateurSerializer(utilisateur).data
        return reponse


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profil(request):
    """GET /api/auth/me/ - profil de l'admin connecte."""
    return Response(UtilisateurSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deconnexion(request):
    """POST /api/auth/logout/ - ferme la session Django (le front oublie ses jetons)."""
    from django.contrib.auth import logout

    logout(request)
    return Response({"detail": "Deconnecte."})


# ==========================================================================
# CRUD Personnel
# ==========================================================================


class PersonnelViewSet(viewsets.ModelViewSet):
    serializer_class = PersonnelSerializer
    filterset_class = PersonnelFilter
    search_fields = ["matricule", "nom", "prenom", "departement"]
    ordering_fields = [
        "matricule",
        "nom",
        "prenom",
        "sexe",
        "departement",
        "date_recrutement",
        "nb_enfants",
    ]
    ordering = ["nom", "prenom"]

    def get_queryset(self):
        return (
            Personnel.objects.all()
            .annotate(
                nb_tr=Count("transactions", distinct=True),
                total_tr=Coalesce(Sum("transactions__montantTR"), ZERO),
            )
            .prefetch_related("transactions__id_activitee")
        )

    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        """Detail des services dont un employe a beneficie."""
        employe = self.get_object()
        lignes = employe.transactions.select_related("id_activitee").all()
        return Response(TransactionSerializer(lignes, many=True).data)

    @action(detail=False, methods=["get"], url_path="sans-aucune-aide")
    def sans_aucune_aide(self, request):
        """Employes n'ayant jamais beneficie de la moindre action sociale."""
        employes = self.filter_queryset(self.get_queryset()).filter(transactions__isnull=True)
        page = self.paginate_queryset(employes)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(employes, many=True).data)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """?format=excel|pdf - export de la liste filtree."""
        employes = self.filter_queryset(self.get_queryset())
        colonnes = [
            "matricule",
            "nom",
            "prenom",
            "sexe_libelle",
            "departement",
            "date_recrutement",
            "nb_enfants",
            "anciennete",
            "nb_transactions",
            "total_percu",
        ]
        lignes = [
            {c: l.get(c) for c in colonnes} for l in PersonnelSerializer(employes, many=True).data
        ]
        return _rendre_export(request, "Liste du personnel", colonnes, lignes, "personnel")

    @action(detail=False, methods=["get"])
    def departements(self, request):
        """Liste des departements distincts (pour les filtres du front)."""
        # order_by() vide : sinon l'ordering par defaut du modele casse le DISTINCT.
        return Response(
            sorted(
                Personnel.objects.order_by().values_list("departement", flat=True).distinct()
            )
        )


# ==========================================================================
# CRUD Activitee + equite
# ==========================================================================


class ActiviteeViewSet(viewsets.ModelViewSet):
    serializer_class = ActiviteeSerializer
    filterset_class = ActiviteeFilter
    search_fields = ["service", "description"]
    ordering_fields = ["service", "montantSC", "budget_alloue"]
    ordering = ["service"]

    def get_queryset(self):
        return Activitee.objects.annotate(
            consomme=Coalesce(Sum("transactions__montantTR"), ZERO),
            beneficiaires=Count("transactions__matricule", distinct=True),
        )

    def destroy(self, request, *args, **kwargs):
        """Une activite deja utilisee ne peut pas etre supprimee (FK PROTECT)."""
        activitee = self.get_object()
        rattachees = activitee.transactions.count()
        if rattachees:
            return Response(
                {
                    "detail": (
                        f"Suppression impossible : {rattachees} transaction(s) sont rattachees "
                        f"a « {activitee.service} »."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def beneficiaires(self, request, pk=None):
        """Employes ayant DEJA beneficie de ce service (option ?annee=)."""
        activitee = self.get_object()
        annee = request.query_params.get("annee")
        base = Transaction.objects.filter(id_activitee=activitee).select_related("matricule")
        if annee:
            base = base.filter(annee=annee)
        donnees = [
            {
                "id_transaction": t.id_transaction,
                "matricule": t.matricule_id,
                "nom": t.matricule.nom,
                "prenom": t.matricule.prenom,
                "departement": t.matricule.departement,
                "nb_enfants": t.matricule.nb_enfants,
                "montantTR": t.montantTR,
                "date_transaction": t.date_transaction,
                "annee": t.annee,
            }
            for t in base.order_by("matricule__nom", "-annee")
        ]
        return Response(
            {
                "service": activitee.service,
                "annee": int(annee) if annee else None,
                "total": len(donnees),
                "resultats": donnees,
            }
        )

    @action(detail=True, methods=["get"], url_path="non-beneficiaires")
    def non_beneficiaires(self, request, pk=None):
        """
        Employes n'ayant JAMAIS beneficie de ce service : les opportunites manquees.

        Equivalent SQL :
            SELECT p.* FROM personnel p
            LEFT JOIN transaction t
                   ON t.matricule = p.matricule
                  AND t.id_activitee = :id  [AND t.annee = :annee]
            WHERE t.id_transaction IS NULL;
        """
        activitee = self.get_object()
        annee = request.query_params.get("annee")
        departement = request.query_params.get("departement")

        deja_servis = Transaction.objects.filter(id_activitee=activitee)
        if annee:
            deja_servis = deja_servis.filter(annee=annee)

        oublies = Personnel.objects.exclude(matricule__in=deja_servis.values("matricule")).annotate(
            nb_aides=Count("transactions", distinct=True),
            total_percu=Coalesce(Sum("transactions__montantTR"), ZERO),
        )
        if departement:
            oublies = oublies.filter(departement__iexact=departement)

        donnees = [
            {
                "matricule": e.matricule,
                "nom": e.nom,
                "prenom": e.prenom,
                "sexe": e.sexe_libelle,
                "departement": e.departement,
                "date_recrutement": e.date_recrutement,
                "anciennete": e.anciennete,
                "nb_enfants": e.nb_enfants,
                "nb_aides_total": e.nb_aides,
                "total_percu": e.total_percu,
            }
            for e in oublies.order_by("nom", "prenom")
        ]
        effectif = Personnel.objects.count()
        return Response(
            {
                "service": activitee.service,
                "annee": int(annee) if annee else None,
                "effectif_total": effectif,
                "total": len(donnees),
                "taux_couverture": (
                    round((effectif - len(donnees)) / effectif * 100, 2) if effectif else 0
                ),
                "resultats": donnees,
            }
        )

    @action(detail=True, methods=["get"], url_path="export-non-beneficiaires")
    def export_non_beneficiaires(self, request, pk=None):
        reponse = self.non_beneficiaires(request, pk)
        activitee = self.get_object()
        colonnes = [
            "matricule",
            "nom",
            "prenom",
            "sexe",
            "departement",
            "date_recrutement",
            "anciennete",
            "nb_enfants",
            "nb_aides_total",
        ]
        lignes = [{c: l.get(c) for c in colonnes} for l in reponse.data["resultats"]]
        return _rendre_export(
            request,
            f"Non-beneficiaires - {activitee.service}",
            colonnes,
            lignes,
            f"non_beneficiaires_{activitee.id_activitee}",
        )

    @action(detail=False, methods=["get"])
    def budget(self, request):
        """Suivi budgetaire par activite, avec alerte de depassement de seuil."""
        seuil = int(request.query_params.get("seuil", settings.BUDGET_ALERT_THRESHOLD))
        annee = request.query_params.get("annee")
        lignes = []
        for activitee in Activitee.objects.all():
            transactions = activitee.transactions.all()
            if annee:
                transactions = transactions.filter(annee=annee)
            consomme = transactions.aggregate(s=Coalesce(Sum("montantTR"), ZERO))["s"]
            alloue = activitee.budget_alloue or Decimal("0")
            taux = round(float(consomme / alloue) * 100, 2) if alloue > 0 else None
            if taux is None:
                alerte = "budget_non_defini"
            elif taux >= 100:
                alerte = "depassement"
            elif taux >= seuil:
                alerte = "seuil_atteint"
            else:
                alerte = "ok"
            lignes.append(
                {
                    "id_activitee": activitee.id_activitee,
                    "service": activitee.service,
                    "montantSC": activitee.montantSC,
                    "budget_alloue": alloue,
                    "consomme": consomme,
                    "restant": alloue - consomme,
                    "taux_consommation": taux,
                    "nb_transactions": transactions.count(),
                    "alerte": alerte,
                }
            )
        total_alloue = sum((l["budget_alloue"] for l in lignes), Decimal("0"))
        total_consomme = sum((l["consomme"] for l in lignes), Decimal("0"))
        return Response(
            {
                "seuil_alerte": seuil,
                "annee": int(annee) if annee else None,
                "total_alloue": total_alloue,
                "total_consomme": total_consomme,
                "total_restant": total_alloue - total_consomme,
                "taux_global": (
                    round(float(total_consomme / total_alloue) * 100, 2) if total_alloue > 0 else None
                ),
                "resultats": lignes,
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        activites = self.filter_queryset(self.get_queryset())
        colonnes = [
            "service",
            "montantSC",
            "budget_alloue",
            "montant_consomme",
            "budget_restant",
            "taux_consommation",
            "nb_beneficiaires",
        ]
        lignes = [
            {c: l.get(c) for c in colonnes} for l in ActiviteeSerializer(activites, many=True).data
        ]
        return _rendre_export(request, "Activites et budgets", colonnes, lignes, "activites")


# ==========================================================================
# CRUD Transaction
# ==========================================================================


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    search_fields = [
        "matricule__matricule",
        "matricule__nom",
        "matricule__prenom",
        "id_activitee__service",
    ]
    ordering_fields = [
        "id_transaction",
        "date_transaction",
        "annee",
        "montantTR",
        "matricule__nom",
        "id_activitee__service",
    ]
    ordering = ["-date_transaction"]

    def get_queryset(self):
        return Transaction.objects.select_related("matricule", "id_activitee")

    @action(detail=False, methods=["get"], url_path="verifier-doublon")
    def verifier_doublon(self, request):
        """
        Controle prealable a la saisie : ?matricule=..&id_activitee=..&annee=..
        Renvoie une alerte si l'employe a deja beneficie du service.
        """
        matricule = request.query_params.get("matricule")
        id_activitee = request.query_params.get("id_activitee")
        annee = request.query_params.get("annee") or date.today().year
        if not matricule or not id_activitee:
            return Response(
                {"detail": "Parametres 'matricule' et 'id_activitee' requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activitee = Activitee.objects.filter(pk=id_activitee).first()
        employe = Personnel.objects.filter(pk=matricule).first()
        if not activitee or not employe:
            return Response(
                {"detail": "Employe ou activite introuvable."}, status=status.HTTP_404_NOT_FOUND
            )

        historique = Transaction.objects.filter(matricule=employe, id_activitee=activitee)
        cette_annee = historique.filter(annee=annee)

        if activitee.unique_par_employe and historique.exists():
            precedente = historique.first()
            return Response(
                {
                    "doublon": True,
                    "bloquant": True,
                    "message": (
                        f"{employe.nom} {employe.prenom} a deja beneficie du service "
                        f"« {activitee.service} » en {precedente.annee}. "
                        f"Ce service n'est pas renouvelable."
                    ),
                    "historique": TransactionSerializer(historique, many=True).data,
                }
            )
        if cette_annee.exists():
            return Response(
                {
                    "doublon": True,
                    "bloquant": True,
                    "message": (
                        f"{employe.nom} {employe.prenom} a deja beneficie du service "
                        f"« {activitee.service} » en {annee}."
                    ),
                    "historique": TransactionSerializer(cette_annee, many=True).data,
                }
            )
        if historique.exists():
            annees = ", ".join(str(t.annee) for t in historique)
            return Response(
                {
                    "doublon": False,
                    "bloquant": False,
                    "message": (
                        f"Attention : {employe.nom} {employe.prenom} a deja beneficie de ce "
                        f"service les annees precedentes ({annees})."
                    ),
                    "historique": TransactionSerializer(historique, many=True).data,
                }
            )
        return Response(
            {
                "doublon": False,
                "bloquant": False,
                "message": f"{employe.nom} {employe.prenom} n'a jamais beneficie de ce service.",
                "historique": [],
            }
        )

    @action(detail=True, methods=["get"])
    def attestation(self, request, pk=None):
        """Attestation PDF individuelle."""
        return exports.attestation_pdf(self.get_object())

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        transactions = self.filter_queryset(self.get_queryset())
        colonnes = [
            "id_transaction",
            "matricule",
            "nom",
            "prenom",
            "departement",
            "service",
            "montantTR",
            "duree",
            "date_transaction",
            "annee",
        ]
        lignes = [
            {c: l.get(c) for c in colonnes}
            for l in TransactionSerializer(transactions, many=True).data
        ]
        return _rendre_export(request, "Registre des transactions", colonnes, lignes, "transactions")

    @action(detail=False, methods=["get"])
    def annees(self, request):
        """Annees presentes en base (pour les filtres du front)."""
        return Response(
            sorted(
                Transaction.objects.order_by().values_list("annee", flat=True).distinct(),
                reverse=True,
            )
        )


# ==========================================================================
# Statistiques
# ==========================================================================


class StatistiquesView(APIView):
    """GET /api/stats/ - tableau de bord consolide."""

    def get(self, request):
        annee = request.query_params.get("annee")
        transactions = Transaction.objects.all()
        if annee:
            transactions = transactions.filter(annee=annee)
        filtre_annee = Q(transactions__annee=annee) if annee else Q()

        effectif = Personnel.objects.count()
        servis = Personnel.objects.filter(transactions__in=transactions).distinct().count()
        nb_transactions = transactions.count()
        total_distribue = transactions.aggregate(s=Coalesce(Sum("montantTR"), ZERO))["s"]

        par_service = list(
            Activitee.objects.annotate(
                total=Coalesce(Sum("transactions__montantTR", filter=filtre_annee), ZERO),
                nb_transactions=Count("transactions", filter=filtre_annee, distinct=True),
                nb_beneficiaires=Count(
                    "transactions__matricule", filter=filtre_annee, distinct=True
                ),
            ).values(
                "id_activitee",
                "service",
                "total",
                "nb_transactions",
                "nb_beneficiaires",
                "budget_alloue",
            )
        )
        for ligne in par_service:
            ligne["taux_couverture"] = (
                round(ligne["nb_beneficiaires"] / effectif * 100, 2) if effectif else 0
            )

        par_annee = list(
            Transaction.objects.values("annee")
            .annotate(total=Coalesce(Sum("montantTR"), ZERO), nb=Count("id_transaction"))
            .order_by("annee")
        )

        par_departement = list(
            Personnel.objects.values("departement")
            .annotate(
                effectif=Count("matricule", distinct=True),
                nb_beneficiaires=Count("transactions__matricule", filter=filtre_annee, distinct=True),
                total=Coalesce(Sum("transactions__montantTR", filter=filtre_annee), ZERO),
            )
            .order_by("departement")
        )
        for ligne in par_departement:
            ligne["taux_couverture"] = (
                round(ligne["nb_beneficiaires"] / ligne["effectif"] * 100, 2)
                if ligne["effectif"]
                else 0
            )

        # Equite hommes / femmes : meme lecture que par departement.
        par_sexe = list(
            Personnel.objects.values("sexe")
            .annotate(
                effectif=Count("matricule", distinct=True),
                nb_beneficiaires=Count("transactions__matricule", filter=filtre_annee, distinct=True),
                total=Coalesce(Sum("transactions__montantTR", filter=filtre_annee), ZERO),
            )
            .order_by("sexe")
        )
        libelles = dict(Personnel.SEXE_CHOIX)
        for ligne in par_sexe:
            ligne["libelle"] = libelles.get(ligne["sexe"], "Non renseigne")
            ligne["taux_couverture"] = (
                round(ligne["nb_beneficiaires"] / ligne["effectif"] * 100, 2)
                if ligne["effectif"]
                else 0
            )
            ligne["montant_moyen"] = (
                round(float(ligne["total"]) / ligne["nb_beneficiaires"], 2)
                if ligne["nb_beneficiaires"]
                else 0
            )

        # Evolution service x annee (graphique empile).
        evolution = list(
            Transaction.objects.values("annee", "id_activitee__service")
            .annotate(total=Coalesce(Sum("montantTR"), ZERO))
            .order_by("annee")
        )

        return Response(
            {
                "annee": int(annee) if annee else None,
                "effectif": effectif,
                "nb_beneficiaires": servis,
                "nb_jamais_servis": effectif - servis,
                "taux_couverture_global": round(servis / effectif * 100, 2) if effectif else 0,
                "nb_transactions": nb_transactions,
                "total_distribue": total_distribue,
                "montant_moyen": (
                    round(float(total_distribue) / nb_transactions, 2) if nb_transactions else 0
                ),
                "nb_activites": Activitee.objects.count(),
                "par_service": par_service,
                "par_annee": par_annee,
                "par_departement": par_departement,
                "par_sexe": par_sexe,
                "evolution": [
                    {"annee": e["annee"], "service": e["id_activitee__service"], "total": e["total"]}
                    for e in evolution
                ],
            }
        )


class CouvertureView(APIView):
    """GET /api/stats/couverture/ - taux de couverture service par service."""

    def get(self, request):
        annee = request.query_params.get("annee")
        effectif = Personnel.objects.count()
        lignes = []
        for activitee in Activitee.objects.all():
            base = Transaction.objects.filter(id_activitee=activitee)
            if annee:
                base = base.filter(annee=annee)
            servis = base.values("matricule").distinct().count()
            lignes.append(
                {
                    "id_activitee": activitee.id_activitee,
                    "service": activitee.service,
                    "beneficiaires": servis,
                    "non_beneficiaires": effectif - servis,
                    "effectif": effectif,
                    "taux_couverture": round(servis / effectif * 100, 2) if effectif else 0,
                }
            )
        lignes.sort(key=lambda l: l["taux_couverture"])
        return Response(
            {"annee": int(annee) if annee else None, "effectif": effectif, "resultats": lignes}
        )


class RapportAnnuelView(APIView):
    """GET /api/stats/rapport-annuel/?annee=2025&format=excel|pdf"""

    def get(self, request):
        annee = int(request.query_params.get("annee") or date.today().year)
        effectif = Personnel.objects.count()
        colonnes = [
            "service",
            "nb_beneficiaires",
            "nb_transactions",
            "montant_total",
            "budget_alloue",
            "taux_couverture",
        ]
        lignes = []
        for activitee in Activitee.objects.all():
            base = Transaction.objects.filter(id_activitee=activitee, annee=annee)
            beneficiaires = base.values("matricule").distinct().count()
            lignes.append(
                {
                    "service": activitee.service,
                    "nb_beneficiaires": beneficiaires,
                    "nb_transactions": base.count(),
                    "montant_total": base.aggregate(s=Coalesce(Sum("montantTR"), ZERO))["s"],
                    "budget_alloue": activitee.budget_alloue,
                    "taux_couverture": (
                        round(beneficiaires / effectif * 100, 2) if effectif else 0
                    ),
                }
            )
        return _rendre_export(
            request,
            f"Etat recapitulatif annuel {annee}",
            colonnes,
            lignes,
            f"rapport_annuel_{annee}",
        )


# ==========================================================================
# IA
# ==========================================================================


def _calculer_recommandations(request):
    """Facteur commun a la vue JSON et a la vue export."""
    id_activitee = request.query_params.get("id_activitee")
    if not id_activitee:
        return None, Response(
            {"detail": "Parametre 'id_activitee' requis."}, status=status.HTTP_400_BAD_REQUEST
        )
    activitee = Activitee.objects.filter(pk=id_activitee).first()
    if not activitee:
        return None, Response({"detail": "Activite introuvable."}, status=status.HTTP_404_NOT_FOUND)

    annee = request.query_params.get("annee")
    limite = request.query_params.get("limite")
    departement = request.query_params.get("departement")
    seulement_eligibles = (request.query_params.get("eligibles") or "true").lower() != "false"

    resultats = ai.scorer_beneficiaires(activitee, annee=int(annee) if annee else None)
    if departement:
        resultats = [r for r in resultats if r["departement"].lower() == departement.lower()]
    if seulement_eligibles:
        resultats = [r for r in resultats if r["eligible"]]
    if limite:
        resultats = resultats[: int(limite)]

    budget = activitee.budget_alloue or Decimal("0")
    consomme = activitee.transactions.aggregate(s=Coalesce(Sum("montantTR"), ZERO))["s"]
    restant = budget - consomme
    financables = int(restant / activitee.montantSC) if activitee.montantSC and restant > 0 else 0

    return {
        "id_activitee": activitee.id_activitee,
        "service": activitee.service,
        "montantSC": activitee.montantSC,
        "budget_restant": restant,
        "beneficiaires_financables": financables,
        "total": len(resultats),
        "resultats": resultats,
    }, None


class RecommandationsView(APIView):
    """
    GET /api/ia/recommandations/?id_activitee=3&annee=2026&limite=20
    Classement des employes par score d'equite pour un service donne.
    """

    def get(self, request):
        donnees, erreur = _calculer_recommandations(request)
        return erreur if erreur is not None else Response(donnees)


class ExportRecommandationsView(APIView):
    """GET /api/ia/recommandations/export/?id_activitee=3&format=excel|pdf"""

    def get(self, request):
        donnees, erreur = _calculer_recommandations(request)
        if erreur is not None:
            return erreur
        colonnes = [
            "rang",
            "matricule",
            "nom",
            "prenom",
            "departement",
            "anciennete",
            "nb_enfants",
            "nb_aides_total",
            "score",
            "justifications",
        ]
        lignes = [{c: r.get(c) for c in colonnes} for r in donnees["resultats"]]
        return _rendre_export(
            request,
            f"Priorisation - {donnees['service']}",
            colonnes,
            lignes,
            "recommandations",
        )


class ClustersView(APIView):
    """GET /api/ia/clusters/?n=4 - segmentation K-Means du personnel."""

    def get(self, request):
        try:
            n = int(request.query_params.get("n", 4))
        except ValueError:
            n = 4
        return Response(ai.clusteriser(n_clusters=max(2, min(n, 8))))


class ChatbotView(APIView):
    """
    POST /api/ia/chatbot/ {"question": "...", "contexte": {...}}

    Le `contexte` renvoye dans la reponse doit etre repost par le client au tour
    suivant : il porte le sujet de la conversation (service, annee, departement)
    et permet de comprendre les questions elliptiques (« et en 2023 ? »).
    L'API reste ainsi sans etat.
    """

    def get(self, request):
        """Etat du moteur, pour que l'interface annonce ce qui est actif."""
        return Response(
            {
                "llm_actif": settings.LLM_ACTIF,
                "modele": settings.GROQ_MODELE if settings.LLM_ACTIF else None,
            }
        )

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response({"detail": "Question vide."}, status=status.HTTP_400_BAD_REQUEST)
        contexte = request.data.get("contexte")
        if not isinstance(contexte, dict):
            contexte = {}
        resultat = ai.repondre(question, contexte=contexte)
        resultat["question"] = question
        return Response(resultat)


# ==========================================================================
# Helper export
# ==========================================================================


def _rendre_export(request, titre, colonnes, lignes, nom_fichier):
    """Aiguille vers Excel ou PDF selon ?format=."""
    fmt = (request.query_params.get("format") or "excel").lower()
    if fmt == "pdf":
        return exports.export_pdf(titre, colonnes, lignes, nom_fichier)
    return exports.export_excel(titre, colonnes, lignes, nom_fichier)
