"""
Rattrapage du champ `sexe` pour les dossiers deja enregistres.

Le sexe est deduit du prenom a partir d'une liste de prenoms courants. Les
prenoms inconnus restent vides : mieux vaut « non renseigne » qu'une valeur
inventee, l'admin corrigera depuis la fiche de l'employe.
"""

from django.db import migrations

PRENOMS_H = {
    "mohamed", "youssef", "hamza", "karim", "omar", "reda", "anas", "yassine",
    "mehdi", "adil", "rachid", "khalid", "said", "hicham", "abdellah", "ismail",
    "ahmed", "hassan", "othmane", "ayoub", "soufiane", "zakaria", "nabil",
    "jamal", "mustapha", "abdelaziz", "brahim", "tarik", "amine", "walid",
}
PRENOMS_F = {
    "fatima", "khadija", "salma", "imane", "nadia", "hanane", "meryem", "sanaa",
    "ghita", "aicha", "loubna", "samira", "zineb", "houda", "amina", "hind",
    "asmae", "nawal", "leila", "rajae", "soukaina", "chaimae", "btissam",
    "karima", "latifa", "malika", "naima", "rachida", "siham", "wafae",
}


def remplir(apps, schema_editor):
    Personnel = apps.get_model("core", "Personnel")
    a_modifier = []
    for employe in Personnel.objects.filter(sexe=""):
        prenom = (employe.prenom or "").strip().lower()
        if prenom in PRENOMS_H:
            employe.sexe = "H"
        elif prenom in PRENOMS_F:
            employe.sexe = "F"
        else:
            continue
        a_modifier.append(employe)
    Personnel.objects.bulk_update(a_modifier, ["sexe"])


def vider(apps, schema_editor):
    apps.get_model("core", "Personnel").objects.update(sexe="")


class Migration(migrations.Migration):
    dependencies = [("core", "0002_personnel_sexe")]
    operations = [migrations.RunPython(remplir, vider)]
