# Template Builder Discussion Notes

Date: 2026-02-09
Context: LaConcorde (GUI) — user wants a configurable template-driven transformation flow.

## Goal
Build a configurable "Template Builder" mode that:
- Ingests a template spreadsheet (ODS/XLSX) describing target structure.
- Lets user map source data columns into that structure (including concatenations).
- Exports a NEW target file (no enrichment of existing file for now).
- Preserves template header/title rows in the output.
- Supports output either as:
  - Single sheet with blocks stacked (primary usage), or
  - One sheet per block (secondary option).

## User Requirements (confirmed)
- Must be configurable, not tied to a single dataset.
- Source data typically has an ID per row (but user wants an option for strict row-order alignment).
- Must support concatenation (ordering, separator, per-field prefixes).
- Concat: prefix must be configurable per aggregated source column.
- Must allow defining a target zone/field that can receive multiple elements, with a user-chosen separator.
- Export should keep the template’s title/header rows (do NOT drop them).
- "Everything must be exportable" (all blocks).
- Choice between "single sheet (stacked blocks)" and "multi-sheet (one per block)"; primary usage is single sheet.

## Current State in Code (already implemented)
- Concat transfers with:
  - per-column prefix
  - per-transfer separator
  - overwrite modes: if_empty / replace / append / prepend
  - join_with_existing separator for append/prepend
- Configurable header row for source/target (Project screen + config).
- Bulk accept respects selection; added "Valider auto" button.
- Strip known file extensions option per rule.

## ODS Sample Reviewed
File: `C:\Users\hsemil01\Documents\IGE\Correspondance datas-mapping.ods`
Sheet: `Feuille1` (11 rows, 46 cols)
Structure observed:
- Row 1: "Fichier Datas" (title)
- Row 2: "Tous les documents" (repeated across columns)
- Row 3: FR/ES human labels (e.g., Cote/Código, Titre/Título)
- Row 4: technical mapping (e.g., dcterms:title, dcterms:creator)
- Rows 5-6: per-field prefixes (FR/ES)
- Row 9: "Fichier Push" (title)
- Rows 10-11: push mapping/labels

## Open Decisions (to confirm)
- Block definitions:
  - "Fichier Datas" block starting at Row 1
  - "Fichier Push" block starting at Row 9
- For each block, which row is the "technical target columns" row?
  - Datas: likely Row 4 (dcterms:*)
  - Push: likely Row 10 or Row 11 (needs decision)
- Data insertion start row per block:
  - "after last header row" vs fixed row number
- Which prefix row to use by default:
  - Row 5 (FR) or Row 6 (ES), or manual
- Concatenation target zones:
  - How to designate a field/zone as multi-value (per target column setting? per block?)
  - Separator selection UI (per target field or per concat mapping)
- Zone delimitation:
  - Support both manual coordinates (row/col start/end) and visual selection
- Header detection:
  - Auto-detect is allowed, but without regex; rely on unique template terms / exact matches
  - Manual override by row numbers remains available
- Multi-line aggregation (optional per zone):
  - Group by an ID column to aggregate multiple source rows
  - Non-concat fields default to first non-empty value
  - Concat fields may optionally deduplicate values (no duplicates) per field
- Output formatting:
  - single sheet (stacked blocks) vs multi-sheet (one block per sheet) — both supported, default to single sheet
  - whether to add block_name column (currently not required)

## Suggested MVP (when implementing)
- Add "Template Builder" mode:
  - Import template sheet
  - Define blocks (start row, end row, header rows)
  - Choose target columns row per block
  - Choose prefix row (optional)
  - Generate mapping UI (reuse concat/transfer logic)
  - Export new file with preserved header/title rows

## Notes
- User clarified: keep template title/header rows in output; ignore was a misunderstanding.
- Primary usage: single sheet with stacked blocks; multi-sheet still needed as option.


## Terminology
- Use term "Zone" (not "Bloc") in UI and config where possible.
