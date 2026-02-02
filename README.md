# ConcordX

Outil de concordance entre tableurs Excel (xlsx) avec fuzzy matching multi-colonnes, validation humaine et transfert de colonnes vers un tableur cible.

## Installation

```bash
pip install -e .
# ou avec les dépendances de test :
pip install -e ".[dev]"
```

## Usage CLI

Exécuter les commandes depuis la racine du projet.

### Lister les feuilles d'un fichier

```bash
concordx list-sheets fichier.xlsx
```

### Créer des données de démonstration

```bash
python examples/create_sample_data.py
```

### Exécuter le linkage

```bash
concordx run --config examples/config_example.json --output out.xlsx
```

Options :
- `--dry-run` : Ne produit que le mapping.csv et le rapport console (pas de fichier xlsx de sortie)
- `--interactive` / `-i` : Validation interactive des cas ambigus
- `--mapping` / `-m` : Chemin personnalisé pour mapping.csv

Exemple en mode dry-run :

```bash
concordx run --config examples/config_example.json --dry-run
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
| `overwrite_mode` | `never`, `if_empty`, `always` |
| `auto_accept_score` | Score au-dessus duquel on accepte automatiquement (si non ambigu) |
| `ambiguity_delta` | Si top1 - top2 < delta → marqué ambigu |
| `blocker` | Stratégie de réduction : `year_or_initial` |

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

## Licence

MIT
