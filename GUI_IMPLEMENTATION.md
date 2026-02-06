# Guide d'implémentation d'une interface graphique — LaConcorde

Ce document décrit l'architecture et les APIs de LaConcorde pour faciliter le développement d'une interface graphique (GUI).

---

## 1. Vue d'ensemble du flux

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Fichiers Excel  │     │   Configuration │     │   Résultats      │
│  source + cible  │────▶│   (Config)      │────▶│   MatchResult[]  │
└─────────────────┘     └─────────────────┘     └──────────────────┘
         │                        │                         │
         │                        ▼                         ▼
         │               ┌─────────────────┐     ┌──────────────────┐
         │               │  Linker.run()    │     │  Transfert +     │
         └──────────────▶│  (matching)     │────▶│  Export xlsx/csv │
                         └─────────────────┘     └──────────────────┘
```

---

## 2. Architecture des modules

| Module | Rôle | APIs principales |
|--------|------|------------------|
| `laconcorde.config` | Configuration, validation | `Config`, `Config.from_dict()`, `Config.load()` |
| `laconcorde.io_excel` | Lecture/écriture Excel | `list_sheets()`, `load_sheet()`, `load_source_target()`, `save_xlsx()` |
| `laconcorde.matching.linker` | Moteur de matching | `Linker(config).run()`, `resolve_pending()` |
| `laconcorde.matching.schema` | Types de données | `MatchResult`, `MatchCandidate` |
| `laconcorde.transfer` | Transfert colonnes, mapping | `transfer_columns()`, `build_mapping_csv()` |
| `laconcorde.report` | Rapport de synthèse | `build_report_df()`, `print_report_console()` |

---

## 3. Configuration (Config)

### Structure

```python
from laconcorde.config import Config, ConfigError, ConfigFileError

# Charger depuis un fichier JSON
config = Config.load("chemin/config.json")

# Ou créer depuis un dict (pour une GUI sans fichier)
config = Config.from_dict({
    "source_file": "chemin/source.xlsx",
    "target_file": "chemin/target.xlsx",
    "source_sheet": None,  # None = première feuille
    "target_sheet": None,
    "rules": [
        {
            "source_col": "auteur",
            "target_col": "author",
            "weight": 1.0,
            "method": "fuzzy_ratio",  # exact, normalized_exact, fuzzy_ratio, token_set, contains
            "normalize": True,
            "remove_diacritics": False
        }
    ],
    "transfer_columns": ["notes", "categorie"],
    "transfer_column_rename": {"notes": "commentaires", "categorie": "cat"},
    "overwrite_mode": "if_empty",  # never, if_empty, always
    "create_missing_cols": True,
    "suffix_on_collision": "_src",
    "min_score": 0.0,
    "auto_accept_score": 95.0,
    "top_k": 5,
    "ambiguity_delta": 5.0,
    "blocker": "year_or_initial"  # ou "default"
})
```

### Paramètres importants

| Paramètre | Type | Description | Valeurs possibles |
|-----------|------|-------------|-------------------|
| `source_file` | str | Fichier Excel source | Chemin absolu ou relatif |
| `target_file` | str | Fichier Excel cible | Idem |
| `single_file` | str | Un seul fichier avec 2 feuilles | Si défini, utiliser `source_sheet_in_single` et `target_sheet_in_single` |
| `rules` | list | Règles de matching | Liste de `{source_col, target_col, weight, method, normalize}` |
| `method` | str | Méthode de comparaison | `exact`, `normalized_exact`, `fuzzy_ratio`, `token_set`, `contains` |
| `transfer_columns` | list[str] | Colonnes à transférer | Noms des colonnes source |
| `transfer_column_rename` | dict | Renommage optionnel | `{source: cible}` |
| `overwrite_mode` | str | Écrasement des valeurs | `never`, `if_empty`, `always` |
| `auto_accept_score` | float | Score ≥ 95 → accepté auto | 0–100 |
| `ambiguity_delta` | float | Si top1–top2 < 5 → ambigu | 0+ |
| `top_k` | int | Nombre de candidats affichés | 1+ |

### Résolution des chemins

Si `Config` est créé via `from_dict()` sans fichier de config, `resolve_paths()` doit être appelé manuellement avec un répertoire de base (ex. dossier de travail) :

```python
config = Config.from_dict(d)
config.resolve_paths(Path("."))  # Chemins relatifs au répertoire courant
```

---

## 4. I/O Excel

```python
from laconcorde.io_excel import list_sheets, load_sheet, load_source_target, save_xlsx
from laconcorde.config import Config

# Lister les feuilles d'un fichier
sheets = list_sheets("fichier.xlsx")  # ["Feuille1", "Feuille2", ...]

# Charger une feuille
df = load_sheet("fichier.xlsx")  # Première feuille
df = load_sheet("fichier.xlsx", sheet_name="MaFeuille")

# Charger source + cible depuis la config
df_source, df_target = load_source_target(config)

# Sauvegarder
save_xlsx("sortie.xlsx", {"Target": df_enriched, "REPORT": report_df})
```

**Exceptions :** `ExcelFileError` (fichier absent, feuille inexistante)

---

## 5. Pipeline de matching

```python
from laconcorde.config import Config
from laconcorde.io_excel import load_source_target
from laconcorde.matching.linker import Linker
from laconcorde.matching.schema import MatchResult

# 1. Charger config et données
config = Config.load("config.json")  # ou Config.from_dict(...)
df_source, df_target = load_source_target(config)

# 2. Exécuter le matching
linker = Linker(config)
results: list[MatchResult] = linker.run(df_source, df_target)

# 3. Résoudre les cas ambigus (optionnel, mode interactif)
# results contient des MatchResult avec status="pending" pour les ambigus
pending = [r for r in results if r.status == "pending"]
for r in pending:
    # Afficher dans la GUI : ligne cible + candidats (r.candidates)
    # L'utilisateur choisit : r.candidates[i].source_row_id ou None
    choices = {r.target_row_id: chosen_source_row_id}  # ou None
linker.resolve_pending(results, choices)
```

### Structure MatchResult

```python
@dataclass
class MatchResult:
    target_row_id: int           # Index de la ligne cible
    candidates: list[MatchCandidate]  # Top-k candidats source
    best_score: float
    is_ambiguous: bool
    status: str                  # "auto", "accepted", "rejected", "pending", "skipped"
    chosen_source_row_id: int | None  # Résultat final (None = pas de match)
    explanation: str

@dataclass
class MatchCandidate:
    source_row_id: int
    score: float
    details: dict[str, float]    # Score par champ (ex: "auteur:author": 95.0)
```

### Statuts possibles

| Statut | Signification |
|--------|---------------|
| `auto` | Accepté automatiquement (score ≥ auto_accept_score, non ambigu) |
| `accepted` | Accepté par l'utilisateur (mode interactif) |
| `rejected` | Pas de correspondance |
| `pending` | En attente de validation (ambigu ou score < seuil) |
| `skipped` | Ignoré par l'utilisateur |

---

## 6. Transfert et export

```python
from laconcorde.transfer import transfer_columns, build_mapping_csv
from laconcorde.report import build_report_df

# Transfert des colonnes
df_enriched = transfer_columns(
    df_target,
    df_source,
    results,
    config.transfer_columns,
    transfer_column_rename=config.transfer_column_rename or None,
    overwrite_mode=config.overwrite_mode,
    create_missing_cols=config.create_missing_cols,
    suffix_on_collision=config.suffix_on_collision,
)

# Générer le rapport
report_df = build_report_df(results, config)

# Sauvegarder
save_xlsx("sortie.xlsx", {"Target": df_enriched, "REPORT": report_df})
build_mapping_csv(results, "mapping.csv")
```

### Format mapping.csv

| Colonne | Description |
|---------|-------------|
| `target_row_id` | Index de la ligne cible |
| `source_row_id` | Index de la ligne source (vide si rejeté) |
| `score` | Meilleur score |
| `status` | auto, accepted, rejected, pending, skipped |
| `explanation` | Explication |

---

## 7. Gestion des erreurs

```python
from laconcorde import LaConcordeError, ConfigError, ConfigFileError, ExcelFileError

try:
    config = Config.load("config.json")
    df_source, df_target = load_source_target(config)
    # ...
except ConfigFileError as e:
    # Fichier config absent, JSON invalide
    message = str(e)
except ExcelFileError as e:
    # Fichier Excel absent, feuille inexistante
    message = str(e)
except ConfigError as e:
    # Validation de config (paramètres, règles)
    message = str(e)
except LaConcordeError as e:
    # Toute autre erreur LaConcorde
    message = str(e)
```

---

## 8. Points d'entrée pour une GUI

### 8.1 Sans fichier de config

La GUI peut construire un `Config` en mémoire via `Config.from_dict()` :

```python
config_dict = {
    "source_file": path_source,  # Chemin absolu
    "target_file": path_target,
    "source_sheet": sheet_source or None,
    "target_sheet": sheet_target or None,
    "rules": [
        {"source_col": col_src, "target_col": col_tgt, "weight": w, "method": m, "normalize": True}
        for col_src, col_tgt, w, m in rules_from_ui
    ],
    "transfer_columns": transfer_cols_from_ui,
    "transfer_column_rename": rename_dict or {},
    "overwrite_mode": overwrite_from_ui,
    "auto_accept_score": float(slider_value),
    "ambiguity_delta": float(delta_value),
    "top_k": int(top_k_value),
    "blocker": "year_or_initial",
    # ... autres paramètres
}
config = Config.from_dict(config_dict)
# Pas besoin de resolve_paths si chemins déjà absolus
```

### 8.2 Workflow recommandé pour la GUI

1. **Paramétrage**
   - Sélection fichier source + feuille (via `list_sheets`)
   - Sélection fichier cible + feuille
   - Éditeur de règles (source_col, target_col, weight, method)
   - Colonnes à transférer + renommage optionnel
   - Sliders : auto_accept_score, ambiguity_delta, top_k

2. **Exécution**
   - `load_source_target(config)` → afficher aperçu des colonnes
   - `Linker(config).run(df_source, df_target)` → afficher progression (le run est synchrone)

3. **Résolution des ambigus**
   - Filtrer `results` où `status == "pending"`
   - Pour chaque : afficher ligne cible + tableau des candidats (source_row_id, score, aperçu)
   - Boutons : Accepter candidat N / Rejeter / Passer
   - Appeler `linker.resolve_pending(results, choices)`

4. **Export**
   - Chemin de sortie xlsx
   - Optionnel : chemin mapping.csv
   - `transfer_columns()` + `build_report_df()` + `save_xlsx()` + `build_mapping_csv()`

### 8.3 Exécution asynchrone (threading)

Pour ne pas bloquer l'UI pendant le matching :

```python
import threading

def run_in_background():
    try:
        config = Config.from_dict(config_dict)
        df_source, df_target = load_source_target(config)
        results = Linker(config).run(df_source, df_target)
        # Signaler à la GUI : résultats prêts
        gui.on_results_ready(results, df_source, df_target)
    except LaConcordeError as e:
        gui.on_error(str(e))

thread = threading.Thread(target=run_in_background)
thread.start()
```

---

## 9. Dépendances

```
pandas>=2.0.0
openpyxl>=3.1.0
rapidfuzz>=3.0.0
```

Pour une GUI : tkinter (inclus), PyQt, PySide, CustomTkinter, etc.

---

## 10. Exemple minimal (sans GUI)

```python
from pathlib import Path
from laconcorde.config import Config
from laconcorde.io_excel import load_source_target, save_xlsx
from laconcorde.matching.linker import Linker
from laconcorde.transfer import transfer_columns, build_mapping_csv
from laconcorde.report import build_report_df

config = Config.from_dict({
    "source_file": "source.xlsx",
    "target_file": "target.xlsx",
    "rules": [
        {"source_col": "auteur", "target_col": "author", "weight": 1.0, "method": "fuzzy_ratio", "normalize": True},
        {"source_col": "annee", "target_col": "year", "weight": 1.0, "method": "exact", "normalize": True},
    ],
    "transfer_columns": ["notes"],
    "auto_accept_score": 95.0,
    "blocker": "year_or_initial",
})
config.resolve_paths(Path("."))

df_source, df_target = load_source_target(config)
results = Linker(config).run(df_source, df_target)
df_enriched = transfer_columns(df_target, df_source, results, config.transfer_columns)
report_df = build_report_df(results, config)

save_xlsx("out.xlsx", {"Target": df_enriched, "REPORT": report_df})
build_mapping_csv(results, "mapping.csv")
```

---

## 11. Résumé des imports

```python
# Configuration
from laconcorde.config import Config, ConfigError, ConfigFileError, LaConcordeError

# I/O
from laconcorde.io_excel import (
    ExcelFileError,
    list_sheets,
    load_sheet,
    load_source_target,
    save_xlsx,
)

# Matching
from laconcorde.matching.linker import Linker
from laconcorde.matching.schema import MatchCandidate, MatchResult

# Transfert et rapport
from laconcorde.transfer import build_mapping_csv, transfer_columns
from laconcorde.report import build_report_df
```
