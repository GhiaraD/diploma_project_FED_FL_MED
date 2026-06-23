#!/usr/bin/env python3
"""
Plot resource usage from a performance CSV collected during FL training.
Extended version with per-stage metrics table.

Usage:
    python scripts/plot_performance_Dragos.py storage/node1/performance/resources_fl_15a34d02.csv
    python scripts/plot_performance_Dragos.py storage/node1/performance/resources_fl_15a34d02.csv --out plots/
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.colors as mc

# ── Matplotlib style ──────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "#f8f9fa",
    "axes.grid":        True,
    "grid.color":       "white",
    "grid.linewidth":   1.0,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "font.size":        11,
})

COLORS = {
    "cpu":      "#3498db",   # blue
    "ram":      "#1abc9c",   # teal
    "gpu_util": "#e74c3c",   # red
    "vram":     "#e67e22",   # orange
    "io_read":  "#9b59b6",   # purple
    "io_write": "#f39c12",   # amber
}

# Stage background colors — saturated, clearly distinguishable
STAGE_COLORS = {
    "init":           "#b0bec5",   # blue-grey
    "loading_data":   "#3b82f6",   # bright blue
    "waiting_server": "#10b981",   # emerald green
    "done":           "#b0bec5",   # blue-grey
}

def _stage_color(stage: str) -> str:
    if stage in STAGE_COLORS:
        return STAGE_COLORS[stage]
    if "training" in stage:
        return "#6366f1"   # indigo
    if "evaluating" in stage:
        return "#f43f5e"   # rose red
    if "complete" in stage:
        return "#f59e0b"   # amber
    return "#d5d8dc"       # light grey fallback


def _stage_label(stage: str) -> str:
    """Human-readable label for legend."""
    if stage in ("init", "done", "loading_data", "waiting_server"):
        return stage.replace("_", " ").title()
    if "training" in stage:
        parts = stage.split("_")   # round_1_training
        return f"Round {parts[1]} — Training"
    if "evaluating" in stage:
        parts = stage.split("_")
        return f"Round {parts[1]} — Evaluating"
    if "complete" in stage:
        parts = stage.split("_")
        return f"Round {parts[1]} — Complete"
    return stage


# ── Data loading ──────────────────────────────────────────────────────────────

def load(csv_path: Path, smooth_window: int = 10) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["elapsed_s"] = df["elapsed_s"].astype(float)

    # IO is cumulative — convert to per-interval rate (MB/s)
    interval = df["elapsed_s"].diff().median()
    interval = interval if interval > 0 else 0.1
    df["io_read_rate"]  = df["io_read_mb"].diff().fillna(0).clip(lower=0) / interval
    df["io_write_rate"] = df["io_write_mb"].diff().fillna(0).clip(lower=0) / interval

    if "stage" not in df.columns:
        df["stage"] = "unknown"

    # Smooth noisy metrics with a rolling average (helps at 0.1s sampling)
    if smooth_window > 1 and len(df) > smooth_window:
        for col in ("cpu_percent", "gpu_util_percent", "io_read_rate", "io_write_rate"):
            df[col] = df[col].rolling(window=smooth_window, center=True, min_periods=1).mean()

    return df


# ── Stage shading helper ──────────────────────────────────────────────────────

def _shade_stages(ax, df: pd.DataFrame) -> dict:
    """
    Draw colored background bands for each stage transition.
    Returns {stage: color} dict (unique stages only).
    """
    if df["stage"].eq("unknown").all():
        return {}

    legend_entries = {}
    x = df["elapsed_s"].values
    stages = df["stage"].values

    i = 0
    while i < len(stages):
        stage = stages[i]
        j = i + 1
        while j < len(stages) and stages[j] == stage:
            j += 1
        x_start = x[i]
        x_end   = x[j - 1] if j < len(stages) else x[-1]
        color   = _stage_color(stage)
        ax.axvspan(x_start, x_end, alpha=0.25, color=color, linewidth=0)
        legend_entries[stage] = color
        i = j

    return legend_entries


# ── Per-stage metrics ────────────────────────────────────────────────────────

def _build_stage_metrics(df: pd.DataFrame) -> list[list]:
    """
    Returns table rows with mean CPU, RAM, GPU util, VRAM and duration per stage.
    Ordered by first appearance in the data. Skips 'unknown' stage.
    """
    # Order by first occurrence in the CSV — preserves chronological order
    seen = []
    for s in df["stage"]:
        if s not in seen:
            seen.append(s)

    rows = []
    for stage in seen:
        if stage == "unknown":
            continue
        mask = df["stage"] == stage
        chunk = df[mask]
        duration = chunk["elapsed_s"].max() - chunk["elapsed_s"].min()
        rows.append([
            _stage_label(stage),
            f"{duration:.1f}",
            f"{chunk['cpu_percent'].mean():.1f}",
            f"{chunk['ram_used_mb'].mean():.0f}",
            f"{chunk['gpu_util_percent'].mean():.1f}",
            f"{chunk['vram_used_mb'].mean():.0f}",
        ])
    return rows


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot(df: pd.DataFrame, csv_path: Path, out_dir: Path) -> None:
    job_id = csv_path.stem.replace("resources_", "")
    x = df["elapsed_s"]
    x_label = "Elapsed time (s)"
    has_stages = not df["stage"].eq("unknown").all()

    # 4 rows: row0=CPU+RAM, row1=GPU+VRAM, row2=IO Rate (full width), row3=stage legend
    fig = plt.figure(figsize=(26, 18))
    fig.suptitle(f"Resource usage — {job_id}", fontsize=14, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(
        4, 2, figure=fig,
        height_ratios=[1, 1, 1, 0.45],
        hspace=0.55, wspace=0.35,
    )

    # ── 1. CPU % ──────────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    _shade_stages(ax1, df)
    ax1.plot(x, df["cpu_percent"], color=COLORS["cpu"], linewidth=1.5)
    ax1.fill_between(x, df["cpu_percent"], alpha=0.35, color=COLORS["cpu"])
    ax1.set_title("CPU Usage")
    ax1.set_ylabel("CPU %  (multi-core sum)")
    ax1.set_xlabel(x_label)

    # ── 2. RAM ────────────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    _shade_stages(ax2, df)
    ax2.plot(x, df["ram_used_mb"], color=COLORS["ram"], linewidth=1.5, label="Process RSS")
    ax2.fill_between(x, df["ram_used_mb"], alpha=0.35, color=COLORS["ram"])
    ax2_r = ax2.twinx()
    ax2_r.plot(x, df["ram_system_percent"], color="#e67e22", linewidth=2.0,
               linestyle="--", alpha=0.6, label="System %")
    ax2_r.set_ylabel("System RAM %", color="#e67e22", alpha=0.7)
    ax2_r.tick_params(axis="y", labelcolor="#e67e22")
    ax2.set_title("RAM Usage")
    ax2.set_ylabel("Process RSS (MB)")
    ax2.set_xlabel(x_label)
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="lower right")

    # ── 3. GPU Utilization % ──────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    _shade_stages(ax3, df)
    ax3.plot(x, df["gpu_util_percent"], color=COLORS["gpu_util"], linewidth=1.5)
    ax3.fill_between(x, df["gpu_util_percent"], alpha=0.35, color=COLORS["gpu_util"])
    ax3.set_ylim(0, 105)
    ax3.set_title("GPU Utilization")
    ax3.set_ylabel("GPU %")
    ax3.set_xlabel(x_label)

    # ── 4. VRAM ───────────────────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    _shade_stages(ax4, df)
    ax4.plot(x, df["vram_used_mb"], color=COLORS["vram"], linewidth=1.5, label="Used")
    ax4.axhline(df["vram_total_mb"].iloc[0], color=COLORS["vram"], linewidth=1.0,
                linestyle="--", alpha=0.5,
                label=f"Total ({df['vram_total_mb'].iloc[0]:.0f} MB)")
    ax4.fill_between(x, df["vram_used_mb"], alpha=0.35, color=COLORS["vram"])
    ax4.set_title("VRAM Usage")
    ax4.set_ylabel("VRAM (MB)")
    ax4.set_xlabel(x_label)
    ax4.legend(fontsize=9)

    # ── 5. IO rate (half width, col 0) ───────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 0])
    _shade_stages(ax5, df)
    ax5.plot(x, df["io_read_rate"],  color=COLORS["io_read"],  linewidth=1.5, label="Read")
    ax5.plot(x, df["io_write_rate"], color=COLORS["io_write"], linewidth=1.5, label="Write")
    ax5.fill_between(x, df["io_read_rate"],  alpha=0.35, color=COLORS["io_read"])
    ax5.fill_between(x, df["io_write_rate"], alpha=0.35, color=COLORS["io_write"])
    ax5.set_title("IO Rate (MB/s per interval)")
    ax5.set_ylabel("MB/s")
    ax5.set_xlabel(x_label)
    ax5.legend(fontsize=9)

    # ── 6. Stage legend ───────────────────────────────────────────────────────
    ax_legend = fig.add_subplot(gs[3, :])
    ax_legend.axis("off")
    if has_stages:
        # Order by first appearance in the data
        seen_stages = []
        for s in df["stage"]:
            if s not in seen_stages:
                seen_stages.append(s)
        seen_stages = [s for s in seen_stages if s != "unknown"]

        # Deduplicate by color — one patch per stage type, not per round number
        seen_colors = {}
        for s in seen_stages:
            color = _stage_color(s)
            if color not in seen_colors:
                seen_colors[color] = _stage_label(s)
        # Simplify round labels: strip round number, keep only the type
        def _generic_label(label: str) -> str:
            if "— Training" in label:
                return "Round — Training"
            if "— Evaluating" in label:
                return "Round — Evaluating"
            if "— Complete" in label:
                return "Round — Complete"
            return label
        legend_patches = [
            mpatches.Patch(color=color, alpha=0.7, label=_generic_label(label))
            for color, label in seen_colors.items()
        ]
        if legend_patches:
            ax_legend.legend(
                handles=legend_patches,
                loc="center",
                ncol=min(len(legend_patches), 6),
                fontsize=18,
                framealpha=0.8,
                title="Training stages (background shading)",
                title_fontsize=18,
                handlelength=3.0,
                handleheight=2.0,
            )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"performance_{job_id}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


def plot_stage_table(df: pd.DataFrame, csv_path: Path, out_dir: Path) -> None:
    """Save the per-stage resource averages as a separate PNG."""
    if df["stage"].eq("unknown").all():
        return

    job_id = csv_path.stem.replace("resources_", "")
    stage_rows = _build_stage_metrics(df)
    if not stage_rows:
        return

    stage_cols = ["Stage", "Duration (s)", "Avg CPU %", "Avg RAM (MB)", "Avg GPU %", "Avg VRAM (MB)"]
    n_rows = len(stage_rows)

    # Size: wide enough for 6 columns, tall enough for all rows
    fig_w = max(14, 2.2 * len(stage_cols))
    fig_h = 0.55 * (n_rows + 2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    fig.suptitle(
        f"Per-Stage Resource Averages — {job_id}",
        fontsize=13, fontweight="bold", y=1.02,
    )

    tbl = ax.table(
        cellText=stage_rows,
        colLabels=stage_cols,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 2.0)

    # Header row
    for j in range(len(stage_cols)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # Data rows — tint matching stage color
    for i, row in enumerate(stage_rows, start=1):
        stage_name = row[0]
        match = df[df["stage"].apply(_stage_label) == stage_name]["stage"]
        raw_stage = match.iloc[0] if not match.empty else ""
        base_color = _stage_color(raw_stage) if raw_stage else "#ecf0f1"
        rgb = mc.to_rgb(base_color)
        tint = tuple(0.82 + 0.18 * c for c in rgb)
        for j in range(len(stage_cols)):
            tbl[i, j].set_facecolor(tint)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"stage_metrics_{job_id}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Plot FL node resource usage from CSV")
    parser.add_argument("csv", help="Path to resources_*.csv file")
    parser.add_argument("--out", default=None,
                        help="Output directory (default: same folder as CSV)")
    parser.add_argument("--smooth", type=int, default=10,
                        help="Rolling average window for noisy metrics (default: 10, use 1 to disable)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out) if args.out else csv_path.parent

    df = load(csv_path, smooth_window=args.smooth)
    plot(df, csv_path, out_dir)
    plot_stage_table(df, csv_path, out_dir)


if __name__ == "__main__":
    main()
