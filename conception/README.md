# Conception — MarsaSocial

Diagrammes UML de la plateforme, au format **draw.io** (XML non compressé : lisible,
versionnable et comparable dans git). Chaque `.drawio` est accompagné de son export PNG,
prêt à être inséré dans le rapport.

| Fichier | Contenu |
|---|---|
| `diagramme_classes.drawio` | Modèle de données (3 tables), énumérations, couche métier |
| `diagramme_cas_utilisation.drawio` | Acteurs et cas d'utilisation, relations `include` / `extend` |
| `diagramme_sequence.drawio` | **3 pages** : attribution, authentification, assistant IA |

## Ouvrir et modifier

- **draw.io Desktop** — double-clic sur le fichier
- **En ligne** — <https://app.diagrams.net> → *Ouvrir un fichier existant*
- **VS Code** — extension *Draw.io Integration* (`hediet.vscode-drawio`)

Le fichier de séquence contient trois pages : les onglets sont en bas de la fenêtre.

## Regénérer les PNG

```bash
"C:/Program Files/draw.io/draw.io.exe" --export --format png --scale 1 --border 10 \
  --output diagramme_classes.png diagramme_classes.drawio
```

Pour une page précise d'un fichier multi-pages, ajouter `--page-index N`.
Attention : **cet indice commence à 1**, contrairement à ce que son nom suggère.

Pour le rapport, préférer `--format svg` (vectoriel, net à l'impression) ou
`--scale 2` en PNG.

## Contenu des diagrammes

### Diagramme de classes
Les trois entités persistantes et leurs associations, les deux énumérations
(`RegleAttribution`, `Sexe`), et la couche métier : `Regles`, `MoteurIA`,
`RenfortLLM`, `Exports`. Les dépendances montrent que les règles d'attribution
sont isolées dans un module unique.

### Diagramme de cas d'utilisation
L'administrateur RH est le seul acteur humain. Le modèle de langage est un
**acteur secondaire optionnel**, relié par une relation `extend` : le cas de base
reste complet sans lui. La vérification des règles est en `include` — elle est
obligatoire à chaque attribution.

### Diagrammes de séquence
1. **Attribution d'un service** — le scénario central, avec les deux niveaux de
   contrôle (préalable pour le confort, à l'enregistrement pour la garantie) et
   les deux fragments `alt`.
2. **Authentification JWT** — connexion, puis rafraîchissement automatique du
   jeton expiré dans un fragment `opt`.
3. **Assistant en langage naturel** — la nature hybride du moteur : le fragment
   `opt` du LLM est simplement sauté quand aucune clé n'est configurée.
