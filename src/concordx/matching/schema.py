"""Schémas et types pour le matching."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchCandidate:
    """Un candidat de correspondance pour une ligne cible."""

    source_row_id: int
    score: float
    details: dict[str, float]  # score par champ

    def __repr__(self) -> str:
        return f"MatchCandidate(source_row={self.source_row_id}, score={self.score:.1f})"


@dataclass
class MatchResult:
    """Résultat de matching pour une ligne cible."""

    target_row_id: int
    candidates: list[MatchCandidate]
    best_score: float
    is_ambiguous: bool
    status: str  # auto, accepted, rejected, skipped
    chosen_source_row_id: int | None = None
    explanation: str = ""
