"""
Interface d'administration Django.

Elle sert de porte de secours technique (correction de donnees, gestion des
comptes), l'interface metier etant l'application React. Les regles
d'attribution y sont appliquees : elles sont portees par `Transaction.clean()`,
que les formulaires Django appellent, et non par les serializers DRF.
"""

from django.contrib import admin

from .models import Activitee, Personnel, Transaction

admin.site.site_header = "MarsaSocial — administration technique"
admin.site.site_title = "MarsaSocial"
admin.site.index_title = "Donnees et comptes"


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = (
        "matricule", "nom", "prenom", "sexe", "departement", "date_recrutement", "nb_enfants"
    )
    search_fields = ("matricule", "nom", "prenom")
    list_filter = ("departement", "sexe")


@admin.register(Activitee)
class ActiviteeAdmin(admin.ModelAdmin):
    list_display = ("id_activitee", "service", "montantSC", "budget_alloue", "regle_attribution")
    list_filter = ("regle_attribution",)
    search_fields = ("service",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id_transaction",
        "matricule",
        "id_activitee",
        "montantTR",
        "date_transaction",
        "annee",
    )
    search_fields = ("matricule__matricule", "matricule__nom", "id_activitee__service")
    list_filter = ("annee", "id_activitee")
    autocomplete_fields = ("matricule", "id_activitee")
