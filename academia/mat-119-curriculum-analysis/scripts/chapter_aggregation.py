"""
chapter_aggregation.py

Purpose
-------
Aggregate chapter-level Homework and Quiz performance (mean across sub-assignments),
then correlate these aggregates with Final Score using Spearman + Pearson.

Why this matters
----------------
- Reduces feature noise and "too-many-columns" issues in LMS exports
- Produces interpretable, curriculum-aligned signals ("Chapter 1.2 HW Avg")
- Supports decision-making (pacing, remediation, assessment alignment)

Input
-----
Predictors-only numeric dataset from clean_data.py, containing FINAL_COL and assessment columns.

Output
------
- outputs/chapter_aggregates_summary_hw_quiz.csv
- figures/chapter_aggregates_top.png
"""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def shorten_label(label: str, width: int = 52) -> str:
    s = re.sub(r"\s*\(\d+\)\s*", "", str(label))
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= width:
        return s
    return textwrap.shorten(s, width=width, placeholder="…")


def load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing input: {path}\n"
            "This repo does not include raw data. Generate this file locally via clean_data.py."
        )
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    raise ValueError("Input must be .csv or .parquet")


def parse_chapter(col_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract chapter token and type from a column name.
    Returns: (chapter, typ) where typ in {"HW","Quiz","Videos","Other"}.
    """
    m = re.search(r"(?:Chapter|Chap\.?)\s*([0-9]+(?:\.[0-9]+)?)", str(col_name), flags=re.IGNORECASE)
    if not m:
        return None, None
    chap = m.group(1)

    if re.search(r"\bHW\b|Homework", str(col_name), re.IGNORECASE):
        typ = "HW"
    elif re.search(r"\bQuiz\b", str(col_name), re.IGNORECASE):
        typ = "Quiz"
    elif re.search(r"\bVideos?\b", str(col_name), re.IGNORECASE):
        typ = "Videos"
    else:
        typ = "Other"
    return chap, typ


def corr_with_final(df: pd.DataFrame, final_col: str, method: str) -> pd.Series:
    return df.corr(method=method)[final_col].drop(labels=[final_col], errors="ignore")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="outputs/predictors_only.parquet", type=str)
    ap.add_argument("--final-col", default="Final Score", type=str)
    ap.add_argument("--out-csv", default="outputs/chapter_aggregates_summary_hw_quiz.csv", type=str)
    ap.add_argument("--fig", default="figures/chapter_aggregates_top.png", type=str)
    ap.add_argument("--top-n", default=20, type=int)
    args = ap.parse_args()

    df = load_table(Path(args.input))

    if args.final_col not in df.columns:
        raise ValueError(f"final_col='{args.final_col}' not found in input columns.")

    # Build mapping: chapter -> type -> list of columns
    chapter_map: Dict[str, Dict[str, List[str]]] = {}
    for col in df.columns:
        if col == args.final_col:
            continue
        chap, typ = parse_chapter(col)
        if chap is None or typ is None:
            continue
        if typ not in ("HW", "Quiz"):
            continue
        chapter_map.setdefault(chap, {}).setdefault(typ, []).append(col)

    # Create aggregated features
    chapter_features = pd.DataFrame(index=df.index)
    for chap, typ_map in chapter_map.items():
        if "HW" in typ_map and len(typ_map["HW"]) > 0:
            chapter_features[f"Chapter {chap} HW Avg"] = df[typ_map["HW"]].mean(axis=1)
        if "Quiz" in typ_map and len(typ_map["Quiz"]) > 0:
            chapter_features[f"Chapter {chap} Quiz Avg"] = df[typ_map["Quiz"]].mean(axis=1)

    chapter_features[args.final_col] = df[args.final_col]

    # Correlate aggregates
    s = corr_with_final(chapter_features, args.final_col, "spearman")
    p = corr_with_final(chapter_features, args.final_col, "pearson")

    summary = pd.DataFrame({
        "Feature": s.index,
        "Spearman": s.values,
        "Pearson": p.reindex(s.index).values,
    })
    summary["AbsSpearman"] = summary["Spearman"].abs()
    summary = summary.sort_values("AbsSpearman", ascending=False).drop(columns=["AbsSpearman"])

    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out_csv, index=False)

    # Plot top N
    top_n = min(args.top_n, len(summary))
    top = summary.head(top_n).copy()

    Path(args.fig).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, max(7, int(top_n * 0.40))))
    y = np.arange(len(top))

    plt.barh(y, top["Spearman"].values, alpha=0.9, label="Spearman")
    plt.plot(top["Pearson"].values, y, marker="o", linestyle="None", label="Pearson")

    plt.yticks(y, [shorten_label(f, width=56) for f in top["Feature"]])
    plt.axvline(0, linewidth=1)
    plt.xlabel("Correlation with Final Score")
    plt.title("Top Chapter Aggregate Correlations (HW vs Quiz)\n(Spearman ranked; Pearson shown)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.fig, dpi=300)
    plt.close()

    print("Saved:")
    print(f"- {args.out_csv}")
    print(f"- {args.fig}")


if __name__ == "__main__":
    main()
