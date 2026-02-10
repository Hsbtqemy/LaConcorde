"""I/O tableurs : chargement et sauvegarde (Excel, ODS, CSV)."""

from __future__ import annotations

from pathlib import Path
import csv

import pandas as pd

from laconcorde.config import Config, LaConcordeError


# Formats supportés
SUPPORTED_INPUT_EXTENSIONS = (".xlsx", ".xls", ".ods", ".csv")
SUPPORTED_INPUT_FILTER = "Tableurs (*.xlsx *.xls *.ods *.csv);;Excel (*.xlsx *.xls);;ODS (*.ods);;CSV (*.csv);;Tous (*.*)"


class ExcelFileError(LaConcordeError):
    """Erreur de chargement d'un fichier (fichier absent, feuille inexistante)."""


def _get_engine(path: Path) -> str | None:
    """Retourne le moteur pandas selon l'extension, ou None pour auto."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "openpyxl"
    if suffix == ".xls":
        return "xlrd"
    if suffix in (".ods", ".odt"):
        return "odf"
    if suffix == ".xlsb":
        return "pyxlsb"
    return None


def _is_csv(path: Path) -> bool:
    return path.suffix.lower() == ".csv"


def _detect_csv_delimiter(path: Path, encoding: str, *, skip_rows: int = 0) -> str | None:
    try:
        with path.open("r", encoding=encoding, errors="replace") as f:
            for _ in range(skip_rows):
                if f.readline() == "":
                    return None
            sample_lines: list[str] = []
            for line in f:
                if line.strip() == "":
                    continue
                sample_lines.append(line)
                if len(sample_lines) >= 5:
                    break
        if not sample_lines:
            return None
        sample = "".join(sample_lines)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
            return dialect.delimiter
        except Exception:
            first = sample_lines[0]
            counts = {d: first.count(d) for d in [",", ";", "\t", "|"]}
            best = max(counts, key=counts.get)
            return best if counts[best] > 0 else None
    except Exception:
        return None


def list_sheets(filepath: str | Path) -> list[str]:
    """
    Liste les noms des feuilles d'un fichier tableur.

    Formats supportés : .xlsx, .xls, .ods, .csv (une seule "feuille" pour CSV).

    Args:
        filepath: Chemin vers le fichier.

    Returns:
        Liste des noms de feuilles.

    Raises:
        ExcelFileError: Si le fichier est absent ou illisible.
    """
    path = Path(filepath)
    if not path.exists():
        raise ExcelFileError(f"Fichier introuvable: {path}")
    if _is_csv(path):
        return ["(données)"]
    try:
        engine = _get_engine(path)
        xl = pd.ExcelFile(path, engine=engine) if engine else pd.ExcelFile(path)
        return list(xl.sheet_names)  # type: ignore[return-value]
    except ImportError as e:
        ext = path.suffix.lower()
        if ext == ".xls":
            raise ExcelFileError(
                f"Format .xls requis: pip install xlrd. Détail: {e}"
            ) from e
        if ext in (".ods", ".odt"):
            raise ExcelFileError(
                f"Format ODS requis: pip install odfpy. Détail: {e}"
            ) from e
        raise ExcelFileError(f"Impossible de lire {path}: {e}") from e
    except Exception as e:
        raise ExcelFileError(f"Impossible de lire le fichier {path}: {e}") from e


def load_sheet(
    filepath: str | Path,
    sheet_name: str | None = None,
    *,
    dtype: type | dict[str, type] | None = None,
    header_row: int = 1,
) -> pd.DataFrame:
    """
    Charge une feuille dans un DataFrame en préservant le texte.

    Formats supportés : .xlsx, .xls, .ods, .csv.

    Args:
        filepath: Chemin vers le fichier.
        sheet_name: Nom de la feuille (None = première). Ignoré pour CSV.
        dtype: Types de colonnes (None = str pour tout).
        header_row: Numéro de ligne (1-based) contenant les en-têtes.

    Returns:
        DataFrame chargé.

    Raises:
        ExcelFileError: Si le fichier est absent, illisible ou si la feuille n'existe pas.
    """
    path = Path(filepath)
    if not path.exists():
        raise ExcelFileError(f"Fichier introuvable: {path}")

    header_idx = max(header_row - 1, 0)
    if _is_csv(path):
        def _read_csv(
            encoding: str,
            *,
            header: int | None,
            skiprows: range | None = None,
            engine: str | None = None,
            sep: str | None = None,
            on_bad_lines: str | None = None,
        ) -> pd.DataFrame:
            kwargs: dict[str, object] = {
                "dtype": dtype or str,
                "encoding": encoding,
                "header": header,
                "skiprows": skiprows,
                "engine": engine,
                "sep": sep,
            }
            if on_bad_lines is not None:
                kwargs["on_bad_lines"] = on_bad_lines
            return pd.read_csv(path, **kwargs)

        base_skip = range(header_idx) if header_idx > 0 else None
        header_arg = 0 if header_idx > 0 else header_idx
        try:
            delimiter = _detect_csv_delimiter(path, "utf-8", skip_rows=header_idx) or ","
            return _read_csv("utf-8", header=header_arg, skiprows=base_skip, sep=delimiter)
        except UnicodeDecodeError:
            try:
                delimiter = _detect_csv_delimiter(path, "latin-1", skip_rows=header_idx) or ","
                return _read_csv("latin-1", header=header_arg, skiprows=base_skip, sep=delimiter)
            except Exception as e:
                raise ExcelFileError(f"Erreur CSV {path}: {e}") from e
        except pd.errors.ParserError:
            # Si la première ligne ne contient pas de séparateur, réessaie en la sautant.
            if header_idx == 0:
                try:
                    delimiter = _detect_csv_delimiter(path, "utf-8", skip_rows=1) or ","
                    return _read_csv("utf-8", header=0, skiprows=range(1), sep=delimiter)
                except UnicodeDecodeError:
                    try:
                        delimiter = _detect_csv_delimiter(path, "latin-1", skip_rows=1) or ","
                        return _read_csv("latin-1", header=0, skiprows=range(1), sep=delimiter)
                    except Exception:
                        pass
                except Exception:
                    pass
            # Fallback avec moteur python + détection du séparateur + lignes invalides ignorées.
            try:
                delimiter = _detect_csv_delimiter(path, "utf-8", skip_rows=header_idx) or ","
                return _read_csv(
                    "utf-8",
                    header=header_arg,
                    skiprows=base_skip,
                    engine="python",
                    sep=delimiter,
                    on_bad_lines="warn",
                )
            except UnicodeDecodeError:
                try:
                    delimiter = _detect_csv_delimiter(path, "latin-1", skip_rows=header_idx) or ","
                    return _read_csv(
                        "latin-1",
                        header=header_arg,
                        skiprows=base_skip,
                        engine="python",
                        sep=delimiter,
                        on_bad_lines="warn",
                    )
                except Exception as e:
                    raise ExcelFileError(
                        f"Erreur CSV {path}: {e}. Vérifiez la ligne d'en-tête et le séparateur."
                    ) from e
            except Exception as e:
                raise ExcelFileError(
                    f"Erreur CSV {path}: {e}. Vérifiez la ligne d'en-tête et le séparateur."
                ) from e
        except Exception as e:
            raise ExcelFileError(f"Erreur CSV {path}: {e}") from e

    try:
        engine = _get_engine(path)
        xl = pd.ExcelFile(path, engine=engine) if engine else pd.ExcelFile(path)
    except ImportError as e:
        ext = path.suffix.lower()
        if ext == ".xls":
            raise ExcelFileError(f"Format .xls requis: pip install xlrd") from e
        if ext in (".ods", ".odt"):
            raise ExcelFileError(f"Format ODS requis: pip install odfpy") from e
        raise ExcelFileError(f"Impossible de lire {path}: {e}") from e
    except Exception as e:
        raise ExcelFileError(f"Impossible de lire le fichier {path}: {e}") from e

    if sheet_name is None:
        sheet_name = xl.sheet_names[0]  # type: ignore[assignment]
    elif sheet_name not in xl.sheet_names:
        sheets = [str(s) for s in xl.sheet_names]
        raise ExcelFileError(
            f"Feuille '{sheet_name}' introuvable dans {path}. Feuilles: {', '.join(sheets)}"
        )

    if dtype is None:
        dtype = str
    try:
        read_engine = engine if engine else "openpyxl"
        df = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            dtype=dtype,
            engine=read_engine,
            header=header_idx,
        )
        return df  # type: ignore[return-value]
    except Exception as e:
        raise ExcelFileError(f"Erreur feuille '{sheet_name}' dans {path}: {e}") from e


def load_sheet_raw(
    filepath: str | Path,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    """
    Charge une feuille sans en-têtes (toutes les cellules, index/colonnes numériques).

    Formats supportés : .xlsx, .xls, .ods, .csv.
    """
    path = Path(filepath)
    if not path.exists():
        raise ExcelFileError(f"Fichier introuvable: {path}")

    if _is_csv(path):
        def _read_csv(
            encoding: str,
            *,
            engine: str | None = None,
            sep: str | None = None,
            on_bad_lines: str | None = None,
        ) -> pd.DataFrame:
            kwargs: dict[str, object] = {
                "dtype": str,
                "encoding": encoding,
                "header": None,
                "engine": engine,
                "sep": sep,
            }
            if on_bad_lines is not None:
                kwargs["on_bad_lines"] = on_bad_lines
            return pd.read_csv(path, **kwargs)

        try:
            delimiter = _detect_csv_delimiter(path, "utf-8") or ","
            return _read_csv("utf-8", sep=delimiter)
        except UnicodeDecodeError:
            try:
                delimiter = _detect_csv_delimiter(path, "latin-1") or ","
                return _read_csv("latin-1", sep=delimiter)
            except Exception as e:
                raise ExcelFileError(f"Erreur CSV {path}: {e}") from e
        except pd.errors.ParserError:
            try:
                delimiter = _detect_csv_delimiter(path, "utf-8") or ","
                return _read_csv("utf-8", engine="python", sep=delimiter, on_bad_lines="warn")
            except UnicodeDecodeError:
                try:
                    delimiter = _detect_csv_delimiter(path, "latin-1") or ","
                    return _read_csv("latin-1", engine="python", sep=delimiter, on_bad_lines="warn")
                except Exception as e:
                    raise ExcelFileError(
                        f"Erreur CSV {path}: {e}. Vérifiez le séparateur."
                    ) from e
            except Exception as e:
                raise ExcelFileError(f"Erreur CSV {path}: {e}. Vérifiez le séparateur.") from e
        except Exception as e:
            raise ExcelFileError(f"Erreur CSV {path}: {e}") from e

    try:
        engine = _get_engine(path)
        xl = pd.ExcelFile(path, engine=engine) if engine else pd.ExcelFile(path)
    except ImportError as e:
        ext = path.suffix.lower()
        if ext == ".xls":
            raise ExcelFileError(f"Format .xls requis: pip install xlrd") from e
        if ext in (".ods", ".odt"):
            raise ExcelFileError(f"Format ODS requis: pip install odfpy") from e
        raise ExcelFileError(f"Impossible de lire {path}: {e}") from e
    except Exception as e:
        raise ExcelFileError(f"Impossible de lire le fichier {path}: {e}") from e

    if sheet_name is None:
        sheet_name = xl.sheet_names[0]  # type: ignore[assignment]
    elif sheet_name not in xl.sheet_names:
        sheets = [str(s) for s in xl.sheet_names]
        raise ExcelFileError(
            f"Feuille '{sheet_name}' introuvable dans {path}. Feuilles: {', '.join(sheets)}"
        )

    try:
        read_engine = engine if engine else "openpyxl"
        df = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            dtype=str,
            engine=read_engine,
            header=None,
        )
        return df  # type: ignore[return-value]
    except Exception as e:
        raise ExcelFileError(f"Erreur feuille '{sheet_name}' dans {path}: {e}") from e


def save_xlsx(
    filepath: str | Path,
    dataframes: dict[str, pd.DataFrame],
    *,
    preserve_order: bool = True,
    header: bool = True,
    index: bool = False,
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
            df.to_excel(writer, sheet_name=safe_name, index=index, header=header)


def save_spreadsheet(
    filepath: str | Path,
    dataframes: dict[str, pd.DataFrame],
    *,
    preserve_order: bool = True,
    header: bool = True,
    index: bool = False,
) -> None:
    """
    Sauvegarde plusieurs DataFrames dans un fichier xlsx ou ods.

    Args:
        filepath: Chemin de sortie (.xlsx ou .ods).
        dataframes: Dict {nom_feuille: DataFrame}.
        preserve_order: Si True, utilise un OrderedDict (Python 3.7+ dict est ordonné).
    """
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".ods":
        engine = "odf"
    elif suffix == ".xlsx":
        engine = "openpyxl"
    else:
        raise ExcelFileError(f"Format de sortie non supporté: {suffix}")

    with pd.ExcelWriter(path, engine=engine) as writer:
        for sheet_name, df in dataframes.items():
            safe_name = str(sheet_name)[:31]
            df.to_excel(writer, sheet_name=safe_name, index=index, header=header)


def load_source_target(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge les DataFrames source et cible selon la configuration.

    Returns:
        (df_source, df_target)
    """
    if config.single_file:
        path = Path(config.single_file)
        df_source = load_sheet(
            path,
            config.source_sheet_in_single,
            header_row=config.source_header_row,
        )
        df_target = load_sheet(
            path,
            config.target_sheet_in_single,
            header_row=config.target_header_row,
        )
    else:
        df_source = load_sheet(
            config.source_file,
            config.source_sheet,
            header_row=config.source_header_row,
        )
        df_target = load_sheet(
            config.target_file,
            config.target_sheet,
            header_row=config.target_header_row,
        )
    return df_source, df_target
