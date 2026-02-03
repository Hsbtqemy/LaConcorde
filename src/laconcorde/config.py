"""Configuration et chargement du fichier config JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_METHODS = frozenset({"exact", "normalized_exact", "fuzzy_ratio", "token_set", "contains"})
VALID_OVERWRITE_MODES = frozenset({"never", "if_empty", "always"})
VALID_BLOCKERS = frozenset({"year_or_initial", "default"})


class LaConcordeError(Exception):
    """Exception de base pour LaConcorde."""


class ConfigError(LaConcordeError, ValueError):
    """Erreur de validation de la configuration."""


class ConfigFileError(LaConcordeError):
    """Erreur de chargement du fichier de configuration (fichier absent, JSON invalide)."""


@dataclass
class FieldRule:
    """Règle de matching pour un champ."""

    source_col: str
    target_col: str
    weight: float = 1.0
    method: str = "fuzzy_ratio"  # exact, normalized_exact, fuzzy_ratio, token_set, contains
    normalize: bool = True
    remove_diacritics: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FieldRule:
        source_col = d.get("source_col", "")
        target_col = d.get("target_col", "")
        weight = float(d.get("weight", 1.0))
        method = d.get("method", "fuzzy_ratio")

        if weight <= 0:
            raise ConfigError(f"weight doit être > 0 (got {weight})")
        if method not in VALID_METHODS:
            raise ConfigError(f"method invalide: {method!r}. Valides: {sorted(VALID_METHODS)}")

        return cls(
            source_col=source_col,
            target_col=target_col,
            weight=weight,
            method=method,
            normalize=d.get("normalize", True),
            remove_diacritics=d.get("remove_diacritics", False),
        )


@dataclass
class Config:
    """Configuration principale de LaConcorde."""

    source_file: str = ""
    target_file: str = ""
    source_sheet: str | None = None  # None = première feuille
    target_sheet: str | None = None
    # Si un seul fichier avec deux feuilles
    single_file: str | None = None
    source_sheet_in_single: str | None = None
    target_sheet_in_single: str | None = None

    rules: list[FieldRule] = field(default_factory=list)
    transfer_columns: list[str] = field(default_factory=list)
    transfer_column_rename: dict[str, str] = field(default_factory=dict)  # source_col -> target_col_name
    overwrite_mode: str = "if_empty"  # never, if_empty, always
    create_missing_cols: bool = True
    suffix_on_collision: str = "_src"

    min_score: float = 0.0
    auto_accept_score: float = 95.0
    top_k: int = 5
    ambiguity_delta: float = 5.0
    blocker: str = "year_or_initial"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Config:
        rules = [FieldRule.from_dict(r) for r in d.get("rules", [])]
        single_file = d.get("single_file")
        source_file = d.get("source_file", "")
        target_file = d.get("target_file", "")
        overwrite_mode = d.get("overwrite_mode", "if_empty")
        min_score = float(d.get("min_score", 0.0))
        auto_accept_score = float(d.get("auto_accept_score", 95.0))
        top_k = int(d.get("top_k", 5))
        ambiguity_delta = float(d.get("ambiguity_delta", 5.0))
        blocker = d.get("blocker", "year_or_initial")

        if single_file:
            if not d.get("source_sheet_in_single") or not d.get("target_sheet_in_single"):
                raise ConfigError("single_file requis: source_sheet_in_single et target_sheet_in_single")
        else:
            if not source_file or not target_file:
                raise ConfigError("source_file et target_file requis (ou single_file avec feuilles)")

        if overwrite_mode not in VALID_OVERWRITE_MODES:
            raise ConfigError(f"overwrite_mode invalide: {overwrite_mode!r}. Valides: {sorted(VALID_OVERWRITE_MODES)}")
        if not 0 <= min_score <= 100:
            raise ConfigError(f"min_score doit être entre 0 et 100 (got {min_score})")
        if not 0 <= auto_accept_score <= 100:
            raise ConfigError(f"auto_accept_score doit être entre 0 et 100 (got {auto_accept_score})")
        if top_k < 1:
            raise ConfigError(f"top_k doit être >= 1 (got {top_k})")
        if ambiguity_delta < 0:
            raise ConfigError(f"ambiguity_delta doit être >= 0 (got {ambiguity_delta})")
        if blocker not in VALID_BLOCKERS:
            raise ConfigError(f"blocker invalide: {blocker!r}. Valides: {sorted(VALID_BLOCKERS)}")

        return cls(
            source_file=source_file,
            target_file=target_file,
            source_sheet=d.get("source_sheet"),
            target_sheet=d.get("target_sheet"),
            single_file=single_file,
            source_sheet_in_single=d.get("source_sheet_in_single"),
            target_sheet_in_single=d.get("target_sheet_in_single"),
            rules=rules,
            transfer_columns=d.get("transfer_columns", []),
            transfer_column_rename=d.get("transfer_column_rename", {}),
            overwrite_mode=overwrite_mode,
            create_missing_cols=d.get("create_missing_cols", True),
            suffix_on_collision=d.get("suffix_on_collision", "_src"),
            min_score=min_score,
            auto_accept_score=auto_accept_score,
            top_k=top_k,
            ambiguity_delta=ambiguity_delta,
            blocker=blocker,
        )

    @classmethod
    def load(cls, path: str | Path) -> Config:
        """
        Charge la configuration depuis un fichier JSON.

        Raises:
            ConfigFileError: Si le fichier est absent ou le JSON invalide.
            ConfigError: Si la configuration est invalide.
        """
        path = Path(path).resolve()
        if not path.exists():
            raise ConfigFileError(f"Fichier de configuration introuvable: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigFileError(f"JSON invalide dans {path}: {e}") from e
        except OSError as e:
            raise ConfigFileError(f"Impossible de lire {path}: {e}") from e

        if not isinstance(d, dict):
            raise ConfigFileError(f"Fichier de configuration invalide: {path} doit contenir un objet JSON")

        config = cls.from_dict(d)
        config.resolve_paths(path.parent)
        return config

    def resolve_paths(self, base_dir: Path) -> None:
        """
        Résout les chemins relatifs par rapport au répertoire de base (ex. dossier du fichier config).

        Modifie source_file, target_file et single_file en place.
        """
        base = Path(base_dir)
        if self.source_file and not Path(self.source_file).is_absolute():
            self.source_file = str((base / self.source_file).resolve())
        if self.target_file and not Path(self.target_file).is_absolute():
            self.target_file = str((base / self.target_file).resolve())
        if self.single_file and not Path(self.single_file).is_absolute():
            self.single_file = str((base / self.single_file).resolve())
