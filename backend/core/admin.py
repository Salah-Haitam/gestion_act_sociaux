from django.contrib import admin

from .models import Activitee, Personnel, Transaction


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = (
        "matricule", "nom", "prenom", "sexe", "departement", "date_recrutement", "nb_enfants"
    )
    search_fields = ("matricule", "nom", "prenom")
    list_filter = ("departement", "sexe")


@admin.register(Activitee)
class ActiviteeAdmin(admin.ModelAdmin):
    list_display = ("id_activitee", "service", "montantSC", "budget_alloue", "unique_par_employe")
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
