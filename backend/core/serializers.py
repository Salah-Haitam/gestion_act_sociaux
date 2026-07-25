"""Serializers DRF."""

from decimal import Decimal

from rest_framework import serializers

from .models import Activitee, Personnel, Transaction


class ActiviteeSerializer(serializers.ModelSerializer):
    montant_consomme = serializers.SerializerMethodField()
    budget_restant = serializers.SerializerMethodField()
    taux_consommation = serializers.SerializerMethodField()
    nb_beneficiaires = serializers.SerializerMethodField()

    class Meta:
        model = Activitee
        fields = [
            "id_activitee",
            "service",
            "montantSC",
            "budget_alloue",
            "description",
            "unique_par_employe",
            "montant_consomme",
            "budget_restant",
            "taux_consommation",
            "nb_beneficiaires",
        ]

    def _consomme(self, obj):
        # Valeur pre-calculee par l'annotation du ViewSet quand elle existe.
        valeur = getattr(obj, "consomme", None)
        if valeur is None:
            valeur = sum((t.montantTR for t in obj.transactions.all()), Decimal("0"))
        return Decimal(valeur or 0)

    def get_montant_consomme(self, obj):
        return self._consomme(obj)

    def get_budget_restant(self, obj):
        return (obj.budget_alloue or Decimal("0")) - self._consomme(obj)

    def get_taux_consommation(self, obj):
        budget = obj.budget_alloue or Decimal("0")
        if budget <= 0:
            return None
        return round(float(self._consomme(obj) / budget) * 100, 2)

    def get_nb_beneficiaires(self, obj):
        valeur = getattr(obj, "beneficiaires", None)
        if valeur is None:
            valeur = obj.transactions.values("matricule").distinct().count()
        return valeur


class PersonnelSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    sexe_libelle = serializers.CharField(read_only=True)
    anciennete = serializers.IntegerField(read_only=True)
    nb_transactions = serializers.SerializerMethodField()
    total_percu = serializers.SerializerMethodField()
    services_beneficies = serializers.SerializerMethodField()

    class Meta:
        model = Personnel
        fields = [
            "matricule",
            "nom",
            "prenom",
            "nom_complet",
            "sexe",
            "sexe_libelle",
            "departement",
            "date_recrutement",
            "nb_enfants",
            "anciennete",
            "nb_transactions",
            "total_percu",
            "services_beneficies",
        ]

    def get_nb_transactions(self, obj):
        valeur = getattr(obj, "nb_tr", None)
        return obj.transactions.count() if valeur is None else valeur

    def get_total_percu(self, obj):
        valeur = getattr(obj, "total_tr", None)
        if valeur is None:
            valeur = sum((t.montantTR for t in obj.transactions.all()), Decimal("0"))
        return Decimal(valeur or 0)

    def get_services_beneficies(self, obj):
        """Liste distincte des services dont l'employe a deja beneficie."""
        return sorted(
            {t.id_activitee.service for t in obj.transactions.all()}
        )


class TransactionSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source="matricule.nom", read_only=True)
    prenom = serializers.CharField(source="matricule.prenom", read_only=True)
    departement = serializers.CharField(source="matricule.departement", read_only=True)
    service = serializers.CharField(source="id_activitee.service", read_only=True)
    montantSC = serializers.DecimalField(
        source="id_activitee.montantSC", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            "id_transaction",
            "matricule",
            "nom",
            "prenom",
            "departement",
            "id_activitee",
            "service",
            "montantSC",
            "montantTR",
            "duree",
            "date_transaction",
            "annee",
        ]
        extra_kwargs = {"annee": {"required": False}}

    def validate(self, attrs):
        """Regles metier : coherence de l'annee + alerte doublon."""
        instance = self.instance
        personnel = attrs.get("matricule") or getattr(instance, "matricule", None)
        activitee = attrs.get("id_activitee") or getattr(instance, "id_activitee", None)
        date_tr = attrs.get("date_transaction") or getattr(instance, "date_transaction", None)
        annee = attrs.get("annee") or (date_tr.year if date_tr else None)

        if date_tr and annee and annee != date_tr.year:
            raise serializers.ValidationError(
                {"annee": f"L'annee ({annee}) ne correspond pas a la date ({date_tr.year})."}
            )
        if annee:
            attrs["annee"] = annee

        # Doublon : l'employe a-t-il deja beneficie de ce service ?
        if personnel and activitee:
            doublons = Transaction.objects.filter(matricule=personnel, id_activitee=activitee)
            if instance is not None:
                doublons = doublons.exclude(pk=instance.pk)
            if activitee.unique_par_employe:
                existante = doublons.first()
                if existante:
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                f"DOUBLON : {personnel.nom} {personnel.prenom} a deja beneficie "
                                f"du service « {activitee.service} » en {existante.annee} "
                                f"(non renouvelable)."
                            ]
                        }
                    )
            elif annee:
                existante = doublons.filter(annee=annee).first()
                if existante:
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                f"DOUBLON : {personnel.nom} {personnel.prenom} a deja beneficie "
                                f"du service « {activitee.service} » en {annee} "
                                f"(transaction #{existante.id_transaction})."
                            ]
                        }
                    )
        return attrs


class UtilisateurSerializer(serializers.Serializer):
    """Profil de l'administrateur connecte."""

    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_superuser = serializers.BooleanField()
