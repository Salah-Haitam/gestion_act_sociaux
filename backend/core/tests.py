"""
Tests automatises de l'API.

    python manage.py test core
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from . import llm
from .ai import clusteriser, repondre, scorer_beneficiaires
from .models import Activitee, Personnel, Transaction


@override_settings(LLM_ACTIF=False)
class BaseAPITest(APITestCase):
    """
    Jeu de donnees minimal partage par tous les tests.

    Le renfort LLM est desactive par defaut : les tests restent hors ligne et
    deterministes. Seule la classe LLMTest le reactive, avec un appel simule.
    """

    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_superuser("admin", "rh@marsamaroc.ma", "motdepasse")

        cls.scolaire = Activitee.objects.create(
            service="Aide scolaire", montantSC=Decimal("2500"), budget_alloue=Decimal("10000")
        )
        cls.hajj = Activitee.objects.create(
            service="Pelerinage Hajj",
            montantSC=Decimal("25000"),
            budget_alloue=Decimal("50000"),
            regle_attribution=Activitee.ROTATION,
        )
        cls.mariage = Activitee.objects.create(
            service="Aide au mariage",
            montantSC=Decimal("8000"),
            budget_alloue=Decimal("40000"),
            regle_attribution=Activitee.UNIQUE,
        )

        cls.servi = Personnel.objects.create(
            matricule="MM0001",
            nom="Alaoui",
            prenom="Youssef",
            sexe="H",
            departement="Maintenance",
            date_recrutement=date(2005, 3, 1),
            nb_enfants=3,
        )
        cls.oublie = Personnel.objects.create(
            matricule="MM0002",
            nom="Bennani",
            prenom="Salma",
            sexe="F",
            departement="Finance",
            date_recrutement=date(2010, 9, 15),
            nb_enfants=4,
        )

        cls.transaction = Transaction.objects.create(
            matricule=cls.servi,
            id_activitee=cls.scolaire,
            montantTR=Decimal("2500"),
            duree=0,
            date_transaction=date(2024, 9, 10),
            annee=2024,
        )

    def setUp(self):
        self.client.force_authenticate(user=get_user_model().objects.get(username="admin"))


class AuthentificationTest(APITestCase):
    def test_api_fermee_sans_authentification(self):
        self.assertEqual(self.client.get("/api/personnel/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_retourne_un_jeton_et_le_profil(self):
        get_user_model().objects.create_superuser("admin", "a@b.ma", "motdepasse")
        reponse = self.client.post(
            reverse("login"), {"username": "admin", "password": "motdepasse"}, format="json"
        )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("access", reponse.data)
        self.assertEqual(reponse.data["utilisateur"]["username"], "admin")

    def test_mauvais_mot_de_passe_refuse(self):
        get_user_model().objects.create_superuser("admin", "a@b.ma", "motdepasse")
        reponse = self.client.post(
            reverse("login"), {"username": "admin", "password": "faux"}, format="json"
        )
        self.assertEqual(reponse.status_code, status.HTTP_401_UNAUTHORIZED)


class EquiteTest(BaseAPITest):
    """Le coeur du sujet : distinguer les servis des oublies."""

    def test_liste_des_beneficiaires(self):
        reponse = self.client.get(f"/api/activites/{self.scolaire.pk}/beneficiaires/")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data["total"], 1)
        self.assertEqual(reponse.data["resultats"][0]["matricule"], "MM0001")

    def test_liste_des_non_beneficiaires(self):
        reponse = self.client.get(f"/api/activites/{self.scolaire.pk}/non-beneficiaires/")
        self.assertEqual(reponse.data["total"], 1)
        self.assertEqual(reponse.data["resultats"][0]["matricule"], "MM0002")
        self.assertEqual(reponse.data["taux_couverture"], 50.0)

    def test_non_beneficiaires_filtres_par_annee(self):
        """En 2025 personne n'a ete servi : les deux employes remontent."""
        reponse = self.client.get(f"/api/activites/{self.scolaire.pk}/non-beneficiaires/?annee=2025")
        self.assertEqual(reponse.data["total"], 2)

    def test_non_beneficiaires_filtres_par_departement(self):
        reponse = self.client.get(
            f"/api/activites/{self.scolaire.pk}/non-beneficiaires/?departement=Finance"
        )
        self.assertEqual(reponse.data["total"], 1)

    def test_employes_sans_aucune_aide(self):
        reponse = self.client.get("/api/personnel/sans-aucune-aide/")
        self.assertEqual(reponse.data["count"], 1)
        self.assertEqual(reponse.data["results"][0]["matricule"], "MM0002")


class DoublonTest(BaseAPITest):
    """Alerte automatique en cas de double attribution."""

    def _payload(self, employe, activitee, jour):
        return {
            "matricule": employe.pk,
            "id_activitee": activitee.pk,
            "montantTR": "2500.00",
            "duree": 0,
            "date_transaction": jour,
        }

    def test_creation_refusee_si_deja_servi_la_meme_annee(self):
        reponse = self.client.post(
            "/api/transactions/", self._payload(self.servi, self.scolaire, "2024-11-02"), format="json"
        )
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("REFUS", str(reponse.data))
        self.assertIn("deja beneficie", str(reponse.data))

    def test_creation_acceptee_une_autre_annee(self):
        reponse = self.client.post(
            "/api/transactions/", self._payload(self.servi, self.scolaire, "2025-09-02"), format="json"
        )
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reponse.data["annee"], 2025)

    def test_service_unique_bloque_toute_annee(self):
        Transaction.objects.create(
            matricule=self.servi,
            id_activitee=self.mariage,
            montantTR=Decimal("8000"),
            date_transaction=date(2022, 5, 1),
            annee=2022,
        )
        reponse = self.client.post(
            "/api/transactions/",
            self._payload(self.servi, self.mariage, "2026-05-01"),
            format="json",
        )
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("une seule fois", str(reponse.data))

    def test_endpoint_de_verification_prealable(self):
        url = (
            f"/api/transactions/verifier-doublon/?matricule={self.servi.pk}"
            f"&id_activitee={self.scolaire.pk}&annee=2024"
        )
        reponse = self.client.get(url)
        self.assertTrue(reponse.data["doublon"])
        self.assertTrue(reponse.data["bloquant"])

    def test_verification_prealable_employe_jamais_servi(self):
        url = (
            f"/api/transactions/verifier-doublon/?matricule={self.oublie.pk}"
            f"&id_activitee={self.scolaire.pk}&annee=2024"
        )
        reponse = self.client.get(url)
        self.assertFalse(reponse.data["doublon"])
        self.assertIn("jamais beneficie", reponse.data["message"])


class RotationTest(BaseAPITest):
    """
    Rotation equitable (Hajj) : un employe ne peut repartir que lorsque tout le
    personnel a beneficie du meme nombre de departs.
    """

    def _partir(self, employe, annee):
        return Transaction.objects.create(
            matricule=employe,
            id_activitee=self.hajj,
            montantTR=Decimal("25000"),
            date_transaction=date(annee, 5, 1),
            annee=annee,
        )

    def _demander(self, employe, jour="2026-06-01"):
        return self.client.post(
            "/api/transactions/",
            {
                "matricule": employe.pk,
                "id_activitee": self.hajj.pk,
                "montantTR": "25000.00",
                "duree": 0,
                "date_transaction": jour,
            },
            format="json",
        )

    def test_premier_depart_autorise_pour_tous(self):
        self.assertEqual(self._demander(self.servi).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._demander(self.oublie).status_code, status.HTTP_201_CREATED)

    def test_second_depart_refuse_si_un_collegue_n_est_jamais_parti(self):
        self._partir(self.servi, 2024)
        reponse = self._demander(self.servi)
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("encore en attente", str(reponse.data))

    def test_second_depart_autorise_quand_le_tour_est_complet(self):
        self._partir(self.servi, 2024)
        self._partir(self.oublie, 2025)
        # Tout l'effectif est a 1 depart : le tour 2 s'ouvre.
        self.assertEqual(self._demander(self.servi).status_code, status.HTTP_201_CREATED)

    def test_troisieme_depart_refuse_tant_que_le_tour_2_est_incomplet(self):
        self._partir(self.servi, 2024)
        self._partir(self.oublie, 2025)
        self._partir(self.servi, 2026)  # 2e depart, legitime
        reponse = self._demander(self.servi)  # 3e : trop tot
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_une_nouvelle_recrue_rouvre_le_tour(self):
        """Cas limite : un arrivant remet le minimum a zero."""
        self._partir(self.servi, 2024)
        self._partir(self.oublie, 2025)
        Personnel.objects.create(
            matricule="MM0500",
            nom="Recrue",
            prenom="Nouvelle",
            sexe="F",
            departement="Commercial",
            date_recrutement=date(2026, 1, 5),
        )
        reponse = self._demander(self.servi)
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_etat_du_tour_expose_par_l_api(self):
        self._partir(self.servi, 2024)
        url = (
            f"/api/transactions/verifier-doublon/?matricule={self.servi.pk}"
            f"&id_activitee={self.hajj.pk}&annee=2026"
        )
        donnees = self.client.get(url).data
        self.assertTrue(donnees["bloquant"])
        self.assertEqual(donnees["regle"], "ROTATION")
        self.assertEqual(donnees["nb_attributions"], 1)
        self.assertEqual(donnees["tour"]["tour_en_cours"], 1)
        self.assertEqual(donnees["tour"]["en_attente"], 1)

    def test_tour_expose_sur_l_activite(self):
        self._partir(self.servi, 2024)
        activite = next(
            a for a in self.client.get("/api/activites/").data["results"]
            if a["id_activitee"] == self.hajj.pk
        )
        self.assertEqual(activite["regle_attribution"], "ROTATION")
        self.assertEqual(activite["tour"]["tour"], 1)
        self.assertEqual(activite["tour"]["restants"], 1)

    def test_pas_de_tour_pour_les_autres_regles(self):
        activite = next(
            a for a in self.client.get("/api/activites/").data["results"]
            if a["id_activitee"] == self.scolaire.pk
        )
        self.assertIsNone(activite["tour"])

    def test_priorisation_ecarte_celui_qui_est_en_avance(self):
        self._partir(self.servi, 2024)
        classement = {r["matricule"]: r for r in scorer_beneficiaires(self.hajj)}
        self.assertFalse(classement["MM0001"]["eligible"])
        self.assertTrue(classement["MM0002"]["eligible"])

    def test_priorisation_reeligible_au_tour_suivant(self):
        self._partir(self.servi, 2024)
        self._partir(self.oublie, 2025)
        classement = {r["matricule"]: r for r in scorer_beneficiaires(self.hajj)}
        self.assertTrue(classement["MM0001"]["eligible"])
        self.assertTrue(classement["MM0002"]["eligible"])
        self.assertIn("Tour 2", " ".join(classement["MM0001"]["justifications"]))


class CrudTest(BaseAPITest):
    def test_creation_et_suppression_personnel(self):
        reponse = self.client.post(
            "/api/personnel/",
            {
                "matricule": "MM0003",
                "nom": "Tazi",
                "prenom": "Omar",
                "departement": "Commercial",
                "date_recrutement": "2018-01-05",
                "nb_enfants": 1,
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.delete("/api/personnel/MM0003/").status_code, 204)

    def test_recherche_et_tri(self):
        reponse = self.client.get("/api/personnel/?search=Bennani")
        self.assertEqual(reponse.data["count"], 1)
        reponse = self.client.get("/api/personnel/?ordering=-nb_enfants")
        self.assertEqual(reponse.data["results"][0]["matricule"], "MM0002")

    def test_activite_utilisee_non_supprimable(self):
        reponse = self.client.delete(f"/api/activites/{self.scolaire.pk}/")
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Suppression impossible", reponse.data["detail"])

    def test_annee_deduite_de_la_date(self):
        reponse = self.client.post(
            "/api/transactions/",
            {
                "matricule": self.oublie.pk,
                "id_activitee": self.scolaire.pk,
                "montantTR": "2500.00",
                "duree": 0,
                "date_transaction": "2023-07-04",
            },
            format="json",
        )
        self.assertEqual(reponse.data["annee"], 2023)

    def test_annee_incoherente_refusee(self):
        reponse = self.client.post(
            "/api/transactions/",
            {
                "matricule": self.oublie.pk,
                "id_activitee": self.scolaire.pk,
                "montantTR": "2500.00",
                "date_transaction": "2023-07-04",
                "annee": 2020,
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)


class StatistiquesEtBudgetTest(BaseAPITest):
    def test_tableau_de_bord(self):
        reponse = self.client.get("/api/stats/")
        self.assertEqual(reponse.data["effectif"], 2)
        self.assertEqual(reponse.data["nb_beneficiaires"], 1)
        self.assertEqual(reponse.data["nb_jamais_servis"], 1)
        self.assertEqual(reponse.data["taux_couverture_global"], 50.0)
        self.assertEqual(Decimal(reponse.data["total_distribue"]), Decimal("2500.00"))

    def test_couverture_par_service(self):
        reponse = self.client.get("/api/stats/couverture/")
        couverture = {l["service"]: l["taux_couverture"] for l in reponse.data["resultats"]}
        self.assertEqual(couverture["Aide scolaire"], 50.0)
        self.assertEqual(couverture["Pelerinage Hajj"], 0.0)

    def test_alerte_budget(self):
        # 2 500 sur 10 000 = 25 % : sous le seuil par defaut, au-dessus d'un seuil a 20 %.
        ligne = next(
            l for l in self.client.get("/api/activites/budget/").data["resultats"]
            if l["service"] == "Aide scolaire"
        )
        self.assertEqual(ligne["taux_consommation"], 25.0)
        self.assertEqual(ligne["alerte"], "ok")

        ligne = next(
            l for l in self.client.get("/api/activites/budget/?seuil=20").data["resultats"]
            if l["service"] == "Aide scolaire"
        )
        self.assertEqual(ligne["alerte"], "seuil_atteint")


class ExportTest(BaseAPITest):
    def test_export_excel(self):
        reponse = self.client.get("/api/personnel/export/?format=excel")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("spreadsheetml", reponse["Content-Type"])

    def test_export_pdf(self):
        reponse = self.client.get("/api/transactions/export/?format=pdf")
        self.assertEqual(reponse["Content-Type"], "application/pdf")

    def test_attestation_individuelle(self):
        reponse = self.client.get(f"/api/transactions/{self.transaction.pk}/attestation/")
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertGreater(len(reponse.content), 1000)

    def test_rapport_annuel(self):
        reponse = self.client.get("/api/stats/rapport-annuel/?annee=2024&format=excel")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)


class IATest(BaseAPITest):
    def test_score_privilegie_celui_qui_na_jamais_ete_servi(self):
        classement = scorer_beneficiaires(self.scolaire)
        self.assertEqual(classement[0]["matricule"], "MM0002")
        self.assertTrue(classement[0]["jamais_beneficie"])
        self.assertGreater(classement[0]["score"], classement[1]["score"])

    def test_employe_deja_servi_marque_non_eligible(self):
        classement = {r["matricule"]: r for r in scorer_beneficiaires(self.scolaire, annee=2024)}
        self.assertFalse(classement["MM0001"]["eligible"])
        self.assertTrue(classement["MM0002"]["eligible"])

    def test_endpoint_recommandations(self):
        reponse = self.client.get(f"/api/ia/recommandations/?id_activitee={self.scolaire.pk}")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data["resultats"][0]["matricule"], "MM0002")

    def test_recommandations_sans_parametre(self):
        self.assertEqual(
            self.client.get("/api/ia/recommandations/").status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_clustering(self):
        resultat = clusteriser(n_clusters=2)
        self.assertEqual(len(resultat["clusters"]), 2)
        self.assertEqual(len(resultat["employes"]), 2)

    def test_chatbot_non_beneficiaires(self):
        reponse = repondre("Qui n'a pas beneficie de l'aide scolaire en 2024 ?")
        self.assertEqual(reponse["type"], "liste")
        self.assertEqual(len(reponse["donnees"]), 1)
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0002")

    def test_chatbot_beneficiaires(self):
        reponse = repondre("Qui a beneficie de l'aide scolaire ?")
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0001")

    def test_chatbot_montant(self):
        self.assertIn("2 500.00 MAD", repondre("Quel est le montant total distribue ?")["reponse"])

    def test_chatbot_question_incomprise(self):
        self.assertEqual(repondre("il fait beau aujourd'hui")["type"], "aide")

    def test_endpoint_chatbot(self):
        reponse = self.client.post("/api/ia/chatbot/", {"question": "Qui n'a jamais rien recu ?"}, format="json")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data["donnees"][0]["matricule"], "MM0002")


class ChatbotLangageTest(BaseAPITest):
    """Politesse, abreviations, fautes de frappe et entites."""

    def test_salutations(self):
        for salutation in ("bonjour", "bjr", "slt", "Salut !"):
            self.assertEqual(repondre(salutation)["type"], "message", salutation)

    def test_remerciement_et_conge(self):
        self.assertIn("plaisir", repondre("merci")["reponse"])
        self.assertIn("Bonne journee", repondre("au revoir")["reponse"])

    def test_meta_question(self):
        self.assertEqual(repondre("que peux-tu faire ?")["type"], "aide")

    def test_tolerance_aux_fautes_de_frappe(self):
        reponse = repondre("qui n'a pas beneficie de l'aide scolair ?")
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0002")

    def test_abreviations(self):
        reponse = repondre("cb a coute l'aide scolaire ?")
        self.assertIn("2 500.00 MAD", reponse["reponse"])

    def test_service_ambigu_demande_precision(self):
        """« aide » seul correspond a plusieurs services : on demande de trancher."""
        Activitee.objects.create(service="Aide au deces", montantSC=Decimal("100"))
        reponse = repondre("aide")
        self.assertEqual(reponse["type"], "aide")

    def test_recherche_par_matricule(self):
        reponse = repondre("qu'a recu MM0001 ?")
        self.assertIn("Alaoui", reponse["reponse"])
        self.assertEqual(len(reponse["donnees"]), 1)

    def test_employe_sans_aide(self):
        self.assertIn("prioritaire", repondre("qu'a recu MM0002 ?")["reponse"])

    def test_homonymes_demandent_precision(self):
        Personnel.objects.create(
            matricule="MM0009",
            nom="Alaoui",
            prenom="Nadia",
            departement="Commercial",
            date_recrutement=date(2015, 1, 1),
        )
        reponse = repondre("qu'a recu Alaoui ?")
        self.assertEqual(reponse["type"], "message")
        self.assertIn("Precisez", reponse["reponse"])

    def test_filtre_par_departement(self):
        reponse = repondre("qui n'a jamais rien recu a la finance ?")
        self.assertEqual(len(reponse["donnees"]), 1)
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0002")


class ChatbotContexteTest(BaseAPITest):
    """Le fil de la conversation : questions elliptiques."""

    def _echange(self, question, contexte):
        reponse = repondre(question, contexte=contexte)
        return reponse, reponse["contexte"]

    def test_le_service_est_memorise(self):
        _, contexte = self._echange("Qui a beneficie de l'aide scolaire ?", {})
        self.assertEqual(contexte["service"], "Aide scolaire")

    def test_question_elliptique_rejoue_l_intention(self):
        """« et en 2025 ? » doit relancer la meme requete sur la nouvelle annee."""
        _, contexte = self._echange("Qui a beneficie de l'aide scolaire ?", {})
        reponse, contexte = self._echange("et en 2025 ?", contexte)
        self.assertIn("Aide scolaire", reponse["reponse"])
        self.assertIn("2025", reponse["reponse"])
        self.assertEqual(contexte["annee"], 2025)

    def test_suite_de_la_conversation_sur_le_meme_service(self):
        _, contexte = self._echange("Qui a beneficie de l'aide scolaire ?", {})
        reponse, contexte = self._echange("qui n'en a pas beneficie ?", contexte)
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0002")
        reponse, contexte = self._echange("les prioritaires ?", contexte)
        self.assertIn("prioritaires", reponse["reponse"])

    def test_portee_globale_ignore_le_service_du_contexte(self):
        """« qui n'a jamais rien recu ? » porte sur toutes les aides."""
        _, contexte = self._echange("Qui a beneficie du Hajj ?", {})
        reponse, _ = self._echange("qui n'a jamais rien recu ?", contexte)
        self.assertIn("aucune action sociale", reponse["reponse"])
        self.assertNotIn("Hajj", reponse["reponse"])

    def test_question_vague_ne_rejoue_pas_une_requete_au_hasard(self):
        """« le seul ? » n'a pas de sens : on rappelle le sujet, on n'invente pas."""
        _, contexte = self._echange("Qui a beneficie du Hajj ?", {})
        reponse, _ = self._echange("le seul ?", contexte)
        self.assertEqual(reponse["type"], "aide")
        self.assertIn("Pelerinage Hajj", reponse["reponse"])
        self.assertEqual(reponse["donnees"], [])

    def test_contexte_transporte_par_l_api(self):
        premiere = self.client.post(
            "/api/ia/chatbot/", {"question": "Qui a beneficie de l'aide scolaire ?"}, format="json"
        )
        seconde = self.client.post(
            "/api/ia/chatbot/",
            {"question": "et en 2025 ?", "contexte": premiere.data["contexte"]},
            format="json",
        )
        self.assertEqual(seconde.status_code, status.HTTP_200_OK)
        self.assertIn("Aide scolaire", seconde.data["reponse"])

    def test_contexte_invalide_ignore(self):
        reponse = self.client.post(
            "/api/ia/chatbot/", {"question": "bonjour", "contexte": "n'importe quoi"}, format="json"
        )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)


class ChatbotIntentionsTest(BaseAPITest):
    """Les intentions ajoutees : classement, couverture, catalogue, effectif."""

    def test_classement_des_services(self):
        reponse = repondre("quel service coute le plus cher ?")
        self.assertIn("Aide scolaire", reponse["reponse"])
        self.assertEqual(len(reponse["donnees"]), Activitee.objects.count())

    def test_classement_inverse(self):
        self.assertIn("le moins dote", repondre("quel service est le moins distribue ?")["reponse"])

    def test_taux_de_couverture(self):
        reponse = repondre("quel est le taux de couverture de l'aide scolaire ?")
        self.assertIn("50.0 %", reponse["reponse"])

    def test_catalogue_des_services(self):
        reponse = repondre("quels services existent ?")
        self.assertEqual(len(reponse["donnees"]), Activitee.objects.count())
        self.assertIn("regle", reponse["colonnes"])

    def test_effectif(self):
        self.assertIn("2 employe(s)", repondre("combien d'employes avons-nous ?")["reponse"])

    def test_budget_signale_les_depassements(self):
        reponse = repondre("quel est l'etat du budget ?")
        self.assertEqual(len(reponse["donnees"]), Activitee.objects.count())
        self.assertEqual(reponse["colonnes"][0], "service")

    def test_montant_formate_avec_separateur(self):
        """Le separateur de milliers ne doit pas manger les virgules de la phrase."""
        reponse = repondre("quel service coute le plus cher ?")
        self.assertIn(", 1 beneficiaires", reponse["reponse"])


class ChatbotRobustesseTest(BaseAPITest):
    """Saisies approximatives et criteres absents du modele de donnees."""

    def test_mot_colle_au_service(self):
        """« dehajj » : la preposition collee au nom du service."""
        reponse = repondre("qui a beneficie dehajj ?")
        self.assertIn("Pelerinage Hajj", reponse["reponse"])

    def test_un_seul_mot_discriminant_suffit(self):
        self.assertIn("Pelerinage Hajj", repondre("les beneficiaires du hajj")["reponse"])

    def test_faute_sur_le_verbe(self):
        """« benificier » doit etre reconnu comme « beneficier »."""
        reponse = repondre("qui sont les benificiers du hajj ?")
        self.assertIn("Pelerinage Hajj", reponse["reponse"])
        self.assertEqual(reponse["type"], "liste")

    def test_annee_malformee_corrigee_et_signalee(self):
        """« 20025 » -> 2025 seulement si une seule annee de la base en decoule."""
        Transaction.objects.create(
            matricule=self.oublie,
            id_activitee=self.scolaire,
            montantTR=Decimal("2500"),
            date_transaction=date(2025, 9, 1),
            annee=2025,
        )
        reponse = repondre("combien a-t-on distribue en 20025 ?")
        self.assertIn("interprete l'annee saisie comme 2025", reponse["reponse"])
        self.assertIn("en 2025", reponse["reponse"])

    def test_annee_malformee_non_devinable(self):
        """Aucune annee plausible en base : on ne devine pas."""
        reponse = repondre("qui a beneficie en 19999 ?")
        self.assertNotIn("interprete l'annee", reponse["reponse"])

    def test_criteres_absents_divers(self):
        for question, attendu in (
            ("quel est le salaire moyen ?", "le salaire"),
            ("qui a plus de 40 ans ?", "l'age"),
            ("combien d'employes sont maries ?", "la situation familiale"),
        ):
            self.assertIn(attendu, repondre(question)["reponse"], question)

    def test_anciennete_nest_pas_signalee_comme_absente(self):
        """« 10 ans d'anciennete » est calculable : aucun avertissement."""
        reponse = repondre("qui a plus de 10 ans d'anciennete ?")
        self.assertNotIn("ne contient pas", reponse["reponse"])

    def test_question_complete_de_l_utilisateur(self):
        """La question exacte qui echouait : fautes + mot colle + annee + sexe."""
        Transaction.objects.create(
            matricule=self.servi,
            id_activitee=self.hajj,
            montantTR=Decimal("25000"),
            date_transaction=date(2025, 6, 1),
            annee=2025,
        )
        reponse = repondre("qui sont les hommes benificier dehajj en 20025?")
        self.assertEqual(reponse["type"], "liste")
        self.assertIn("Pelerinage Hajj", reponse["reponse"])
        self.assertIn("2025", reponse["reponse"])
        self.assertIn("(hommes)", reponse["reponse"])
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0001")


class SexeTest(BaseAPITest):
    """Le champ sexe : modele, API, filtres, statistiques et chatbot."""

    def test_libelle_et_valeur_vide(self):
        self.assertEqual(self.servi.sexe_libelle, "Homme")
        anonyme = Personnel.objects.create(
            matricule="MM0100",
            nom="Tazi",
            prenom="Inconnu",
            departement="Commercial",
            date_recrutement=date(2020, 1, 1),
        )
        self.assertEqual(anonyme.sexe_libelle, "Non renseigne")

    def test_filtre_api(self):
        self.assertEqual(self.client.get("/api/personnel/?sexe=H").data["count"], 1)
        self.assertEqual(
            self.client.get("/api/personnel/?sexe=F").data["results"][0]["matricule"], "MM0002"
        )

    def test_tri_par_sexe(self):
        reponse = self.client.get("/api/personnel/?ordering=sexe")
        self.assertEqual(reponse.data["results"][0]["sexe"], "F")

    def test_filtre_sur_les_transactions(self):
        self.assertEqual(self.client.get("/api/transactions/?sexe=H").data["count"], 1)
        self.assertEqual(self.client.get("/api/transactions/?sexe=F").data["count"], 0)

    def test_creation_avec_sexe(self):
        reponse = self.client.post(
            "/api/personnel/",
            {
                "matricule": "MM0200",
                "nom": "Berrada",
                "prenom": "Nadia",
                "sexe": "F",
                "departement": "Juridique",
                "date_recrutement": "2019-04-01",
                "nb_enfants": 2,
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reponse.data["sexe_libelle"], "Femme")

    def test_sexe_invalide_refuse(self):
        reponse = self.client.post(
            "/api/personnel/",
            {
                "matricule": "MM0201",
                "nom": "X",
                "prenom": "Y",
                "sexe": "Z",
                "departement": "Juridique",
                "date_recrutement": "2019-04-01",
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_statistiques_par_sexe(self):
        lignes = {l["sexe"]: l for l in self.client.get("/api/stats/").data["par_sexe"]}
        self.assertEqual(lignes["H"]["effectif"], 1)
        self.assertEqual(lignes["H"]["nb_beneficiaires"], 1)
        self.assertEqual(lignes["H"]["taux_couverture"], 100.0)
        self.assertEqual(lignes["F"]["nb_beneficiaires"], 0)
        self.assertEqual(lignes["F"]["libelle"], "Femme")

    def test_chatbot_filtre_les_hommes(self):
        reponse = repondre("qui sont les hommes beneficiaires de l'aide scolaire ?")
        self.assertIn("(hommes)", reponse["reponse"])
        self.assertEqual(len(reponse["donnees"]), 1)
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0001")

    def test_chatbot_filtre_les_femmes(self):
        reponse = repondre("les femmes qui n'ont jamais rien recu")
        self.assertIn("(femmes)", reponse["reponse"])
        self.assertEqual(reponse["donnees"][0]["matricule"], "MM0002")

    def test_chatbot_sexe_memorise_dans_le_contexte(self):
        premiere = repondre("qui sont les hommes beneficiaires de l'aide scolaire ?")
        self.assertEqual(premiere["contexte"]["sexe"], "H")
        seconde = repondre("combien ?", contexte=premiere["contexte"])
        self.assertIn("hommes", seconde["reponse"])

    def test_export_contient_la_colonne_sexe(self):
        reponse = self.client.get("/api/personnel/export/?format=excel")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)


@override_settings(LLM_ACTIF=True, GROQ_API_KEY="cle-de-test", GROQ_MODELE="modele-test")
class LLMTest(BaseAPITest):
    """
    Renfort LLM. L'appel reseau est toujours simule : la suite de tests reste
    hors ligne, deterministe, et ne consomme aucun quota.
    """

    def test_validation_ecarte_un_service_invente(self):
        """Garde-fou central : ce qui n'existe pas en base est ignore."""
        plan = llm._valider(
            {"intention": "beneficiaires", "service": "Aide au logement lunaire", "confiance": 0.9}
        )
        self.assertIsNone(plan["service"])
        self.assertEqual(plan["intention"], "beneficiaires")

    def test_validation_accepte_un_service_existant(self):
        plan = llm._valider({"intention": "montant", "service": "aide scolaire"})
        self.assertEqual(plan["service"], self.scolaire)

    def test_validation_ecarte_les_valeurs_aberrantes(self):
        plan = llm._valider(
            {
                "intention": "n_importe_quoi",
                "annee": 20025,
                "sexe": "X",
                "departement": "Service des licornes",
                "confiance": 42,
            }
        )
        self.assertIsNone(plan["intention"])
        self.assertIsNone(plan["annee"])
        self.assertIsNone(plan["sexe"])
        self.assertIsNone(plan["departement"])
        self.assertEqual(plan["confiance"], 1.0)

    def test_validation_resiste_a_une_reponse_non_conforme(self):
        for brut in (None, [], "texte", {}):
            self.assertIsNone(llm._valider(brut)["intention"])

    def test_le_llm_corrige_une_intention_mal_deduite(self):
        """« ceux qui meritent X » : les regles disent beneficiaires, le LLM priorisation."""
        plan = {
            "intention": "priorisation", "service": self.scolaire, "annee": None,
            "departement": None, "sexe": None, "employe": None, "confiance": 0.9,
        }
        with patch.object(llm, "analyser", return_value=plan):
            reponse = repondre("montre moi ceux qui meritent l'aide scolaire")
        self.assertIn("prioritaires", reponse["reponse"])
        self.assertEqual(reponse["moteur"], "llm")

    def test_le_llm_ne_supplante_pas_une_intention_certaine(self):
        """Un mot-clef explicite dans la question prime sur l'avis du modele."""
        plan = {
            "intention": "budget", "service": None, "annee": None, "departement": None,
            "sexe": None, "employe": None, "confiance": 1.0,
        }
        with patch.object(llm, "analyser", return_value=plan):
            reponse = repondre("qui n'a pas beneficie de l'aide scolaire ?")
        self.assertIn("n'ont pas beneficie", reponse["reponse"])

    def test_repli_silencieux_si_le_llm_echoue(self):
        with patch.object(llm, "analyser", return_value=None):
            reponse = repondre("qui a beneficie de l'aide scolaire ?")
        self.assertEqual(reponse["moteur"], "regles")
        self.assertEqual(reponse["type"], "liste")

    def test_repli_silencieux_si_le_reseau_tombe(self):
        with patch.object(llm, "_appeler_groq", side_effect=OSError("reseau coupe")):
            self.assertIsNone(llm.analyser("peu importe"))

    def test_erreur_http_ne_remonte_pas(self):
        import urllib.error

        erreur = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
        with patch("urllib.request.urlopen", side_effect=erreur):
            self.assertIsNone(llm.analyser("peu importe"))

    def test_llm_desactivable(self):
        with override_settings(LLM_ACTIF=False):
            self.assertFalse(llm.disponible())
            self.assertIsNone(llm.analyser("peu importe"))

    def test_aucun_appel_quand_utiliser_llm_est_faux(self):
        with patch.object(llm, "analyser") as espion:
            repondre("qui a beneficie de l'aide scolaire ?", utiliser_llm=False)
        espion.assert_not_called()

    def test_aucune_donnee_nominative_envoyee(self):
        """Le prompt ne doit contenir que des libelles, jamais un nom d'employe."""
        captures = {}

        class FausseReponse:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *args):
                return False

            def read(self_inner):
                return b'{"choices":[{"message":{"content":"{\\"intention\\":\\"aide\\"}"}}]}'

        def faux_urlopen(requete, timeout=None):
            captures["corps"] = requete.data.decode("utf-8")
            return FausseReponse()

        with patch("urllib.request.urlopen", side_effect=faux_urlopen):
            llm.analyser("qui a beneficie du hajj ?")

        envoye = captures["corps"]
        self.assertIn("Aide scolaire", envoye)  # les libelles de services, oui
        self.assertNotIn(self.servi.nom, envoye)  # les noms d'employes, non
        self.assertNotIn(self.servi.matricule, envoye)

    def test_endpoint_expose_l_etat_du_moteur(self):
        reponse = self.client.get("/api/ia/chatbot/")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertTrue(reponse.data["llm_actif"])
        self.assertEqual(reponse.data["modele"], "modele-test")

    def test_la_reponse_indique_le_moteur(self):
        with patch.object(llm, "analyser", return_value=None):
            reponse = self.client.post(
                "/api/ia/chatbot/", {"question": "bonjour"}, format="json"
            )
        self.assertEqual(reponse.data["moteur"], "regles")
