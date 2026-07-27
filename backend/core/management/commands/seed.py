"""
Jeu de donnees de demonstration.

    python manage.py seed            # cree les donnees si la base est vide
    python manage.py seed --reset    # vide puis recree
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from core.models import Activitee, Personnel, Transaction

NOMS = [
    "El Amrani", "Benjelloun", "Tazi", "Bennani", "Alaoui", "Chraibi", "Berrada",
    "Fassi", "Idrissi", "Kabbaj", "Lahlou", "Mekouar", "Naciri", "Ouazzani",
    "Sqalli", "Tahiri", "Zniber", "Bouzoubaa", "Cherkaoui", "Daoudi", "El Fassi",
    "Guessous", "Hakim", "Jaidi", "Karimi", "Lamrani", "Mansouri", "Nejjar",
    "Rachidi", "Sabri", "Tounsi", "Yousfi", "Zerouali", "Amrani", "Belkadi",
]
PRENOMS_H = [
    "Mohamed", "Youssef", "Hamza", "Karim", "Omar", "Reda", "Anas", "Yassine",
    "Mehdi", "Adil", "Rachid", "Khalid", "Said", "Hicham", "Abdellah", "Ismail",
]
PRENOMS_F = [
    "Fatima", "Khadija", "Salma", "Imane", "Nadia", "Hanane", "Meryem", "Sanaa",
    "Ghita", "Aicha", "Loubna", "Samira", "Zineb", "Houda", "Amina", "Hind",
]
DEPARTEMENTS = [
    "Exploitation Portuaire", "Maintenance", "Finance & Comptabilite",
    "Ressources Humaines", "Commercial", "Systemes d'Information",
    "Securite & HSE", "Logistique", "Juridique",
]

SERVICES = [
    # (service, montantSC, budget, regle d'attribution, description)
    ("Aide scolaire", 2500, 350000, "ANNUELLE", "Aide a la rentree scolaire, par enfant scolarise."),
    ("Aide au mariage", 8000, 200000, "UNIQUE", "Prime unique versee a l'occasion du mariage."),
    ("Pelerinage Hajj", 25000, 250000, "ROTATION",
     "Participation aux frais du pelerinage a La Mecque. Un employe ne peut repartir "
     "que lorsque tout le personnel a beneficie du meme nombre de departs."),
    ("Prime de naissance", 3000, 120000, "ANNUELLE", "Prime versee a chaque naissance."),
    ("Aide au deces", 10000, 150000, "ANNUELLE", "Secours accorde en cas de deces d'un proche."),
    ("Colonie de vacances", 1800, 180000, "ANNUELLE", "Sejour d'ete pour les enfants du personnel."),
    ("Aide medicale exceptionnelle", 6000, 200000, "ANNUELLE", "Prise en charge de frais medicaux lourds."),
    ("Pret logement", 40000, 400000, "UNIQUE", "Avance remboursable pour l'acquisition d'un logement."),
]

ANNEES = [2022, 2023, 2024, 2025, 2026]


class Command(BaseCommand):
    help = "Cree un jeu de donnees de demonstration (personnel, activites, transactions)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Vide les tables avant de recreer.")
        parser.add_argument("--employes", type=int, default=60, help="Nombre d'employes a creer.")

    @db_transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        if options["reset"]:
            Transaction.objects.all().delete()
            Activitee.objects.all().delete()
            Personnel.objects.all().delete()
            self.stdout.write(self.style.WARNING("Tables videes."))

        self._creer_admin()
        activites = self._creer_activites()
        employes = self._creer_personnel(options["employes"])
        self._creer_transactions(employes, activites)

        self.stdout.write(
            self.style.SUCCESS(
                f"OK - {Personnel.objects.count()} employes, "
                f"{Activitee.objects.count()} activites, "
                f"{Transaction.objects.count()} transactions."
            )
        )

    # ------------------------------------------------------------------
    def _creer_admin(self):
        Utilisateur = get_user_model()
        if not Utilisateur.objects.filter(username="admin").exists():
            Utilisateur.objects.create_superuser(
                username="admin",
                email="rh@marsamaroc.ma",
                password="admin123",
                first_name="Administrateur",
                last_name="RH",
            )
            self.stdout.write(self.style.SUCCESS("Compte admin cree (admin / admin123)."))

    def _creer_activites(self):
        activites = []
        for service, montant, budget, regle, description in SERVICES:
            activitee, _ = Activitee.objects.get_or_create(
                service=service,
                defaults={
                    "montantSC": Decimal(montant),
                    "budget_alloue": Decimal(budget),
                    "regle_attribution": regle,
                    "description": description,
                },
            )
            activites.append(activitee)
        return activites

    def _creer_personnel(self, nombre):
        existants = Personnel.objects.count()
        if existants >= nombre:
            return list(Personnel.objects.all())

        employes = []
        for i in range(existants + 1, nombre + 1):
            homme = random.random() < 0.65
            prenom = random.choice(PRENOMS_H if homme else PRENOMS_F)
            jours = random.randint(400, 30 * 365)
            employes.append(
                Personnel(
                    matricule=f"MM{i:04d}",
                    nom=random.choice(NOMS),
                    prenom=prenom,
                    sexe="H" if homme else "F",
                    departement=random.choice(DEPARTEMENTS),
                    date_recrutement=date.today() - timedelta(days=jours),
                    nb_enfants=random.choices([0, 1, 2, 3, 4, 5], weights=[20, 20, 28, 18, 10, 4])[0],
                )
            )
        Personnel.objects.bulk_create(employes)
        return list(Personnel.objects.all())

    def _creer_transactions(self, employes, activites):
        if Transaction.objects.exists():
            return

        par_service = {a.service: a for a in activites}
        transactions = []

        # Environ 25 % du personnel ne recoit rien : ce sont les "oublies" que
        # la plateforme doit faire remonter.
        servis = random.sample(employes, k=int(len(employes) * 0.75))

        for employe in servis:
            # Aide scolaire : recurrente, reservee aux employes avec enfants.
            if employe.nb_enfants > 0:
                for annee in random.sample(ANNEES, k=random.randint(1, 3)):
                    activitee = par_service["Aide scolaire"]
                    transactions.append(
                        self._transaction(
                            employe,
                            activitee,
                            annee,
                            montant=activitee.montantSC * employe.nb_enfants,
                        )
                    )
                if random.random() < 0.4:
                    activitee = par_service["Colonie de vacances"]
                    annee = random.choice(ANNEES)
                    transactions.append(
                        self._transaction(employe, activitee, annee, duree=random.choice([7, 14, 21]))
                    )
                if random.random() < 0.35:
                    transactions.append(
                        self._transaction(
                            employe, par_service["Prime de naissance"], random.choice(ANNEES)
                        )
                    )

            # Services non renouvelables : une seule fois par employe.
            if random.random() < 0.25:
                transactions.append(
                    self._transaction(employe, par_service["Aide au mariage"], random.choice(ANNEES))
                )
            if employe.anciennete >= 12 and random.random() < 0.30:
                transactions.append(
                    self._transaction(employe, par_service["Pelerinage Hajj"], random.choice(ANNEES))
                )
            if employe.anciennete >= 8 and random.random() < 0.20:
                transactions.append(
                    self._transaction(employe, par_service["Pret logement"], random.choice(ANNEES))
                )

            # Aides ponctuelles.
            if random.random() < 0.20:
                transactions.append(
                    self._transaction(employe, par_service["Aide au deces"], random.choice(ANNEES))
                )
            if random.random() < 0.25:
                transactions.append(
                    self._transaction(
                        employe, par_service["Aide medicale exceptionnelle"], random.choice(ANNEES)
                    )
                )

        # Deduplique : un service UNIQUE ou en ROTATION n'est accorde qu'une
        # fois par employe dans ce jeu de demonstration (le premier tour n'est
        # jamais complet) ; les services annuels, une fois par annee.
        vues = set()
        propres = []
        for tr in transactions:
            activitee = tr.id_activitee
            cle = (
                (tr.matricule_id, activitee.id_activitee)
                if not activitee.renouvelable_chaque_annee
                else (tr.matricule_id, activitee.id_activitee, tr.annee)
            )
            if cle in vues:
                continue
            vues.add(cle)
            propres.append(tr)

        Transaction.objects.bulk_create(propres)

    def _transaction(self, employe, activitee, annee, montant=None, duree=0):
        montant = Decimal(montant if montant is not None else activitee.montantSC)
        # Petite variation autour du montant standard (+/- 10 %).
        montant = (montant * Decimal(random.uniform(0.9, 1.1))).quantize(Decimal("0.01"))
        # Pas de transaction dans le futur pour l'annee en cours.
        mois_max = date.today().month if annee == date.today().year else 12
        jour = date(annee, random.randint(1, mois_max), random.randint(1, 28))
        return Transaction(
            matricule=employe,
            id_activitee=activitee,
            montantTR=montant,
            duree=duree,
            date_transaction=jour,
            annee=annee,
        )
