"""Modele de donnees : personnel, activitee, transaction."""

from datetime import date

from django.core.validators import MinValueValidator
from django.db import models


class Personnel(models.Model):
    """Un employe de Marsa Maroc, identifie par son matricule."""

    SEXE_CHOIX = [("H", "Homme"), ("F", "Femme")]

    matricule = models.CharField("Matricule", max_length=20, primary_key=True)
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prenom", max_length=100)
    # Facultatif : les dossiers anciens peuvent ne pas le renseigner.
    sexe = models.CharField(
        "Sexe", max_length=1, choices=SEXE_CHOIX, blank=True, default="", db_index=True
    )
    departement = models.CharField("Departement", max_length=100, db_index=True)
    date_recrutement = models.DateField("Date de recrutement")
    nb_enfants = models.PositiveSmallIntegerField("Nombre d'enfants", default=0)

    class Meta:
        db_table = "personnel"
        verbose_name = "Personnel"
        verbose_name_plural = "Personnel"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom}"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"

    @property
    def sexe_libelle(self):
        return self.get_sexe_display() if self.sexe else "Non renseigne"

    @property
    def anciennete(self):
        """Anciennete en annees revolues."""
        today = date.today()
        delta = today.year - self.date_recrutement.year
        if (today.month, today.day) < (self.date_recrutement.month, self.date_recrutement.day):
            delta -= 1
        return max(delta, 0)


class Activitee(models.Model):
    """
    Une action sociale proposee par l'entreprise (aide scolaire, mariage, Hajj...).

    Trois regles d'attribution sont possibles, cf. `regle_attribution`.
    """

    ANNUELLE = "ANNUELLE"
    UNIQUE = "UNIQUE"
    ROTATION = "ROTATION"
    REGLES = [
        (ANNUELLE, "Renouvelable chaque annee"),
        (UNIQUE, "Une seule fois par employe"),
        (ROTATION, "Rotation equitable : un nouveau tour quand tout le monde a ete servi"),
    ]

    id_activitee = models.AutoField(primary_key=True)
    service = models.CharField("Service", max_length=150, unique=True)
    montantSC = models.DecimalField(
        "Montant standard",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    budget_alloue = models.DecimalField(
        "Budget alloue",
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField("Description", blank=True, default="")
    # ANNUELLE : une fois par an et par employe (aide scolaire, colonie).
    # UNIQUE   : une seule fois dans la carriere (mariage, pret logement).
    # ROTATION : une seule fois par TOUR. Un employe ne peut repartir que
    #            lorsque tout le personnel a ete servi autant de fois que lui
    #            (Hajj : personne ne repart tant qu'un collegue n'est jamais parti).
    regle_attribution = models.CharField(
        "Regle d'attribution", max_length=10, choices=REGLES, default=ANNUELLE
    )

    class Meta:
        db_table = "activitee"
        verbose_name = "Activite"
        verbose_name_plural = "Activites"
        ordering = ["service"]

    def __str__(self):
        return self.service

    @property
    def renouvelable_chaque_annee(self):
        return self.regle_attribution == self.ANNUELLE

    def attributions_par_employe(self):
        """Nombre de fois que chaque employe a beneficie de ce service."""
        return Personnel.objects.annotate(
            nb=models.Count(
                "transactions", filter=models.Q(transactions__id_activitee=self), distinct=True
            )
        )

    def tour_en_cours(self):
        """
        Etat du tour de rotation.

        `minimum` est le plus petit nombre d'attributions observe sur
        l'effectif : c'est le seuil qu'un employe ne doit pas depasser pour
        rester eligible. `restants` compte ceux qui sont encore a ce seuil.
        """
        agregat = self.attributions_par_employe().aggregate(
            minimum=models.Min("nb"), effectif=models.Count("matricule")
        )
        minimum = agregat["minimum"] or 0
        restants = self.attributions_par_employe().filter(nb=minimum).count()
        return {
            "minimum": minimum,
            "tour": minimum + 1,  # tour en cours, lisible par un humain
            "restants": restants,
            "effectif": agregat["effectif"] or 0,
        }

    def attributions_de(self, personnel) -> int:
        return self.transactions.filter(matricule=personnel).count()


class Transaction(models.Model):
    """Le lien : un employe a beneficie d'une activite, pour un montant et une annee."""

    id_transaction = models.AutoField(primary_key=True)
    matricule = models.ForeignKey(
        Personnel,
        on_delete=models.CASCADE,
        db_column="matricule",
        related_name="transactions",
        verbose_name="Employe",
    )
    id_activitee = models.ForeignKey(
        Activitee,
        on_delete=models.PROTECT,
        db_column="id_activitee",
        related_name="transactions",
        verbose_name="Activite",
    )
    montantTR = models.DecimalField(
        "Montant verse",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    duree = models.PositiveSmallIntegerField(
        "Duree (jours)", default=0, help_text="Duree en jours, 0 si non applicable"
    )
    date_transaction = models.DateField("Date de la transaction")
    annee = models.PositiveSmallIntegerField("Annee", db_index=True)

    class Meta:
        db_table = "transaction"
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ["-date_transaction", "-id_transaction"]
        indexes = [
            models.Index(fields=["matricule", "id_activitee"]),
            models.Index(fields=["id_activitee", "annee"]),
        ]

    def __str__(self):
        return f"#{self.id_transaction} {self.matricule_id} / {self.id_activitee_id} ({self.annee})"

    def clean(self):
        """
        Validation metier au niveau du modele.

        Placee ici, elle s'applique a TOUT formulaire Django, l'admin compris.
        Le serializer DRF appelle les memes fonctions de `core.regles` : la
        regle est donc unique, mais verifiee sur les deux chemins d'ecriture.
        """
        from django.core.exceptions import ValidationError

        from .regles import controler_attribution

        if self.date_transaction and not self.annee:
            self.annee = self.date_transaction.year
        if self.date_transaction and self.annee and self.annee != self.date_transaction.year:
            raise ValidationError(
                {"annee": f"L'annee ({self.annee}) ne correspond pas a la date "
                          f"({self.date_transaction.year})."}
            )

        if self.matricule_id and self.id_activitee_id:
            message = controler_attribution(
                self.matricule, self.id_activitee, self.annee, exclure=self.pk
            )
            if message:
                raise ValidationError(message)

    def save(self, *args, **kwargs):
        # L'annee reste toujours coherente avec la date de la transaction.
        if self.date_transaction and not self.annee:
            self.annee = self.date_transaction.year
        super().save(*args, **kwargs)
