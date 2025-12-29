# Academic Program Pathways & Major Transitions (Sankey Analysis)

This project analyzes student movement across academic programs over time and visualizes
entry, persistence, switching, and exit patterns using a Sankey diagram.

The goal is to support academic leadership and program planning by providing a clear,
interpretable view of how students flow through programs across semesters.

---

## What is included
- A reproducible Python pipeline for cleaning and normalizing program history data
- Canonicalization logic to ensure consistent student IDs and program codes
- A Sankey visualization showing:
  - Initial program entry
  - Transitions across semesters
  - Current enrollment vs program exit
- Aggregated, non-sensitive outputs suitable for public sharing

## What is NOT included
Raw student records, identifiers, or institutional exports are **not included**
due to data governance and privacy requirements.

---

## Key Methods
- **Student ID normalization** to preserve continuity across semesters (leading zeros)
- **Program canonicalization** to prevent program “fracturing” from naming inconsistencies
- **Deduplication logic** to ensure one record per student per semester
- **Time-aware ordering** of semesters to accurately reflect longitudinal movement
- **Fixed visual lanes and color encoding** to improve interpretability and reduce visual noise

---

## Key Insights & Interpretation
- The visualization reveals **clear entry-to-program patterns** and highlights where students
  persist versus exit over time.
- Program switching and exit behavior becomes immediately visible when viewed longitudinally,
  supporting discussions around retention and pathway alignment.
- Normalizing identifiers and program codes is critical—without it, transitions (Spring to Fall)
  can be undercounted or misrepresented.

These findings are intended to support **program-level decision-making** and are not used
to evaluate individual students.

---

## Data Ethics
All outputs are aggregated at the program level.
No personally identifiable information (PII) is included in this repository.
