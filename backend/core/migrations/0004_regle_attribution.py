"""
Remplace le booleen `unique_par_employe` par `regle_attribution`, qui exprime
trois comportements au lieu de deux.

Conversion :
    unique_par_employe = False  ->  ANNUELLE
    unique_par_employe = True   ->  UNIQUE
    ... puis le Hajj passe en ROTATION : un employe ne peut y retourner que
    lorsque tout le personnel a ete servi autant de fois que lui.
"""

from django.db import migrations, models

MOTS_ROTATION = ("hajj", "omra", "pelerinage")


def convertir(apps, schema_editor):
    Activitee = apps.get_model("core", "Activitee")
    for activitee in Activitee.objects.all():
        libelle = activitee.service.lower()
        if any(mot in libelle for mot in MOTS_ROTATION):
            activitee.regle_attribution = "ROTATION"
        elif activitee.unique_par_employe:
            activitee.regle_attribution = "UNIQUE"
        else:
            activitee.regle_attribution = "ANNUELLE"
        activitee.save(update_fields=["regle_attribution"])


def revenir(apps, schema_editor):
    Activitee = apps.get_model("core", "Activitee")
    for activitee in Activitee.objects.all():
        activitee.unique_par_employe = activitee.regle_attribution in ("UNIQUE", "ROTATION")
        activitee.save(update_fields=["unique_par_employe"])


class Migration(migrations.Migration):
    dependencies = [("core", "0003_remplir_sexe")]

    operations = [
        migrations.AddField(
            model_name="activitee",
            name="regle_attribution",
            field=models.CharField(
                choices=[
                    ("ANNUELLE", "Renouvelable chaque annee"),
                    ("UNIQUE", "Une seule fois par employe"),
                    ("ROTATION", "Rotation equitable : un nouveau tour quand tout le monde a ete servi"),
                ],
                default="ANNUELLE",
                max_length=10,
                verbose_name="Regle d'attribution",
            ),
        ),
        migrations.RunPython(convertir, revenir),
        migrations.RemoveField(model_name="activitee", name="unique_par_employe"),
    ]
