"""I/O Excel : chargement et sauvegarde."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from concordx.config import Config


def list_sheets(filepath: str | Path) -> list[str]:
    """
    Liste les noms des feuilles d'un fichier xlsx.

    Args:
        filepath: Chemin vers le fichier Excel.

    Returns:
        Liste des noms de feuilles.
    """
    xl = pd.ExcelFile(filepath, engine="openpyxl")
    return xl.sheet_names  # type: ignore[return-value]


def load_sheet(
    filepath: str | Path,
    sheet_name: str | None = None,
    *,
    dtype: type | dict[str, type] | None = None,
) -> pd.DataFrame:
    """
    Charge une feuille Excel dans un DataFrame en préservant le texte.

    Évite les conversions agressives en utilisant dtype=str par défaut
    pour les colonnes non numériques explicites.

    Args:
        filepath: Chemin vers le fichier.
        sheet_name: Nom de la feuille (None = première).
        dtype: Types de colonnes (None = str pour tout).

    Returns:
        DataFrame chargé.
    """
    xl = pd.ExcelFile(filepath, engine="openpyxl")
    if sheet_name is None:
        sheet_name = xl.sheet_names[0]  # type: ignore[assignment]
    if dtype is None:
        dtype = str  # Préserver texte par défaut
    df = pd.read_excel(xl, sheet_name=sheet_name, dtype=dtype, engine="openpyxl")
    return df  # type: ignore[return-value]


def save_xlsx(
    filepath: str | Path,
    dataframes: dict[str, pd.DataFrame],
    *,
    preserve_order: bool = True,
) -> None:
    """
    Sauvegarde plusieurs DataFrames dans un fichier xlsx (une feuille par DataFrame).

    Args:
        filepath: Chemin de sortie.
        dataframes: Dict {nom_feuille: DataFrame}.
        preserve_order: Si True, utilise un OrderedDict (Python 3.7+ dict est ordonné).
    """
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, df in dataframes.items():
            # Nettoyer le nom de feuille (Excel limite à 31 caractères)
            safe_name = str(sheet_name)[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)


def load_source_target(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge les DataFrames source et cible selon la configuration.

    Returns:
        (df_source, df_target)
    """
    if config.single_file:
        path = Path(config.single_file)
        df_source = load_sheet(path, config.source_sheet_in_single)
        df_target = load_sheet(path, config.target_sheet_in_single)
    else:
        df_source = load_sheet(config.source_file, config.source_sheet)
        df_target = load_sheet(config.target_file, config.target_sheet)
    return df_source, df_target
