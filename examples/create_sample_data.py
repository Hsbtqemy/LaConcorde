"""Crée des fichiers Excel de démonstration pour ConcordX."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

source = pd.DataFrame({
    "auteur": ["Dupont", "Martin", "Bernard", "Leroy"],
    "titre": ["Introduction à Python", "Méthodes statistiques", "Conclusion", "Data Science"],
    "annee": ["2020", "2021", "2020", "2022"],
    "doi": ["10.1234/abc", "10.5678/xyz", "", "10.9999/ds"],
    "notes": ["Note 1", "Note 2", "Note 3", "Note 4"],
    "categorie": ["Tech", "Stats", "General", "Tech"],
})

target = pd.DataFrame({
    "author": ["Dupont", "Martin", "Durand"],
    "title": ["Introduction à Python", "Methodes statistiques", "Autre ouvrage"],
    "year": ["2020", "2021", "2020"],
    "doi": ["10.1234/abc", "10.5678/xyz", ""],
})

source.to_excel(DATA_DIR / "source.xlsx", index=False, engine="openpyxl")
target.to_excel(DATA_DIR / "target.xlsx", index=False, engine="openpyxl")
print(f"Fichiers créés dans {DATA_DIR}")
