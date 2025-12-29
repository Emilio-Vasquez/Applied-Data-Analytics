# Academia — Applied Analytics in Institutional Contexts

This directory contains applied data analytics projects conducted within an academic institutional setting.  
The work focuses on transforming real-world operational and student data into actionable insights to support
curriculum design, student success initiatives, and institutional decision-making.

All projects emphasize:
- Robust data cleaning and validation for messy, real-world systems
- Statistically responsible analysis (avoiding circular metrics and post-hoc bias)
- Clear, decision-oriented visualizations
- Reproducible Python workflows suitable for operational environments

---

## Projects

### 1. MAT-119 Curriculum & Student Performance Analysis

**Focus:** Curriculum effectiveness, assessment alignment, and student success drivers  

This project analyzes LMS assessment data for a college-level mathematics course (MAT-119) to identify
which instructional components and early learning signals most strongly predict student outcomes.

**Tree Structure:**

```
mat-119-curriculum-analysis/
│
├── README.md
│
├── notebooks/
│   └── analysis.ipynb
│
├── scripts/
│   ├── clean_data.py
│   ├── correlation_analysis.py
│   └── chapter_aggregation.py
│
├── figures/
│   ├── finalscore_top_predictors_bar.png
│   ├── heatmap_top_predictors_spearman.png
│   └── chapter_aggregates_top.png
│
└── outputs/
    ├── chapter_aggregates_summary_hw_quiz.csv
    └── analysis_metadata.txt
```

**Key elements:**
- Cleaning and normalization of noisy LMS exports
- Exclusion of circular grading components (weighted scores, current/unposted grades)
- Spearman and Pearson correlation analysis to assess robustness
- Chapter-level aggregation of homework and quiz performance
- Identification of foundational topic dependencies
- Evidence-based recommendations for curriculum pacing, assessment design, and targeted interventions

**Outcome:**  
Insights from this analysis informed curriculum adjustments and student support strategies aimed at improving pass rates and retention.

---

### 2. Academic Program Pathways & Enrollment Visualization (Sankey Diagram)

**Focus:** Program flow, enrollment distribution, and academic pathways  

This project visualizes student movement and distribution across academic programs using a Sankey diagram.
The goal is to provide administrators and stakeholders with a clear, intuitive view of how students flow
through different programs and pathways over time.

**Tree Structure:**
```
academic-program-pathways/
│
├── README.md
│
├── notebooks/
│   └── pathways_sankey_demo.ipynb
│
├── scripts/
│   └── build_sankey.py
│
├── figures/
│   └── student_major_transitions.png 
│
├── outputs/
│   └── transition_counts.csv
│
├── data/
    └── README.md
```

**Key elements:**
- Aggregation and anonymization of program-level student population data
- Transformation of tabular enrollment data into flow-based structures
- Interactive visualization for high-level decision support
- Emphasis on interpretability over visual complexity

**Outcome:**  
The visualization supports discussions around program growth, pathway optimization, and resource allocation.

---

## Methods & Tools

- **Languages:** Python
- **Libraries:** Pandas, NumPy, Matplotlib, Seaborn
- **Techniques:**  
  - Correlation analysis (Spearman & Pearson)  
  - Feature filtering and data quality thresholds  
  - Aggregation and transformation of assessment data  
  - Visual analytics for decision-makers  

---

## Data Ethics & Privacy

All analyses are performed on aggregated and anonymized data.
No personally identifiable student information is included in this repository.

---

## Scope & Transferability

While these projects originate in an academic context, the analytical approaches are domain-agnostic and
transferable to other sectors such as healthcare, finance, and product analytics—particularly where
messy operational data and decision-driven analysis are required.
