# LaConcorde

Outil de concordance entre tableurs Excel (xlsx) avec fuzzy matching multi-colonnes, validation humaine et transfert de colonnes vers un tableur cible.

## Installation

```bash
pip install -e .
# ou avec les dépendances de test :
pip install -e ".[dev]"
# avec l'interface graphique (PySide6) :
pip install -e ".[gui]"
```

## Interface graphique (GUI)

Lancement :

```bash
laconcorde-gui
# ou
python -m laconcorde_gui
```

Sous Windows, double-cliquez sur `laconcorde-gui.bat` (ou exécutez-le en ligne de commande). Le script active automatiquement un venv `.venv` s'il existe.

### Workflow

1. **Projet** : Sélection des fichiers Excel source et cible (ou un seul fichier avec deux feuilles). Charger les aperçus pour visualiser les colonnes.
2. **Règles** : Éditer les règles de matching (colonnes source/cible, poids, méthode), paramètres globaux (auto_accept_score, top_k, etc.) et colonnes à transférer. Lancer le matching.
3. **Validation** : Valider les cas ambigus (pending) via trois panneaux : queue, détails cible, candidats. Raccourcis : A (accepter #1), 1-9 (accepter candidat n), R (rejeter), S (skipped), U (undo), Bulk accept >= X.
4. **Export** : Choisir le chemin xlsx de sortie et optionnellement mapping.csv, puis exporter.

### Exécutable Windows (.exe)

Pour créer un exécutable autonome (sans installer Python) :

```bash
pip install -e ".[gui]" pyinstaller
python build_exe.py
```

L'exécutable et les DLL seront dans `dist/laconcorde_gui/`. Copiez tout le dossier pour distribuer l'application. Aucune installation de Python ou de dépendances n'est requise sur la machine cible.

### Limites

- Le bouton **Annuler** pendant le matching est best-effort : le moteur `Linker.run()` est synchrone et non interruptible. Si l'annulation est demandée avant la fin, les résultats sont ignorés et un message s'affiche.
- Les fichiers Excel originaux ne sont jamais modifiés ; l'export crée toujours un nouveau fichier.

## Usage CLI

Exécuter les commandes depuis la racine du projet.

### Lister les feuilles d'un fichier

```bash
laconcorde list-sheets fichier.xlsx
```

### Créer des données de démonstration

```bash
python examples/create_sample_data.py
```

### Exécuter le linkage

```bash
laconcorde run --config examples/config_example.json --output out.xlsx
```

Options :
- `--dry-run` : Ne produit que le mapping.csv et le rapport console (pas de fichier xlsx de sortie)
- `--interactive` / `-i` : Validation interactive des cas ambigus
- `--mapping` / `-m` : Chemin personnalisé pour mapping.csv

Exemple en mode dry-run :

```bash
laconcorde run --config examples/config_example.json --dry-run
```

## Configuration (JSON)

Exemple de fichier de configuration :

```json
{
  "source_file": "data/source.xlsx",
  "target_file": "data/target.xlsx",
  "source_sheet": null,
  "target_sheet": null,
  "rules": [
    {"source_col": "auteur", "target_col": "author", "weight": 1.0, "method": "fuzzy_ratio", "normalize": true},
    {"source_col": "titre", "target_col": "title", "weight": 1.0, "method": "fuzzy_ratio", "normalize": true},
    {"source_col": "annee", "target_col": "year", "weight": 1.0, "method": "exact", "normalize": true},
    {"source_col": "doi", "target_col": "doi", "weight": 2.0, "method": "normalized_exact", "normalize": true}
  ],
  "transfer_columns": ["notes", "categorie"],
  "transfer_column_rename": {"notes": "commentaires", "categorie": "cat"},
  "overwrite_mode": "if_empty",
  "create_missing_cols": true,
  "suffix_on_collision": "_src",
  "min_score": 0.0,
  "auto_accept_score": 95.0,
  "top_k": 5,
  "ambiguity_delta": 5.0,
  "blocker": "year_or_initial"
}
```

### Paramètres

| Paramètre | Description |
|-----------|-------------|
| `source_file`, `target_file` | Fichiers Excel source et cible (chemins relatifs au dossier du fichier config) |
| `single_file` | Si défini, un seul fichier avec `source_sheet_in_single` et `target_sheet_in_single` |
| `rules` | Règles de matching : `source_col`, `target_col`, `weight`, `method`, `normalize`, `remove_diacritics` |
| `method` | `exact`, `normalized_exact`, `fuzzy_ratio`, `token_set`, `contains` |
| `transfer_columns` | Colonnes à transférer de la source vers la cible |
| `transfer_column_rename` | Optionnel. Mapping `{source: cible}` pour renommer (ex: `{"notes": "commentaires"}`) |
| `overwrite_mode` | `never`, `if_empty`, `always` |
| `auto_accept_score` | Score au-dessus duquel on accepte automatiquement (si non ambigu) |
| `ambiguity_delta` | Si top1 - top2 < delta → marqué ambigu |
| `blocker` | Stratégie de réduction : `year_or_initial` |

## Formats de fichiers

| Entrée | Sortie |
|--------|--------|
| **.xlsx** (Excel 2007+) | **.xlsx** (Target + REPORT) |
| **.xls** (Excel 97-2003)* | **.csv** (mapping) |
| **.ods** (LibreOffice)* | |
| **.csv** | |

\* Optionnel : `pip install xlrd` pour .xls, `pip install odfpy` pour .ods

## Sorties

- **Fichier xlsx** : Feuille Target enrichie + feuille REPORT
- **mapping.csv** : `target_row_id`, `source_row_id`, `score`, `status`, `explanation`

## Tests

```bash
pytest
```

## Qualité de code

```bash
# Lint + format
ruff check src tests && ruff format src tests

# Vérification des types
mypy src

# Pre-commit (nécessite git)
pre-commit install
pre-commit run --all-files
```

## Exceptions

En cas d'erreur, LaConcorde lève des exceptions explicites :

| Exception | Cas |
|-----------|-----|
| `ConfigFileError` | Fichier config absent, JSON invalide |
| `ExcelFileError` | Fichier Excel absent, feuille inexistante |
| `ConfigError` | Configuration invalide (paramètres hors plage, etc.) |

La CLI affiche le message d'erreur sur stderr et retourne le code 1.

## Licence

MIT
