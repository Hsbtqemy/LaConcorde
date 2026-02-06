"""Contrôleur du pipeline : matching, resolve, export."""

from __future__ import annotations

from pathlib import Path

from laconcorde.config import Config
from laconcorde.io_excel import load_source_target
from laconcorde.matching.linker import Linker
from laconcorde.matching.schema import MatchResult


class PipelineController:
    """Orchestre le pipeline LaConcorde (sans threading, pour usage direct)."""

    @staticmethod
    def run_matching(config_dict: dict, base_dir: Path | None = None) -> tuple:
        """
        Exécute le matching de façon synchrone.
        Returns: (df_source, df_target, results, linker)
        """
        config = Config.from_dict(config_dict)
        config.resolve_paths(base_dir or Path("."))
        df_source, df_target = load_source_target(config)
        linker = Linker(config)
        results = linker.run(df_source, df_target)
        return df_source, df_target, results, linker

    @staticmethod
    def resolve_pending(linker: Linker, results: list[MatchResult], choices: dict[int, int | None]) -> None:
        """Applique les choix utilisateur aux résultats pending."""
        linker.resolve_pending(results, choices)
