"""Moteur de linkage : matching, détection d'ambiguïté, validation."""

from __future__ import annotations

import pandas as pd

from concordx.config import Config
from concordx.matching.blockers import build_blocks, get_candidate_source_indices
from concordx.matching.schema import MatchCandidate, MatchResult
from concordx.matching.scorers import score_row_pair


class Linker:
    """Moteur de linkage entre source et cible."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.rules = config.rules
        self.min_score = config.min_score
        self.auto_accept_score = config.auto_accept_score
        self.top_k = config.top_k
        self.ambiguity_delta = config.ambiguity_delta
        self.blocker = config.blocker

    def run(
        self,
        df_source: pd.DataFrame,
        df_target: pd.DataFrame,
    ) -> list[MatchResult]:
        """
        Exécute le matching pour toutes les lignes cible.

        Returns:
            Liste de MatchResult, un par ligne cible.
        """
        source_cols = set(df_source.columns)
        target_cols = set(df_target.columns)

        if self.blocker == "year_or_initial":
            source_blocks = build_blocks(df_source, self.rules, is_source=True)
        else:
            source_blocks = {"default": list(range(len(df_source)))}

        results: list[MatchResult] = []

        for target_idx in range(len(df_target)):
            target_row = df_target.iloc[target_idx]

            if self.blocker == "year_or_initial":
                candidate_indices = get_candidate_source_indices(
                    target_row,
                    target_idx,
                    source_blocks,
                    self.rules,
                    source_cols,
                    target_cols,
                    df_source,
                    df_target,
                )
            else:
                candidate_indices = list(range(len(df_source)))

            candidates: list[MatchCandidate] = []
            for src_idx in candidate_indices:
                source_row = df_source.iloc[src_idx]
                score, details = score_row_pair(source_row, target_row, self.rules)
                if score >= self.min_score:
                    candidates.append(
                        MatchCandidate(
                            source_row_id=src_idx,
                            score=score,
                            details=details,
                        )
                    )

            candidates.sort(key=lambda c: c.score, reverse=True)
            top_candidates = candidates[: self.top_k]

            best_score = top_candidates[0].score if top_candidates else 0.0
            second_score = top_candidates[1].score if len(top_candidates) > 1 else 0.0
            is_ambiguous = len(top_candidates) >= 2 and (best_score - second_score) < self.ambiguity_delta

            if not top_candidates:
                status = "rejected"
                chosen = None
                explanation = "No candidates above min_score"
            elif best_score >= self.auto_accept_score and not is_ambiguous:
                status = "auto"
                chosen = top_candidates[0].source_row_id
                explanation = f"Auto-accept score={best_score:.1f}"
            elif is_ambiguous or best_score < self.auto_accept_score:
                status = "pending"
                chosen = None
                explanation = (
                    f"Ambiguous (Δ={best_score - second_score:.1f})"
                    if is_ambiguous
                    else f"Below threshold (score={best_score:.1f})"
                )
            else:
                status = "auto"
                chosen = top_candidates[0].source_row_id
                explanation = f"Auto-accept score={best_score:.1f}"

            results.append(
                MatchResult(
                    target_row_id=target_idx,
                    candidates=top_candidates,
                    best_score=best_score,
                    is_ambiguous=is_ambiguous,
                    status=status,
                    chosen_source_row_id=chosen,
                    explanation=explanation,
                )
            )

        return results

    def resolve_pending(
        self,
        results: list[MatchResult],
        choices: dict[int, int | None],
    ) -> None:
        """
        Applique les choix utilisateur aux résultats en attente.

        choices: {target_row_id: source_row_id ou None}
        None = pas de correspondance (rejected).
        """
        for r in results:
            if r.status != "pending":
                continue
            if r.target_row_id in choices:
                src = choices[r.target_row_id]
                if src is not None:
                    r.status = "accepted"
                    r.chosen_source_row_id = src
                    r.explanation = "User accepted"
                else:
                    r.status = "rejected"
                    r.chosen_source_row_id = None
                    r.explanation = "No match (user)"
