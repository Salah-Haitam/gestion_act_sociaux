# Plateforme de Gestion des Actions Sociales — Marsa Maroc

Projet PFA — application web permettant à l'administrateur RH de gérer et suivre les actions
sociales attribuées au personnel de Marsa Maroc.

**Objectif central : garantir l'équité de distribution** en identifiant qui a déjà bénéficié d'un
service et surtout **qui ne l'a jamais reçu**, afin de ne rater aucune opportunité pour les employés
non servis.

---

## Stack technique

| Couche | Technologie |
|---|---|
| Back-end | Django 5.2 + Django REST Framework |
| Front-end | React 19 + Vite + React Router + Recharts |
| Base de données | SQLite |
| Authentification | JWT (`djangorestframework-simplejwt`) + session Django |
| IA | scikit-learn (K-Means), moteur de score et assistant NL maison |
| Exports | openpyxl (Excel) et reportlab (PDF) |

---

## Démarrage rapide

### 1. Back-end

```bash
cd backend
../venv/Scripts/python.exe manage.py migrate     # Windows
# source ../venv/bin/activate && python manage.py migrate   # Linux/macOS

python manage.py seed        # jeu de démonstration (60 employés, 8 services, ~145 transactions)
python manage.py runserver   # http://localhost:8000
```

Pour recréer l'environnement à partir de zéro :

```bash
python -m venv venv
venv/Scripts/pip install -r backend/requirements.txt
```

### 2. Front-end

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

### 3. Connexion

| Identifiant | Mot de passe |
|---|---|
| `admin` | `admin123` |

Le compte est créé par `manage.py seed`. L'admin Django reste disponible sur
<http://localhost:8000/admin/>.

---

## Modèle de données

```
personnel (1) ──< transaction >── (1) activitee
```

**`personnel`** — `matricule` (PK), `nom`, `prenom`, `sexe`, `departement`, `date_recrutement`,
`nb_enfants`

**`activitee`** — `id_activitee` (PK), `service`, `montantSC`, `budget_alloue`, `description`,
`regle_attribution`

**`transaction`** — `id_transaction` (PK), `matricule` (FK), `id_activitee` (FK), `montantTR`,
`duree`, `date_transaction`, `annee`

La table `transaction` est le cœur du système : elle relie un employé à une activité dont il a
bénéficié.

**Trois champs ont été ajoutés au modèle de l'énoncé**, à mentionner en soutenance :

| Champ | Table | Pourquoi |
|---|---|---|
| `budget_alloue` | `activitee` | Sans enveloppe par service, la gestion budgétaire et ses alertes sont impossibles. |
| `regle_attribution` | `activitee` | Trois comportements possibles (annuelle, unique, rotation équitable). Toute la règle anti-doublon en dépend. Voir ci-dessous. |
| `sexe` | `personnel` | Permet de filtrer et surtout de **mesurer l'équité hommes / femmes** de la distribution. Facultatif : les dossiers anciens restent « non renseigné ». |

Le champ `sexe` est arrivé après coup : la migration `0003_remplir_sexe` le renseigne pour les
dossiers déjà en base en le déduisant du prénom, et **laisse vide** tout prénom non reconnu plutôt
que d'inventer une valeur.

---

## Fonctionnalités

### Authentification
Connexion JWT réservée à l'administrateur, rafraîchissement automatique du jeton, déconnexion.
Toutes les routes de l'API exigent une session valide (`401` sinon).

### Visualisation globale
- Liste de tout le personnel avec, pour chacun, les services dont il a bénéficié et le total perçu.
- Registre complet des transactions (qui, quel service, quel montant, quelle année).
- Fiche employé détaillant son historique.

### Éviter les doublons et repérer les oubliés — *le point clé du sujet*
- Pour un service donné : liste des employés **déjà bénéficiaires** et liste de ceux qui **ne l'ont
  jamais été** (`LEFT JOIN transaction … WHERE transaction IS NULL`, exprimé via l'ORM dans
  [`views.py`](backend/core/views.py)).
- Filtrage par année et par département.
- **Alerte automatique de doublon** à deux niveaux : contrôle préalable en direct dans le formulaire
  (`GET /api/transactions/verifier-doublon/`) et refus côté serveur à l'enregistrement. Les deux
  s'appuient sur le **même module** [`regles.py`](backend/core/regles.py), ils ne peuvent donc pas
  diverger — et le front ne peut pas être contourné.
- Liste des employés n'ayant **jamais rien reçu**, tous services confondus.

### Les trois règles d'attribution
Chaque activité porte une `regle_attribution` qui détermine quand un employé y a droit.

| Règle | Condition | Exemples |
|---|---|---|
| `ANNUELLE` | Une fois par an et par employé | Aide scolaire, colonie de vacances, prime de naissance |
| `UNIQUE` | Une seule fois dans la carrière | Aide au mariage, prêt logement |
| `ROTATION` | **Une fois par tour** — un employé n'est éligible que s'il compte le *minimum* d'attributions de l'effectif | Pèlerinage Hajj |

La règle **`ROTATION`** traduit une exigence d'équité concrète : *personne ne repart tant qu'un
collègue n'est jamais parti*. Quand tout le personnel a été servi une fois, un deuxième tour s'ouvre
et chacun redevient éligible. Formellement, l'attribution est autorisée si et seulement si

```
attributions(employé) == min( attributions(e) pour tout e du personnel )
```

Cette formulation gère tous les tours sans cas particulier. Elle a deux conséquences à connaître :

- L'arrivée d'un nouvel employé **remet le minimum à zéro** et referme le tour en cours — ce qui est
  le comportement voulu : le nouvel arrivant passe avant un second départ.
- Sur un effectif réel, le premier tour n'est jamais complet ; en pratique la règle équivaut donc à
  « une fois par carrière », le second tour restant théorique. C'est voulu : la règle est *juste*
  plutôt que restrictive.

L'interface affiche en permanence le tour en cours et le nombre d'employés encore en attente.

### Gestion CRUD
Ajout / modification / suppression du personnel, des activités et des transactions. Une activité
rattachée à des transactions ne peut pas être supprimée (message explicite, pas d'erreur 500).

### Recherche, filtres et tri
Recherche plein texte (nom, prénom, matricule, service), filtres par service, département, **sexe**,
année, plage de montants et de dates, tri sur toutes les colonnes, pagination.

### Gestion budgétaire
Budget alloué par activité, suivi consommé / restant, taux de consommation et **alerte lorsque le
seuil est approché** (80 % par défaut, ajustable dans l'interface). Statuts : *sous contrôle*,
*seuil atteint*, *dépassement*.

### Statistiques
Montant total distribué par service et par année, nombre de bénéficiaires par service, taux de
couverture par service, par département et **par sexe**, montant moyen par bénéficiaire, graphiques
d'évolution des dépenses.

Le tableau *Équité hommes / femmes* est directement dans le thème du sujet : sur le jeu de
démonstration, les femmes affichent 60,9 % de couverture contre 73,0 % pour les hommes — un écart
concret à commenter en soutenance.

### Exports
Excel et PDF pour le personnel, les transactions, les activités, la liste des non-bénéficiaires, la
priorisation IA et l'état récapitulatif annuel. **Attestation individuelle** en PDF pour chaque
transaction.

---

## Partie IA

### 1. Priorisation des bénéficiaires (`core/ai.py` → `scorer_beneficiaires`)
Chaque employé reçoit un **score d'équité sur 100** pour un service donné, combinant cinq critères
pondérés :

| Critère | Poids (service standard) |
|---|---|
| N'a jamais bénéficié de ce service | 40 % |
| A reçu peu d'aides toutes catégories confondues | 20 % |
| A perçu un faible montant cumulé | 12 % |
| Ancienneté | 16 % |
| Charge familiale (nombre d'enfants) | 12 % |

La pondération **s'adapte à la nature du service** : une aide scolaire ou une prime de naissance
pèse davantage le nombre d'enfants (30 %), un pèlerinage ou une aide au mariage pèse l'ancienneté
(25 %) et le fait de n'avoir jamais été servi (45 %). Les valeurs continues sont normalisées min-max
sur l'effectif. Les employés déjà servis sont marqués non éligibles et fortement pénalisés. Chaque
ligne du classement est accompagnée de sa **justification en clair**, ce qui rend la recommandation
défendable devant un jury et devant les employés.

### 2. Assistant admin en langage naturel (`core/ai.py` → `repondre`)
Moteur à base de règles, **sans dépendance externe ni clé d'API**. Il procède en quatre temps :

1. **Normalisation** — minuscules, suppression des accents et de la ponctuation, développement des
   abréviations du langage courant (`bjr`, `slt`, `cb`, `jms`, `ki`, `dpt`…). L'admin n'a donc pas
   besoin de taper les accents ni d'écrire en français soutenu.
2. **Extraction des entités** — service, année, département et employé. La reconnaissance du service
   tolère les fautes de frappe (`aide scolair`, `pelerinag`) via une comparaison par similarité, et
   s'appuie sur les services **réellement présents en base** : créer une nouvelle activité la rend
   immédiatement reconnaissable, rien n'est codé en dur. En cas d'ambiguïté (« aide » seul) ou
   d'homonymes, l'assistant demande de préciser au lieu de deviner.
3. **Détection de l'intention** — `_detecter_intention()` traduit la question en une intention nommée
   (`non_beneficiaires`, `jamais_rien`, `priorisation`, `classement`, `couverture`, `budget`,
   `montant`, `effectif`, `services`, `beneficiaires`, `employe`).
4. **Exécution** — la requête ORM correspondante, renvoyée sous forme structurée
   `{reponse, type, colonnes, donnees, contexte}` que le front affiche en tableau exploitable.

**Mémoire de conversation.** Chaque réponse renvoie un `contexte` (service, année, département,
intention) que le client reposte au tour suivant — l'API reste donc **sans état**. Cela permet les
questions elliptiques :

```
> Qui a bénéficié du Hajj ?          → 5 bénéficiaires
> Et en 2025 ?                       → rejoue la même requête sur 2025
> Les prioritaires ?                 → priorisation IA pour le Hajj
> Qui n'en a pas bénéficié ?         → les 55 oubliés
```

**Robustesse.** Les mots collés (`dehajj`), les fautes sur le verbe (`benificier`) et les années
malformées (`20025`) sont rattrapés. Une saisie d'année approximative n'est corrigée que si la
suppression d'un chiffre mène à **une seule** année réellement présente en base, et la correction
est alors annoncée dans la réponse.

**Trois garde-fous — l'assistant ne devine jamais :**

1. Une question de portée globale (« qui n'a jamais **rien** reçu ? ») n'hérite jamais du service
   en cours.
2. Une question vague (« le seul ? ») ne rejoue pas une requête au hasard : l'assistant rappelle le
   sujet courant et propose les suites possibles.
3. **Un critère absent du modèle de données est signalé, jamais ignoré.** Le fichier du personnel ne
   contient ni l'âge, ni le salaire, ni la situation familiale. À la question « quel est le salaire
   moyen ? », l'assistant répond en tête : *« Le fichier du personnel ne contient pas le salaire :
   ce critère n'a pas pu être appliqué »* et énumère les champs réellement disponibles. Un résultat
   ne peut donc jamais être lu comme la réponse à une question qui n'a pas été traitée. Nuance :
   « 10 ans d'**ancienneté** » ne déclenche aucun avertissement, car l'ancienneté se calcule depuis
   `date_recrutement`.

Le sexe, lui, **est** enregistré : « qui sont les hommes bénéficiaires du Hajj ? » applique
réellement le filtre et l'annonce dans la réponse (`… (hommes)`).

Exemples traités :
- « Qui n'a pas bénéficié de l'aide scolaire en 2024 ? »
- « Qui n'a jamais rien reçu à la maintenance ? »
- « Combien a coûté le pèlerinage Hajj ? »
- « Quel service est le moins distribué ? »
- « Quel est le taux de couverture du Hajj ? »
- « Qu'a reçu MM0012 ? » (ou par son nom)
- « Quels services existent ? »
- « Quel est l'état du budget ? »
- « Qui devrait être prioritaire pour l'aide au mariage ? »
- Politesse et méta-questions : « bjr », « merci », « que peux-tu faire ? »

**Renfort par modèle de langage (optionnel).** Si une clé API est configurée, un LLM
(`llama-3.3-70b-versatile` via Groq) vient compléter les règles pour les tournures libres.
L'architecture est délibérément restrictive :

> **Le LLM ne répond jamais à la question.** Il traduit la phrase en un *plan de requête*
> structuré (intention + entités). C'est ensuite le code Django qui exécute la requête SQL et met
> en forme le résultat.

Trois conséquences, à défendre en soutenance :

1. **Aucun chiffre ne peut être inventé** — montants et effectifs viennent tous de l'ORM.
2. **Aucune donnée nominative ne sort du serveur** — on n'envoie que la question et les libellés
   des services et départements. Un test (`test_aucune_donnee_nominative_envoyee`) vérifie qu'aucun
   nom ni matricule ne figure dans la requête sortante.
3. **Tout ce que le modèle renvoie est revalidé contre la base** (`llm._valider`) : un service
   inventé, une année aberrante ou un département inexistant sont écartés, jamais propagés.

Les **règles restent maîtresses des entités** (correspondance exacte avec la base) ; le LLM
n'intervient que là où elles sont muettes ou peu sûres. Concrètement, sur 9 formulations libres
testées, les règles seules en traitaient 8 correctement, et le LLM a corrigé la neuvième
(« montre-moi ceux qui **méritent** le Hajj » → priorisation, et non liste des bénéficiaires) sans
rien dégrader ailleurs. Chaque réponse indique son moteur (`regles` ou `llm`), affiché par un badge
dans l'interface.

**Sans clé, ou en cas de panne réseau, de quota dépassé ou de timeout**, l'assistant retombe
silencieusement sur ses règles : aucune fonctionnalité n'est perdue et la démo ne peut pas échouer
faute de réseau.

**Configuration** — copiez `backend/.env.example` en `backend/.env` :

```ini
GROQ_API_KEY=votre_cle      # vide = moteur à règles seul
GROQ_MODELE=llama-3.3-70b-versatile
GROQ_TIMEOUT=6
```

Le fichier `.env` est exclu du dépôt. La suite de tests force `LLM_ACTIF=False` : elle reste hors
ligne, déterministe et ne consomme aucun quota.

**Limite assumée** : le périmètre reste celui des intentions prévues. Une question comme « pourquoi
la couverture baisse-t-elle ? » renvoie le message d'aide plutôt qu'une analyse inventée.

### Accès à l'assistant
Deux points d'entrée : la page **Assistant admin**, et une **bulle flottante** disponible en bas à
droite de tous les écrans. Le panneau est masqué et non démonté à la fermeture : la conversation
survit à une consultation de tableau.

### 3. Clustering du personnel (`core/ai.py` → `clusteriser`)
K-Means (scikit-learn) sur quatre variables standardisées — ancienneté, nombre d'enfants, nombre
d'aides reçues, montant cumulé perçu. Chaque groupe est automatiquement étiqueté par comparaison à
la moyenne générale (*sous-servis — à prioriser*, *bien servis*, …), ce qui met en évidence les
déséquilibres de distribution entre profils.

---

## API

Toutes les routes sont préfixées par `/api/` et nécessitent l'en-tête `Authorization: Bearer <jwt>`.

### Authentification
| Méthode | Route | Rôle |
|---|---|---|
| POST | `/auth/login/` | jetons + profil |
| POST | `/auth/refresh/` | rafraîchir le jeton |
| GET | `/auth/me/` | profil courant |
| POST | `/auth/logout/` | déconnexion |

### CRUD
| Méthode | Route |
|---|---|
| GET POST | `/personnel/`, `/activites/`, `/transactions/` |
| GET PUT PATCH DELETE | `/personnel/{matricule}/`, `/activites/{id}/`, `/transactions/{id}/` |

### Équité et doublons
| Route | Rôle |
|---|---|
| `/activites/{id}/beneficiaires/?annee=` | employés déjà servis |
| `/activites/{id}/non-beneficiaires/?annee=&departement=` | **les oubliés** |
| `/personnel/sans-aucune-aide/` | employés n'ayant jamais rien reçu |
| `/personnel/{matricule}/transactions/` | historique d'un employé |
| `/transactions/verifier-doublon/?matricule=&id_activitee=&annee=` | contrôle préalable |

### Statistiques et budget
`/stats/`, `/stats/couverture/`, `/activites/budget/?seuil=&annee=`

### IA
`/ia/recommandations/?id_activitee=&annee=&limite=&departement=&eligibles=`,
`/ia/clusters/?n=`, `/ia/chatbot/` (POST `{"question": "…", "contexte": {…}}` — le `contexte` renvoyé
par la réponse précédente est à reposter pour que l'assistant garde le fil ; l'API reste sans état)

### Exports (`?format=excel|pdf`)
`/personnel/export/`, `/transactions/export/`, `/activites/export/`,
`/activites/{id}/export-non-beneficiaires/`, `/ia/recommandations/export/`,
`/stats/rapport-annuel/?annee=`, `/transactions/{id}/attestation/` (PDF)

Les paramètres `search`, `ordering`, `page`, `page_size` sont disponibles sur toutes les listes et
sont repris tels quels par les exports.

---

## Tests

```bash
cd backend
python manage.py test core
```

102 tests couvrent l'authentification, le CRUD, la logique d'équité (bénéficiaires /
non-bénéficiaires / taux de couverture), les trois règles d'attribution — dont un cycle de rotation
complet et le cas de la nouvelle recrue —, le budget et ses alertes, les
exports Excel et PDF, le champ `sexe` (filtres, statistiques, validation) ainsi que les trois
briques d'IA — dont 46 tests pour le seul assistant : politesse, abréviations, fautes de frappe,
mots collés, années malformées, homonymes, mémoire de conversation, critères absents du modèle,
refus de deviner, et pour la couche LLM : validation des réponses du modèle, non-fuite de données
nominatives, repli sur panne réseau / HTTP 429 / clé absente.

Les appels au LLM sont toujours simulés (`unittest.mock`) et `settings.LLM_ACTIF` est forcé à
`False` pendant les tests : la suite ne sort jamais sur le réseau.

```bash
cd frontend
npm run lint
npm run build
```

---

## Structure du projet

```
gestion_sociaux/
├── venv/                          environnement Python
├── backend/
│   ├── config/                    settings, urls, wsgi
│   ├── core/
│   │   ├── models.py              personnel, activitee, transaction
│   │   ├── serializers.py         sérialisation + validation
│   │   ├── regles.py              les 3 règles d'attribution (source unique)
│   │   ├── views.py               API REST, équité, budget, stats, IA
│   │   ├── filters.py             filtres de recherche
│   │   ├── ai.py                  score d'équité, K-Means, assistant NL
│   │   ├── llm.py                 renfort LLM optionnel (Groq) + garde-fous
│   │   ├── exports.py             Excel et PDF
│   │   ├── tests.py               102 tests
│   │   └── management/commands/seed.py
│   ├── .env.example               modèle de configuration (.env est ignoré)
│   ├── db.sqlite3
│   └── requirements.txt
└── frontend/
    └── src/
        ├── api/client.js          axios + JWT + téléchargements
        ├── context/AuthContext.jsx
        ├── components/            Layout, tableaux, modales, graphiques
        └── pages/                 11 écrans
```

---

## Notes de conception

- **La règle anti-doublon vit dans le serializer**, donc elle s'applique à toute écriture, quelle
  qu'en soit l'origine (front, admin Django, appel direct de l'API).
- **Le champ `annee` est déduit de `date_transaction`** et une incohérence entre les deux est
  refusée : les statistiques annuelles restent fiables.
- **La palette des graphiques est validée pour les daltonismes** (deutan / protan / tritan) : chaque
  série est identifiée par une légende et des libellés directs, jamais par la couleur seule. Les
  statuts budgétaires portent un libellé texte en plus de la couleur.
- **Les listes sont paginées côté serveur** et les exports reprennent les filtres actifs.
