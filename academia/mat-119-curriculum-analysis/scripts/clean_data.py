"""
clean_data.py

Purpose
-------
Sanitize and prepare LMS-exported assessment data for analysis WITHOUT shipping any raw data.
This module is designed to be portfolio-safe: it documents methods and provides a reproducible
pipeline, while requiring the user to supply their own local dataset.

Key behaviors
-------------
- Coerces messy LMS columns to numeric (strings like "(read only)..." become NaN)
- Drops sparse columns AFTER coercion (avoids keeping non-null garbage strings)
- Excludes circular/post-hoc grading proxies ("Current Score", weighted category scores)
- Produces a cleaned dataframe suitable for downstream correlation and chapter aggregation

Usage
-----
python clean_data.py --input path/to/local_export.csv --out outputs/clean_numeric.parquet

Notes on privacy
----------------
Do NOT commit raw inputs to git. Add data/ to .gitignore.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Pattern, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CleanConfig:
    final_col: str = "Final Score"
    id_cols: Sequence[str] = ("ID", "SIS User ID")
    min_valid_frac: float = 0.50  # keep columns with >=50% valid numeric values after coercion

    # Regex patterns to EXCLUDE circular / post-hoc grade components from predictor feature space.
    # Tune these to match your Canvas/LMS export naming.
    exclude_patterns: Sequence[str] = (
        r"\bcurrent score\b",
        r"\bunposted\b",
        r"\bweighted\b",
        r"\bcategory\b",
        r"\bfinal exam\b.*\bfinal score\b",
        r"\bmidterm\b.*\bfinal score\b",
        r"\bwebassign\b.*\bfinal score\b",
        r"\battendance\b.*\bfinal score\b",
        r"\bhomework\b.*\bfinal score\b",
        r"\bquiz(?:zes)?\b.*\bfinal score\b",
        r"\b\(\s*\d+%\s*\)\b.*\bfinal score\b",  # "(25%) Final Score" style
        r"\b\(\s*\d+%\s*\)\b.*\bcurrent score\b",
        r"\b\(\s*\d+%\s*\)\b.*\bunposted\b",
    )


def load_table(path: Path) -> pd.DataFrame:
    """Load a local LMS export. Supports CSV/XLSX/Parquet."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}\n"
            "Raw data is intentionally NOT included in the repository. "
            "Provide your own local export path."
        )

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use .csv, .xlsx, or .parquet.")


def compile_patterns(patterns: Sequence[str]) -> List[Pattern[str]]:
    return [re.compile(p, flags=re.IGNORECASE) for p in patterns]


def should_exclude(col: str, *, final_col: str, id_cols: Sequence[str], pats: List[Pattern[str]]) -> bool:
    if col == final_col:
        return False
    if col in id_cols:
        return True
    c = str(col).strip()
    for p in pats:
        if p.search(c):
            return True
    return False


def coerce_numeric(df: pd.DataFrame, *, final_col: str, id_cols: Sequence[str]) -> pd.DataFrame:
    """
    Coerce all non-ID columns to numeric. Non-numeric artifacts become NaN.
    This prevents correlation computation from failing on LMS string artifacts.
    """
    out = df.copy()
    for col in out.columns:
        if col in id_cols:
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce")
    # Ensure final_col exists and is numeric
    if final_col not in out.columns:
        raise ValueError(f"Expected final_col='{final_col}' not found in data columns.")
    out[final_col] = pd.to_numeric(out[final_col], errors="coerce")
    return out


def drop_sparse(df: pd.DataFrame, *, min_valid_frac: float, keep: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """Drop columns with too few numeric (non-null) values."""
    keep = set(keep or [])
    thresh = int(len(df) * min_valid_frac)
    cols = []
    for c in df.columns:
        if c in keep:
            cols.append(c)
            continue
        if df[c].notna().sum() >= thresh:
            cols.append(c)
    return df.loc[:, cols]


def clean_lms_export(raw: pd.DataFrame, cfg: CleanConfig) -> pd.DataFrame:
    """
    Main cleaning function.
    Returns a numeric-only dataframe appropriate for correlation analysis and aggregation.
    """
    df = raw.copy()

    # 1) Coerce to numeric first (critical ordering)
    df = coerce_numeric(df, final_col=cfg.final_col, id_cols=cfg.id_cols)

    # 2) Fill missing target (optional; keeps corr stable)
    df[cfg.final_col] = df[cfg.final_col].fillna(df[cfg.final_col].mean())

    # 3) Drop sparse columns after coercion
    df = drop_sparse(df, min_valid_frac=cfg.min_valid_frac, keep=[cfg.final_col])

    # 4) Drop IDs (never used for modeling/correlation)
    df = df.drop(columns=[c for c in cfg.id_cols if c in df.columns], errors="ignore")

    return df


def build_predictor_view(df_numeric: pd.DataFrame, cfg: CleanConfig) -> pd.DataFrame:
    """
    Return a 'predictors-only' view (plus FINAL_COL) excluding circular/proxy grading metrics.
    """
    pats = compile_patterns(cfg.exclude_patterns)
    predictor_cols = [c for c in df_numeric.columns if not should_exclude(c, final_col=cfg.final_col, id_cols=cfg.id_cols, pats=pats)]
    predictor_cols = [c for c in predictor_cols if c != cfg.final_col]
    if len(predictor_cols) < 5:
        raise ValueError(
            "Too few predictor columns after exclusions. "
            "Adjust exclude_patterns in CleanConfig to match your dataset."
        )
    return df_numeric[predictor_cols + [cfg.final_col]].copy()


def save_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
    elif suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        raise ValueError("Output must be .csv or .parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=str, help="Path to local LMS export (.csv/.xlsx/.parquet).")
    ap.add_argument("--out", default="outputs/clean_numeric.parquet", type=str, help="Output file (.csv or .parquet).")
    ap.add_argument("--predictors-out", default="outputs/predictors_only.parquet", type=str, help="Predictor-only output (.csv or .parquet).")
    ap.add_argument("--final-col", default="Final Score", type=str)
    ap.add_argument("--min-valid-frac", default=0.50, type=float)
    args = ap.parse_args()

    cfg = CleanConfig(final_col=args.final_col, min_valid_frac=args.min_valid_frac)

    raw = load_table(Path(args.input))
    clean = clean_lms_export(raw, cfg)
    preds = build_predictor_view(clean, cfg)

    save_table(clean, Path(args.out))
    save_table(preds, Path(args.predictors_out))

    print("Saved:")
    print(f"- {args.out}")
    print(f"- {args.predictors_out}")


if __name__ == "__main__":
    main()
