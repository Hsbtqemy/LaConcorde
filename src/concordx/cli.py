"""Interface en ligne de commande ConcordX."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from concordx import __version__
from concordx.config import Config
from concordx.io_excel import list_sheets, load_source_target, save_xlsx
from concordx.matching.linker import Linker
from concordx.matching.schema import MatchResult
from concordx.report import build_report_df, print_report_console
from concordx.transfer import build_mapping_csv, transfer_columns


def _validate_columns(config: Config, df_source: pd.DataFrame, df_target: pd.DataFrame) -> None:
    """Vérifie que les colonnes requises existent et avertit si des colonnes sont absentes."""
    missing: list[str] = []
    for rule in config.rules:
        if rule.source_col not in df_source.columns:
            missing.append(f"source.{rule.source_col}")
        if rule.target_col not in df_target.columns:
            missing.append(f"target.{rule.target_col}")
    for col in config.transfer_columns:
        if col not in df_source.columns:
            missing.append(f"transfer.{col}")
    if missing:
        print(f"Avertissement: colonnes absentes (règles ignorées): {', '.join(missing)}")


def cmd_list_sheets(filepath: str) -> int:
    """Liste les feuilles d'un fichier xlsx."""
    sheets = list_sheets(filepath)
    print(f"Feuilles dans {filepath}:")
    for s in sheets:
        print(f"  - {s}")
    return 0


def interactive_resolve(
    results: list[MatchResult],
    df_target: pd.DataFrame,
    df_source: pd.DataFrame,
    top_k: int,
) -> dict[int, int | None]:
    """
    Mode interactif : pour chaque cas ambigu/pending, demande le choix utilisateur.

    Returns:
        {target_row_id: source_row_id ou None}
    """
    choices: dict[int, int | None] = {}
    pending = [r for r in results if r.status == "pending"]

    for r in pending:
        print("\n" + "=" * 60)
        print(f"Ligne cible #{r.target_row_id}:")
        print(df_target.iloc[r.target_row_id].to_string())
        print("\nCandidats (top", min(top_k, len(r.candidates)), "):")
        for i, c in enumerate(r.candidates[:top_k]):
            print(f"  [{i + 1}] Source #{c.source_row_id} - score={c.score:.1f}")
            print(f"      {df_source.iloc[c.source_row_id].to_string()}")
        print("  [0] Pas de correspondance (reject)")
        print("  [s] Passer (skip)")

        while True:
            inp = input(f"Choix (1-{min(top_k, len(r.candidates))} / 0 / s): ").strip()
            if inp.lower() == "s":
                r.status = "skipped"
                r.explanation = "User skipped"
                break
            if inp == "0":
                choices[r.target_row_id] = None
                break
            try:
                idx = int(inp)
                if 1 <= idx <= len(r.candidates):
                    choices[r.target_row_id] = r.candidates[idx - 1].source_row_id
                    break
            except ValueError:
                pass
            print("Choix invalide, réessayez.")

    return choices


def cmd_run(
    config_path: str,
    output_path: str | None,
    *,
    dry_run: bool = False,
    interactive: bool = False,
    mapping_path: str | None = None,
) -> int:
    """Exécute le pipeline ConcordX."""
    config = Config.load(config_path)
    df_source, df_target = load_source_target(config)
    _validate_columns(config, df_source, df_target)

    linker = Linker(config)
    results = linker.run(df_source, df_target)

    if interactive:
        choices = interactive_resolve(results, df_target, df_source, config.top_k)
        linker.resolve_pending(results, choices)

    # Générer mapping.csv (--mapping prime s'il est fourni)
    map_path = (
        Path(mapping_path)
        if mapping_path
        else (Path(output_path).parent / "mapping.csv" if output_path else Path(config_path).parent / "mapping.csv")
    )
    build_mapping_csv(results, str(map_path))
    print(f"Mapping écrit: {map_path}")

    print_report_console(results, config)

    if dry_run:
        print("Mode dry-run: pas d'écriture du fichier de sortie.")
        return 0

    if not output_path:
        print("Erreur: --output requis en mode non dry-run.")
        return 1

    # Transfert
    df_enriched = transfer_columns(
        df_target,
        df_source,
        results,
        config.transfer_columns,
        overwrite_mode=config.overwrite_mode,
        create_missing_cols=config.create_missing_cols,
        suffix_on_collision=config.suffix_on_collision,
    )

    report_df = build_report_df(results, config)

    sheets = {"Target": df_enriched, "REPORT": report_df}
    save_xlsx(output_path, sheets)
    print(f"Fichier de sortie: {output_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="concordx",
        description="Outil de concordance entre tableurs Excel (fuzzy matching)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Commandes")

    # list-sheets
    p_list = subparsers.add_parser("list-sheets", help="Lister les feuilles d'un xlsx")
    p_list.add_argument("file", help="Fichier xlsx")

    # run
    p_run = subparsers.add_parser("run", help="Exécuter le linkage")
    p_run.add_argument("--config", "-c", required=True, help="Fichier config JSON")
    p_run.add_argument("--output", "-o", help="Fichier xlsx de sortie")
    p_run.add_argument("--dry-run", action="store_true", help="Ne pas écrire le fichier de sortie")
    p_run.add_argument("--interactive", "-i", action="store_true", help="Validation interactive des ambigus")
    p_run.add_argument("--mapping", "-m", help="Chemin pour mapping.csv")

    args = parser.parse_args()

    if args.command == "list-sheets":
        return cmd_list_sheets(args.file)

    if args.command == "run":
        if not args.dry_run and not args.output:
            parser.error("--output requis sauf en --dry-run")
        return cmd_run(
            args.config,
            args.output,
            dry_run=args.dry_run,
            interactive=args.interactive,
            mapping_path=args.mapping,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
