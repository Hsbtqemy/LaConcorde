"""Contrôleur de session : save/load, decisions, undo."""

from __future__ import annotations

import json
from pathlib import Path

from laconcorde.matching.schema import MatchResult


class SessionController:
    """Gère la persistance et l'historique des décisions."""

    def __init__(self, state: object) -> None:
        self._state = state

    def save_session(self, path: Path, config_dict: dict, choices: dict[int, int | None]) -> None:
        """Sauvegarde config_dict et choices dans un fichier JSON."""
        data = {
            "config_dict": config_dict,
            "choices": {str(k): v for k, v in choices.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_session(self, path: Path) -> tuple[dict, dict[int, int | None]]:
        """Charge config_dict et choices depuis un fichier JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        config_dict = data.get("config_dict", {})
        choices_raw = data.get("choices", {})
        choices = {int(k): v for k, v in choices_raw.items()}
        return config_dict, choices

    @staticmethod
    def push_undo(state: object, target_row_id: int, old_chosen: int | None) -> None:
        """Empile une décision pour undo."""
        if hasattr(state, "undo_stack"):
            state.undo_stack.append((target_row_id, old_chosen))

    @staticmethod
    def pop_undo(state: object) -> tuple[int, int | None] | None:
        """Dépile et retourne la dernière décision."""
        if hasattr(state, "undo_stack") and state.undo_stack:
            return state.undo_stack.pop()
        return None
