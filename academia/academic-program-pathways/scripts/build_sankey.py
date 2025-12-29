"""
build_sankey.py

Academic Program Pathways & Major Transitions (Sankey)

This script builds a Sankey diagram that visualizes student transitions across programs by term,
including Entry ("Entered") and End buckets ("Current" vs "Exited").

Portfolio-safe design:
- Raw data is never bundled with the repo.
- The script can write aggregated outputs only (transition counts) that are safe to commit.
- All student identifiers are used only transiently in-memory to compute transitions.

Outputs (default):
- outputs/transition_counts.csv  (aggregated source->target counts; no PII)
- outputs/program_pathways_sankey.html (interactive Sankey)
- outputs/metadata.json (run config + basic stats)

Run (example):
python scripts/build_sankey.py --folder data/private_exports --outdir outputs

"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go


# -----------------------------
# CONFIG (reasonable defaults)
# -----------------------------
TERM_RANK = {"SP": 0, "SSI": 1, "SSII": 2, "SU": 1, "FA": 3}

PROGRAM_PRIORITY = {
    "AS.CYBR": 0,
    "AAS.CYBF": 1,
    "AS.DATA": 2,
}

PROGRAM_LANE_Y = {
    "AS.CYBR": 0.32,
    "AAS.CYBF": 0.70,
    "AS.DATA": 0.86,
}

PROGRAM_COLOR = {
    "AS.CYBR":  "rgba(56, 189, 248, 0.85)",   # blue
    "AAS.CYBF": "rgba(251, 146, 60, 0.85)",   # orange
    "AS.DATA":  "rgba(244, 114, 182, 0.85)",  # pink
}
DEFAULT_NODE_COLOR = "rgba(148, 163, 184, 0.7)"

FRIENDLY = {
    "AS.CYBR": "Cybersecurity",
    "AAS.CYBF": "Cyber Forensics",
    "AS.DATA": "Data Science",
}

REQUIRED = {"Student Program Student ID", "Program"}


@dataclass(frozen=True)
class BuildConfig:
    folder: Path
    student_id_width: int = 7
    outdir: Path = Path("outputs")
    html_name: str = "program_pathways_sankey.html"
    counts_name: str = "transition_counts.csv"
    metadata_name: str = "metadata.json"

    # If True, only write aggregated counts + html (recommended for public repo)
    write_only_aggregates: bool = True


# -----------------------------
# Helpers
# -----------------------------
def norm_cols(cols):
    return [re.sub(r"\s+", " ", str(c)).strip() for c in cols]

def semester_key(sem: str):
    m = re.match(r"(\d{4})([A-Z]+)", str(sem).upper())
    if not m:
        return (9999, 99, str(sem))
    year = int(m.group(1))
    term = m.group(2)
    return (year, TERM_RANK.get(term, 50), term)

def extract_semester_from_filename(filename: str) -> str:
    m = re.search(r"(20\d{2})(FA|SP|SSI|SSII|SU)\b", filename.upper())
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return "Unknown"

def _read_any_header(filepath: str, sheet_name=0) -> pd.DataFrame:
    # Try multiple potential header rows (common in institutional exports)
    for hdr in (0, 1, 2, 3):
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=hdr)
        df.columns = norm_cols(df.columns)
        if REQUIRED.issubset(set(df.columns)):
            return df
    raise ValueError(f"Could not find required columns {REQUIRED} in {os.path.basename(filepath)} (sheet={sheet_name})")

def normalize_student_id(series: pd.Series, width: int) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)   # Excel float artifact
    s = s.str.replace(r"[^\d]", "", regex=True)  # digits only
    s = s.str.zfill(width)                        # preserve leading zeros
    return s

def normalize_program(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.upper()
    s = s.replace({
        "AS.CBSC": "AS.CYBR",
        "AS.CYBER": "AS.CYBR",
        "CYBERSECURITY": "AS.CYBR",
        "A.S. CYBERSECURITY": "AS.CYBR",
        "CYBER FORENSICS": "AAS.CYBF",
        "CYBERFORENSICS": "AAS.CYBF",
        "DATA SCIENCE": "AS.DATA",
        "DATASCIENCE": "AS.DATA",
    })
    return s

def fade_rgba(rgba_str: str, alpha: float = 0.22) -> str:
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+)\)", rgba_str)
    if not m:
        return f"rgba(160,160,160,{alpha})"
    r, g, b = m.group(1), m.group(2), m.group(3)
    return f"rgba({r},{g},{b},{alpha})"

def label_semester(lbl: str) -> Optional[str]:
    m = re.match(r"(\d{4}[A-Z]+):", str(lbl))
    return m.group(1) if m else None

def label_program(lbl: str) -> Optional[str]:
    parts = str(lbl).split(": ", 1)
    return parts[1].strip() if len(parts) == 2 else None

def is_program_node(lbl: str) -> bool:
    return isinstance(lbl, str) and re.match(r"^\d{4}[A-Z]+:\s", lbl) is not None

def pretty_node_label(lbl: str, out_totals: Dict[str, int], in_totals: Dict[str, int]) -> str:
    def node_total(x: str) -> int:
        return int(out_totals.get(x, in_totals.get(x, 0)))

    if lbl == "Entered":
        return f"Entered ({node_total(lbl)})"
    if isinstance(lbl, str) and lbl.startswith("Current: "):
        prog = lbl.split(": ", 1)[1]
        return f"Current: {FRIENDLY.get(prog, prog)} ({node_total(lbl)})"
    if isinstance(lbl, str) and lbl.startswith("Exited: "):
        prog = lbl.split(": ", 1)[1]
        return f"Exited: {FRIENDLY.get(prog, prog)} ({node_total(lbl)})"
    if is_program_node(lbl):
        sem = label_semester(lbl)
        prog = label_program(lbl)
        return f"{sem} {FRIENDLY.get(prog, prog)} ({node_total(lbl)})"
    return f"{lbl} ({node_total(lbl)})"


# -----------------------------
# I/O: load + clean
# -----------------------------
def clean_and_extract(filepath: str, student_id_width: int) -> pd.DataFrame:
    semester = extract_semester_from_filename(os.path.basename(filepath))

    xls = pd.ExcelFile(filepath)
    frames = []
    for sh in xls.sheet_names:
        try:
            df = _read_any_header(filepath, sheet_name=sh)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        raise ValueError(f"No valid sheets found in {os.path.basename(filepath)}")

    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"Student Program Student ID": "Student ID"})

    df = df[["Student ID", "Program"]].dropna(subset=["Student ID", "Program"]).copy()
    df["Student ID"] = normalize_student_id(df["Student ID"], student_id_width)
    df["Program"] = normalize_program(df["Program"])
    df["Semester"] = semester
    return df

def merge_semester_files(folder: Path, student_id_width: int) -> pd.DataFrame:
    excel_files = glob.glob(str(folder / "*.xlsx"))
    if not excel_files:
        raise FileNotFoundError(f"No .xlsx files found in: {folder}")

    dfs = []
    for path in excel_files:
        df = clean_and_extract(path, student_id_width)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        raise ValueError("No valid data extracted. Check file formats/columns.")
    master_df = pd.concat(dfs, ignore_index=True)

    # Collapse duplicates: one row per student per semester (use mode)
    master_df = (
        master_df.groupby(["Student ID", "Semester"], as_index=False)["Program"]
        .agg(lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0])
    )
    return master_df


# -----------------------------
# Build transitions + sankey
# -----------------------------
def build_transition_counts(master_df: pd.DataFrame) -> pd.DataFrame:
    master_df_sorted = master_df.sort_values(by=["Student ID", "Semester"], key=lambda s: s.map(semester_key))
    latest_semester = max(master_df["Semester"].dropna().unique().tolist(), key=semester_key)

    transition_data = []
    for student_id, group in master_df_sorted.groupby("Student ID"):
        group = group.sort_values("Semester", key=lambda s: s.map(semester_key))
        semesters = group["Semester"].tolist()
        programs = group["Program"].tolist()

        # Entry
        transition_data.append(("Entered", f"{semesters[0]}: {programs[0]}"))

        # Between semesters
        for i in range(len(semesters) - 1):
            transition_data.append((f"{semesters[i]}: {programs[i]}", f"{semesters[i+1]}: {programs[i+1]}"))

        # End bucket
        final_sem = semesters[-1]
        final_prog = programs[-1]
        end_bucket = "Current" if final_sem == latest_semester else "Exited"
        transition_data.append((f"{final_sem}: {final_prog}", f"{end_bucket}: {final_prog}"))

    transitions_df = pd.DataFrame(transition_data, columns=["source", "target"])
    sankey_data = transitions_df.groupby(["source", "target"]).size().reset_index(name="count")
    return sankey_data

def order_labels(sankey_data: pd.DataFrame) -> List[str]:
    all_node_labels = pd.unique(sankey_data[["source", "target"]].values.ravel()).tolist()
    semesters = sorted({label_semester(l) for l in all_node_labels if label_semester(l)}, key=semester_key)

    end_nodes = [l for l in all_node_labels if isinstance(l, str) and (l.startswith("Current: ") or l.startswith("Exited: "))]

    def end_sort_key(lbl: str):
        bucket, prog = lbl.split(": ", 1)
        bucket_rank = 0 if bucket == "Current" else 1
        return (PROGRAM_PRIORITY.get(prog, 99), bucket_rank, prog)

    end_nodes = sorted(end_nodes, key=end_sort_key)

    labels = ["Entered"]
    for sem in semesters:
        sem_nodes = [l for l in all_node_labels if str(l).startswith(f"{sem}:")]
        sem_nodes = sorted(sem_nodes, key=lambda l: (PROGRAM_PRIORITY.get(label_program(l), 99), label_program(l) or ""))
        labels.extend(sem_nodes)
    labels.extend(end_nodes)
    return labels

def compute_xy(labels: List[str], semesters: List[str]) -> Tuple[List[float], List[float]]:
    # x positions: Entered=0, semester columns spread, End=1
    n_cols = len(semesters) + 2
    col_x = {sem: i / (n_cols - 1) for i, sem in enumerate(semesters, start=1)}
    xpos = [0.5] * len(labels)
    for i, lbl in enumerate(labels):
        if lbl == "Entered":
            xpos[i] = 0.0
        elif isinstance(lbl, str) and (lbl.startswith("Current: ") or lbl.startswith("Exited: ")):
            xpos[i] = 1.0
        else:
            xpos[i] = col_x.get(label_semester(lbl), 0.5)

    # y positions: program lanes (less clumpy)
    ypos = [0.5] * len(labels)
    ypos[labels.index("Entered")] = 0.5

    END_LANE_Y = {"AAS.CYBF": 0.76, "AS.DATA": 0.94}
    END_SPLIT = 0.10

    for i, lbl in enumerate(labels):
        if lbl == "Entered":
            continue
        if isinstance(lbl, str) and (lbl.startswith("Current: ") or lbl.startswith("Exited: ")):
            prog = lbl.split(": ", 1)[1]
            if prog == "AS.CYBR":
                base = PROGRAM_LANE_Y.get(prog, 0.5)
                offset = -0.06 if lbl.startswith("Current: ") else 0.31
                ypos[i] = min(0.98, max(0.02, base + offset))
                continue
            base = END_LANE_Y.get(prog, PROGRAM_LANE_Y.get(prog, 0.5))
            offset = -END_SPLIT / 2 if lbl.startswith("Current: ") else END_SPLIT / 2
            ypos[i] = min(0.98, max(0.02, base + offset))
            continue

        prog = label_program(lbl)
        base = PROGRAM_LANE_Y.get(prog, 0.5)
        ypos[i] = min(0.98, max(0.02, base))

    return xpos, ypos

def build_sankey_figure(sankey_data: pd.DataFrame) -> go.Figure:
    labels = order_labels(sankey_data)
    label_to_index = {label: i for i, label in enumerate(labels)}
    sankey_data = sankey_data.copy()
    sankey_data["source_idx"] = sankey_data["source"].map(label_to_index)
    sankey_data["target_idx"] = sankey_data["target"].map(label_to_index)

    all_node_labels = pd.unique(sankey_data[["source", "target"]].values.ravel()).tolist()
    semesters = sorted({label_semester(l) for l in all_node_labels if label_semester(l)}, key=semester_key)

    xpos, ypos = compute_xy(labels, semesters)

    # Totals for labels
    out_totals = sankey_data.groupby("source")["count"].sum().to_dict()
    in_totals = sankey_data.groupby("target")["count"].sum().to_dict()
    display_labels = [pretty_node_label(l, out_totals, in_totals) for l in labels]

    # Colors
    node_colors = []
    for lbl in labels:
        if lbl == "Entered":
            node_colors.append("rgba(99, 102, 241, 0.85)")
        elif isinstance(lbl, str) and (lbl.startswith("Current: ") or lbl.startswith("Exited: ")):
            prog = lbl.split(": ", 1)[1]
            node_colors.append(PROGRAM_COLOR.get(prog, DEFAULT_NODE_COLOR))
        else:
            node_colors.append(PROGRAM_COLOR.get(label_program(lbl), DEFAULT_NODE_COLOR))

    link_colors = []
    for s_lbl in sankey_data["source"].tolist():
        if s_lbl == "Entered":
            link_colors.append("rgba(160,160,160,0.25)")
            continue
        prog = label_program(s_lbl)
        base = PROGRAM_COLOR.get(prog, "rgba(160,160,160,1)")
        link_colors.append(fade_rgba(base, alpha=0.22))

    fig = go.Figure(data=[go.Sankey(
        arrangement="fixed",
        node=dict(
            pad=30,
            thickness=26,
            line=dict(color="rgba(0,0,0,0.25)", width=0.6),
            label=display_labels,
            color=node_colors,
            x=xpos,
            y=ypos,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sankey_data["source_idx"],
            target=sankey_data["target_idx"],
            value=sankey_data["count"],
            color=link_colors,
            customdata=sankey_data[["source", "target", "count"]],
            hovertemplate="From %{customdata[0]} → %{customdata[1]}: %{customdata[2]} students<extra></extra>",
        )
    )])

    fig.update_layout(
        title_text="Student Major Transitions (with Entry/Exit)",
        font_size=13,
        height=650,
        margin=dict(l=30, r=30, t=60, b=30),
    )
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, type=str, help="Folder containing term .xlsx exports (local only).")
    ap.add_argument("--outdir", default="outputs", type=str)
    ap.add_argument("--student-id-width", default=7, type=int)
    ap.add_argument("--write-only-aggregates", action="store_true", help="Write only aggregated outputs (recommended).")
    args = ap.parse_args()

    cfg = BuildConfig(
        folder=Path(args.folder),
        student_id_width=args.student_id_width,
        outdir=Path(args.outdir),
        write_only_aggregates=True if args.write_only_aggregates else True,
    )

    cfg.outdir.mkdir(parents=True, exist_ok=True)

    master_df = merge_semester_files(cfg.folder, cfg.student_id_width)
    sankey_data = build_transition_counts(master_df)

    # Save aggregated counts (safe to commit)
    counts_path = cfg.outdir / cfg.counts_name
    sankey_data.to_csv(counts_path, index=False)

    # Build + save Sankey HTML
    fig = build_sankey_figure(sankey_data)
    html_path = cfg.outdir / cfg.html_name
    fig.write_html(str(html_path), include_plotlyjs="cdn")

    # Save metadata
    meta = {
        "folder": str(cfg.folder),
        "student_id_width": cfg.student_id_width,
        "rows_in_master_df": int(len(master_df)),
        "unique_students": int(master_df["Student ID"].nunique()),
        "unique_semesters": int(master_df["Semester"].nunique()),
        "unique_programs": int(master_df["Program"].nunique()),
        "counts_rows": int(len(sankey_data)),
        "outputs": {
            "transition_counts_csv": str(counts_path),
            "sankey_html": str(html_path),
        },
        "privacy_note": "Raw data not saved; only aggregated transition counts and visualization exported."
    }
    with open(cfg.outdir / cfg.metadata_name, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("Saved:")
    print(f"- {counts_path}")
    print(f"- {html_path}")
    print(f"- {cfg.outdir / cfg.metadata_name}")


if __name__ == "__main__":
    main()
