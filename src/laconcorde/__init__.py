"""LaConcorde - Outil de concordance entre tableurs Excel."""

from laconcorde.config import ConfigError, ConfigFileError, LaConcordeError
from laconcorde.io_excel import ExcelFileError

__all__ = [
    "__version__",
    "LaConcordeError",
    "ConfigError",
    "ConfigFileError",
    "ExcelFileError",
]

__version__ = "0.1.0"
