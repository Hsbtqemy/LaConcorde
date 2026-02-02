# Recommandations d'amélioration — ConcordX

Ce document recense les recommandations issues de la revue de code du projet ConcordX.

---

## Problèmes à corriger en priorité

### 1. Imports mal placés dans `cli.py`

Les imports de `Linker`, `MatchResult`, `build_report_df`, `print_report_console`, `build_mapping_csv` et `transfer_columns` sont placés après la fonction `_validate_columns` et un `print`. Ils doivent être regroupés en tête de fichier avec les autres imports.

### 2. Logique de `map_path` dans `cli.py`

Actuellement, si l'utilisateur fournit `--mapping /chemin/custom/mapping.csv` **et** `--output out.xlsx`, le mapping est écrit à côté du fichier de sortie, pas au chemin personnalisé. La priorité doit être donnée à `mapping_path` lorsqu'il est explicitement fourni.

**Logique recommandée :**
```python
map_path = (
    mapping_path
    if mapping_path
    else (Path(output_path).parent / "mapping.csv" if output_path else Path(config_path).parent / "mapping.csv")
)
```

### 3. Import redondant dans `cmd_run`

L'import `import pandas as pd` à l'intérieur de `cmd_run()` est redondant — pandas est déjà importé en tête de fichier. À supprimer.

### 4. Typage `Any` dans `io_excel.py`

La fonction `load_source_target(config: Any)` devrait utiliser le type `Config` pour une meilleure sécurité de typage et une meilleure autocomplétion.

---

## Améliorations recommandées

### 5. Validation de la configuration

`Config.from_dict()` et `FieldRule.from_dict()` n'effectuent pas de validation des valeurs. Recommandations :

- Valider que `method` appartient à `{"exact", "normalized_exact", "fuzzy_ratio", "token_set", "contains"}`
- Valider que `source_file` et `target_file` ne sont pas vides (sauf si `single_file` est utilisé)
- Valider les plages de valeurs (`weight > 0`, `min_score` et `auto_accept_score` entre 0 et 100, etc.)

### 6. Source unique pour la version

La version est définie à deux endroits (`__init__.py` et `pyproject.toml`). Risque de désynchronisation. Solutions possibles :

- Utiliser `importlib.metadata.version("concordx")` dans `__init__.py`
- Ou lire dynamiquement depuis `pyproject.toml` au build

### 7. Performance des blockers

`build_blocks()` utilise `df.iterrows()`, qui est lent sur de gros DataFrames. Pour des volumes importants, envisager :

- Une approche vectorisée avec les colonnes concernées
- Ou `df.apply()` avec une fonction optimisée

### 8. Gestion des erreurs

- **Config.load()** : gérer les cas où le fichier n'existe pas, le JSON est invalide, ou les chemins sont incorrects
- **load_sheet()** : gérer l'absence du fichier Excel ou d'une feuille inexistante
- Lever des exceptions explicites avec des messages d'erreur clairs pour faciliter le débogage

### 9. Outillage qualité de code

| Outil | Usage |
|-------|--------|
| **Ruff** ou **Flake8** | Linting |
| **mypy** | Vérification des types |
| **Black** ou **Ruff format** | Formatage automatique |
| **pre-commit** | Hooks avant commit |
| **GitHub Actions** (ou équivalent) | CI : tests + lint sur chaque push/PR |

### 10. Mutabilité de `MatchResult`

Le dataclass `MatchResult` est modifié in-place dans `resolve_pending()`. Pour une approche plus fonctionnelle et prévisible, envisager de retourner de nouveaux objets plutôt que de muter les existants.

---

## Bonnes pratiques supplémentaires

### Tests

- Ajouter des tests pour les cas d'erreur (fichier manquant, config invalide)
- Envisager `pytest-cov` pour mesurer la couverture de code
- Tester le mode interactif (avec mock de `input()`)

### Documentation

- Documenter les exceptions levées dans les docstrings
- Ajouter des exemples d'utilisation dans le README pour les cas avancés
- Envisager une documentation API (Sphinx, MkDocs)

### Sécurité

- Dans `norm_doi()`, remplacer le `except Exception` par des exceptions plus spécifiques
- Vérifier le comportement avec des chemins très longs ou des liens symboliques selon l'environnement cible

---

## Priorisation suggérée

| Priorité | Action |
|----------|--------|
| P0 | Corriger les imports et la logique `map_path` dans `cli.py` |
| P1 | Remplacer `Any` par `Config` dans `io_excel.py` |
| P2 | Ajouter la validation de configuration |
| P2 | Mettre en place Ruff + mypy + pre-commit |
| P3 | Améliorer la gestion des erreurs |
| P3 | Optimiser `build_blocks()` si volumes importants |
| P4 | Unifier la source de version, documenter les exceptions |
