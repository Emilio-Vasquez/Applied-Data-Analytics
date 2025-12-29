"""
correlation_analysis.py

Purpose
-------
Compute robust correlations with the final course score using BOTH Spearman and Pearson,
rank by Spearman (more robust for bounded grade data), and generate portfolio-ready plots.

Input
-----
A predictors-only numeric dataset produced by scripts/clean_data.py, containing:
- predictors columns
- FINAL_COL (target)

Output
------
- outputs/finalscore_correlations_predictors_only.csv
- figures/finalscore_top_predictors_bar.png
- figures/heatmap_top_predictors_spearman.png
- outputs/analysis_run_metadata.txt

Privacy
-------
No raw data is written. Only aggregated correlations and plots are saved.
"""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def shorten_label(label: str, width: int = 52) -> str:
    s = re.sub(r"\s*\(\d+\)\s*", "", str(label))  # remove LMS IDs in parentheses
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


def corr_with_final(df: pd.DataFrame, final_col: str, method: str) -> pd.Series:
    c = df.corr(method=method)[final_col].drop(labels=[final_col], errors="ignore")
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="outputs/predictors_only.parquet", type=str)
    ap.add_argument("--final-col", default="Final Score", type=str)
    ap.add_argument("--top-n-bar", default=25, type=int)
    ap.add_argument("--top-n-heatmap", default=12, type=int)
    ap.add_argument("--out-csv", default="outputs/finalscore_correlations_predictors_only.csv", type=str)
    ap.add_argument("--bar-fig", default="figures/finalscore_top_predictors_bar.png", type=str)
    ap.add_argument("--heatmap-fig", default="figures/heatmap_top_predictors_spearman.png", type=str)
    ap.add_argument("--metadata", default="outputs/analysis_run_metadata.txt", type=str)
    args = ap.parse_args()

    df = load_table(Path(args.input))

    if args.final_col not in df.columns:
        raise ValueError(f"final_col='{args.final_col}' not found in input columns.")

    # Spearman + Pearson
    spearman = corr_with_final(df, args.final_col, "spearman")
    pearson = corr_with_final(df, args.final_col, "pearson")

    comparison = pd.DataFrame({"Spearman": spearman, "Pearson": pearson}).dropna()
    comparison["AbsSpearman"] = comparison["Spearman"].abs()
    comparison = comparison.sort_values("AbsSpearman", ascending=False)
    comparison.drop(columns=["AbsSpearman"]).to_csv(args.out_csv)

    # Top bar chart
    top = comparison.head(args.top_n_bar).copy()
    top["Label"] = [shorten_label(c, width=56) for c in top.index]
    top = top.sort_values("Spearman", key=lambda s: s.abs(), ascending=True)

    Path(args.bar_fig).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, max(7, int(args.top_n_bar * 0.38))))
    y = np.arange(len(top))

    plt.barh(y, top["Spearman"].values, alpha=0.9, label="Spearman")
    plt.plot(top["Pearson"].values, y, marker="o", linestyle="None", label="Pearson")
    plt.yticks(y, top["Label"].values)
    plt.axvline(0, linewidth=1)
    plt.xlabel("Correlation with Final Score")
    plt.title(f"Top {args.top_n_bar} Predictor Correlations (Spearman ranked; Pearson shown)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.bar_fig, dpi=300)
    plt.close()

    # Focused heatmap (Spearman)
    top_features = comparison.head(args.top_n_heatmap).index.tolist()
    cols = [args.final_col] + top_features
    corr_focus = df[cols].corr(method="spearman")

    Path(args.heatmap_fig).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10.5, 9))
    sns.heatmap(
        corr_focus,
        cmap="coolwarm",
        center=0,
        square=True,
        linewidths=0.5,
        cbar=True,
        annot=False,
    )

    xlabels = [shorten_label(c, width=28) for c in corr_focus.columns]
    ylabels = [shorten_label(c, width=28) for c in corr_focus.index]
    plt.xticks(ticks=np.arange(len(xlabels)) + 0.5, labels=xlabels, rotation=45, ha="right", fontsize=9)
    plt.yticks(ticks=np.arange(len(ylabels)) + 0.5, labels=ylabels, rotation=0, fontsize=9)

    plt.title(f"Focused Spearman Heatmap (Final Score + Top {args.top_n_heatmap} Predictors)")
    plt.tight_layout()
    plt.savefig(args.heatmap_fig, dpi=300)
    plt.close()

    # Metadata
    Path(args.metadata).parent.mkdir(parents=True, exist_ok=True)
    with open(args.metadata, "w", encoding="utf-8") as f:
        f.write(f"input={args.input}\n")
        f.write(f"final_col={args.final_col}\n")
        f.write(f"top_n_bar={args.top_n_bar}\n")
        f.write(f"top_n_heatmap={args.top_n_heatmap}\n")
        f.write("\nNotes:\n")
        f.write("- Input is predictors-only (circular metrics excluded in clean_data.py)\n")
        f.write("- Spearman used for ranking due to bounded/non-linear grade distributions\n")

    print("Saved outputs:")
    print(f"- {args.out_csv}")
    print(f"- {args.bar_fig}")
    print(f"- {args.heatmap_fig}")
    print(f"- {args.metadata}")


if __name__ == "__main__":
    main()
