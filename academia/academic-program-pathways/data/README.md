# Data (Not Included)

Raw student program history exports are **not included** in this repository due to institutional
privacy and data governance requirements.

## Expected input format
This project expects one Excel file per term (or multiple sheets per file), where each sheet that contains
the required columns will be processed.

### Required columns (exact or close match after trimming spaces)
- `Student Program Student ID`
- `Program`

### Optional notes
- Student IDs may appear as integers (`440408`) or strings with leading zeros (`0440408`).
  The pipeline normalizes IDs to digits-only and zero-pads to a fixed width.
- Program names/codes may vary across exports. The pipeline canonicalizes known variants to prevent
  program “fracturing.”
