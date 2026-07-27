"""Filtres django-filter pour les listes de l'espace admin."""

import django_filters as df

from .models import Activitee, Personnel, Transaction


class PersonnelFilter(df.FilterSet):
    departement = df.CharFilter(field_name="departement", lookup_expr="iexact")
    sexe = df.CharFilter(field_name="sexe", lookup_expr="iexact")
    nb_enfants_min = df.NumberFilter(field_name="nb_enfants", lookup_expr="gte")
    nb_enfants_max = df.NumberFilter(field_name="nb_enfants", lookup_expr="lte")
    recrute_avant = df.DateFilter(field_name="date_recrutement", lookup_expr="lte")
    recrute_apres = df.DateFilter(field_name="date_recrutement", lookup_expr="gte")
    # Employes ayant (ou non) beneficie d'un service donne.
    a_beneficie_de = df.NumberFilter(method="filtre_a_beneficie")
    jamais_beneficie_de = df.NumberFilter(method="filtre_jamais_beneficie")
    annee = df.NumberFilter(field_name="transactions__annee", distinct=True)

    class Meta:
        model = Personnel
        fields = ["departement", "nb_enfants", "sexe"]

    def filtre_a_beneficie(self, queryset, name, value):
        return queryset.filter(transactions__id_activitee=value).distinct()

    def filtre_jamais_beneficie(self, queryset, name, value):
        return queryset.exclude(transactions__id_activitee=value).distinct()


class ActiviteeFilter(df.FilterSet):
    service = df.CharFilter(field_name="service", lookup_expr="icontains")
    regle_attribution = df.CharFilter(field_name="regle_attribution", lookup_expr="iexact")

    class Meta:
        model = Activitee
        fields = ["service", "regle_attribution"]


class TransactionFilter(df.FilterSet):
    service = df.NumberFilter(field_name="id_activitee")
    departement = df.CharFilter(field_name="matricule__departement", lookup_expr="iexact")
    sexe = df.CharFilter(field_name="matricule__sexe", lookup_expr="iexact")
    annee = df.NumberFilter(field_name="annee")
    annee_min = df.NumberFilter(field_name="annee", lookup_expr="gte")
    annee_max = df.NumberFilter(field_name="annee", lookup_expr="lte")
    montant_min = df.NumberFilter(field_name="montantTR", lookup_expr="gte")
    montant_max = df.NumberFilter(field_name="montantTR", lookup_expr="lte")
    date_min = df.DateFilter(field_name="date_transaction", lookup_expr="gte")
    date_max = df.DateFilter(field_name="date_transaction", lookup_expr="lte")

    class Meta:
        model = Transaction
        fields = ["matricule", "id_activitee", "annee"]
