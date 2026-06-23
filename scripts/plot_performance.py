#!/usr/bin/env python3
"""
Plot resource usage from a performance CSV collected during FL training.

Usage:
    python scripts/plot_performance.py storage/node1/performance/resources_fl_15a34d02.csv
    python scripts/plot_performance.py storage/node1/performance/resources_fl_15a34d02.csv --out plots/
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches

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
    "cpu":      "#e74c3c",
    "ram":      "#3498db",
    "gpu_util": "#2ecc71",
    "vram":     "#9b59b6",
    "io_read":  "#f39c12",
    "io_write": "#e67e22",
}

# Stage background colors — saturated, clearly distinguishable
STAGE_COLORS = {
    "init":           "#95a5a6",   # medium grey
    "loading_data":   "#e67e22",   # strong orange
    "waiting_server": "#2980b9",   # strong blue
    "done":           "#95a5a6",   # medium grey
}

def _stage_color(stage: str) -> str:
    if stage in STAGE_COLORS:
        return STAGE_COLORS[stage]
    if "training" in stage:
        return "#27ae60"   # strong green
    if "evaluating" in stage:
        return "#8e44ad"   # strong purple
    if "complete" in stage:
        return "#16a085"   # strong teal
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
        ax.axvspan(x_start, x_end, alpha=0.22, color=color, linewidth=0)
        legend_entries[stage] = color
        i = j

    return legend_entries


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot(df: pd.DataFrame, csv_path: Path, out_dir: Path) -> None:
    job_id = csv_path.stem.replace("resources_", "")
    x = df["elapsed_s"]
    x_label = "Elapsed time (s)"
    has_stages = not df["stage"].eq("unknown").all()

    # 5 rows: 3 for charts (2 cols each), 1 for stage legend, 1 for table
    fig = plt.figure(figsize=(14, 22))
    fig.suptitle(f"Resource usage — {job_id}", fontsize=14, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(
        5, 2, figure=fig,
        height_ratios=[1, 1, 1, 0.15, 0.9],
        hspace=0.55, wspace=0.35,
    )

    # ── 1. CPU % ──────────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    _shade_stages(ax1, df)
    ax1.plot(x, df["cpu_percent"], color=COLORS["cpu"], linewidth=1.5)
    ax1.fill_between(x, df["cpu_percent"], alpha=0.15, color=COLORS["cpu"])
    ax1.set_title("CPU Usage")
    ax1.set_ylabel("CPU %  (multi-core sum)")
    ax1.set_xlabel(x_label)

    # ── 2. RAM ────────────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    _shade_stages(ax2, df)
    ax2.plot(x, df["ram_used_mb"], color=COLORS["ram"], linewidth=1.5, label="Process RSS")
    ax2.fill_between(x, df["ram_used_mb"], alpha=0.15, color=COLORS["ram"])
    ax2_r = ax2.twinx()
    ax2_r.plot(x, df["ram_system_percent"], color=COLORS["ram"], linewidth=1.0,
               linestyle="--", alpha=0.6, label="System %")
    ax2_r.set_ylabel("System RAM %", color=COLORS["ram"], alpha=0.7)
    ax2_r.tick_params(axis="y", labelcolor=COLORS["ram"])
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
    ax3.fill_between(x, df["gpu_util_percent"], alpha=0.15, color=COLORS["gpu_util"])
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
    ax4.fill_between(x, df["vram_used_mb"], alpha=0.15, color=COLORS["vram"])
    ax4.set_title("VRAM Usage")
    ax4.set_ylabel("VRAM (MB)")
    ax4.set_xlabel(x_label)
    ax4.legend(fontsize=9)

    # ── 5. IO rate ────────────────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 0])
    _shade_stages(ax5, df)
    ax5.plot(x, df["io_read_rate"],  color=COLORS["io_read"],  linewidth=1.5, label="Read")
    ax5.plot(x, df["io_write_rate"], color=COLORS["io_write"], linewidth=1.5, label="Write")
    ax5.fill_between(x, df["io_read_rate"],  alpha=0.12, color=COLORS["io_read"])
    ax5.fill_between(x, df["io_write_rate"], alpha=0.12, color=COLORS["io_write"])
    ax5.set_title("IO Rate (MB/s per interval)")
    ax5.set_ylabel("MB/s")
    ax5.set_xlabel(x_label)
    ax5.legend(fontsize=9)

    # ── 6. IO cumulative ──────────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, 1])
    _shade_stages(ax6, df)
    ax6.plot(x, df["io_read_mb"],  color=COLORS["io_read"],  linewidth=1.5, label="Read (cumul.)")
    ax6.plot(x, df["io_write_mb"], color=COLORS["io_write"], linewidth=1.5, label="Write (cumul.)")
    ax6.set_title("IO Cumulative")
    ax6.set_ylabel("MB")
    ax6.set_xlabel(x_label)
    ax6.legend(fontsize=9)

    # ── 7. Stage legend — dedicated row between charts and table ──────────────
    ax_legend = fig.add_subplot(gs[3, :])
    ax_legend.axis("off")
    if has_stages:
        all_stages = [s for s in sorted(df["stage"].unique()) if s != "unknown"]
        legend_patches = [
            mpatches.Patch(color=_stage_color(s), alpha=0.7, label=_stage_label(s))
            for s in all_stages
        ]
        if legend_patches:
            ax_legend.legend(
                handles=legend_patches,
                loc="center",
                ncol=min(len(legend_patches), 6),
                fontsize=9,
                framealpha=0.8,
                title="Training stages (background shading)",
                title_fontsize=9,
                handlelength=1.5,
            )

    # ── 8. Summary stats table ────────────────────────────────────────────────
    ax7 = fig.add_subplot(gs[4, :])
    ax7.axis("off")

    # Title as figure text, positioned just above the table subplot
    bbox = ax7.get_position()
    fig.text(
        bbox.x0 + bbox.width / 2,
        bbox.y1 + 0.005,
        "Summary Statistics",
        ha="center", va="bottom",
        fontsize=11, fontweight="bold",
        transform=fig.transFigure,
    )

    cols = ["Metric", "Min", "Max", "Mean", "Final"]
    rows = [
        ["CPU %",
         f"{df['cpu_percent'].min():.1f}",
         f"{df['cpu_percent'].max():.1f}",
         f"{df['cpu_percent'].mean():.1f}", "—"],
        ["RAM (MB)",
         f"{df['ram_used_mb'].min():.0f}",
         f"{df['ram_used_mb'].max():.0f}",
         f"{df['ram_used_mb'].mean():.0f}",
         f"{df['ram_used_mb'].iloc[-1]:.0f}"],
        ["System RAM %",
         f"{df['ram_system_percent'].min():.1f}",
         f"{df['ram_system_percent'].max():.1f}",
         f"{df['ram_system_percent'].mean():.1f}", "—"],
        ["GPU util %",
         f"{df['gpu_util_percent'].min():.0f}",
         f"{df['gpu_util_percent'].max():.0f}",
         f"{df['gpu_util_percent'].mean():.1f}", "—"],
        ["VRAM used (MB)",
         f"{df['vram_used_mb'].min():.0f}",
         f"{df['vram_used_mb'].max():.0f}",
         f"{df['vram_used_mb'].mean():.0f}",
         f"{df['vram_used_mb'].iloc[-1]:.0f}"],
        ["IO read (MB)",   "—", "—", "—", f"{df['io_read_mb'].iloc[-1]:.1f}"],
        ["IO write (MB)",  "—", "—", "—", f"{df['io_write_mb'].iloc[-1]:.1f}"],
        ["Duration (s)",   "—", "—", "—", f"{df['elapsed_s'].iloc[-1]:.1f}"],
    ]

    if has_stages:
        stage_durations = (
            df.groupby("stage")["elapsed_s"]
            .agg(lambda g: g.max() - g.min())
            .sort_values(ascending=False)
        )
        for stage, dur in stage_durations.items():
            if stage not in ("unknown", "done"):
                rows.append([f"  ↳ {_stage_label(stage)} (s)", "—", "—", "—", f"{dur:.1f}"])

    n_stage_rows = len([r for r in rows if r[0].startswith("  ↳")])

    tbl = ax7.table(cellText=rows, colLabels=cols, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.4)

    for j in range(len(cols)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    for i in range(1, len(rows) + 1):
        is_stage_row = i > (len(rows) - n_stage_rows)
        bg = "#fef9e7" if is_stage_row else ("#ecf0f1" if i % 2 == 0 else "white")
        for j in range(len(cols)):
            tbl[i, j].set_facecolor(bg)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"performance_{job_id}.png"
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


if __name__ == "__main__":
    main()
