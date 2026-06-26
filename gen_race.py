import multiprocessing as mp
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Tuple

import matplotlib
import numpy as np
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


@dataclass
class RaceContext:
    player_names: List[str]
    match_list: List[str]
    df_cumsum_rows: List[np.ndarray]
    all_ranks: List[np.ndarray]
    player_colors: List[Tuple[float, float, float, float]]
    steps: int
    fps: int


def ease_in_out_cubic(t: float) -> float:
    """t ∈ [0,1] → slow start, fast middle, slow end"""
    if t < 0.5:
        return 4 * t * t * t
    else:
        p = 2 * t - 2
        return 1 + 0.5 * p * p * p


def ease_out_cubic(t: float) -> float:
    """t ∈ [0,1] → fast start, slow end (tốt cho vị trí bar)"""
    return 1 - (1 - t) ** 3


def load_data(filepath: str) -> Tuple[List[str], List[str], List[np.ndarray]]:
    df = pl.read_excel(filepath, has_header=False)
    df = df.filter(~pl.all_horizontal(pl.all().is_null()))

    player_row = df.row(1)
    sum_col_idx = -1
    for idx, val in enumerate(player_row):
        if val is not None and str(val).strip().lower() == "sum":
            sum_col_idx = idx
            break
    if sum_col_idx == -1:
        sum_col_idx = df.width

    player_names = [str(name).strip() for name in player_row[1:sum_col_idx]]

    data_rows, indices = [], []
    for i in range(2, df.height):
        match_name = df.item(i, 0)
        if match_name is None or str(match_name).strip().lower() in ("nan", ""):
            continue

        row_vals = df.row(i)[1:sum_col_idx]

        def parse_float(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        scores = [parse_float(v) for v in row_vals]
        if all(s is None or s != s for s in scores):
            continue

        scores = [0.0 if (s is None or s != s) else s for s in scores]
        data_rows.append(scores)
        indices.append(str(match_name).strip())

    df_clean = pl.DataFrame(data_rows, schema=player_names, orient="row")
    start_row = pl.DataFrame(
        [[0.0] * len(player_names)], schema=player_names, orient="row"
    )
    df_clean = pl.concat([start_row, df_clean])
    df_cumsum = df_clean.select(pl.all().cum_sum())

    match_list = ["Bắt đầu"] + indices

    # Pre-convert to numpy arrays for faster access in rendering and easier pickling
    df_cumsum_rows = [
        np.array(df_cumsum.row(i), dtype=float) for i in range(df_cumsum.height)
    ]

    return player_names, match_list, df_cumsum_rows


def compute_all_ranks(
    df_cumsum_rows: List[np.ndarray], n_players: int
) -> List[np.ndarray]:
    all_ranks = []
    for vals in df_cumsum_rows:
        order = np.argsort(vals)
        ranks = np.empty(n_players, dtype=float)
        for rank, player_i in enumerate(order):
            ranks[player_i] = rank
        all_ranks.append(ranks)
    return all_ranks


def generate_player_colors(n_players: int) -> List[Tuple[float, float, float, float]]:
    tab10 = plt.get_cmap("tab10")
    dark2 = plt.get_cmap("Dark2")
    high_contrast_colors = [tab10(i) for i in range(10)] + [dark2(i) for i in range(8)]
    return [
        high_contrast_colors[i % len(high_contrast_colors)] for i in range(n_players)
    ]


class FrameRenderer:
    """Manages the matplotlib Figure and axes locally to avoid sharing global state."""

    def __init__(self, ctx: RaceContext):
        self.ctx = ctx
        self.n_players = len(ctx.player_names)

        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
        self.fig, self.ax = plt.subplots(figsize=(8, 5.3), dpi=100)
        self.fig.subplots_adjust(top=0.90, left=0.05, right=0.95, bottom=0.08)

        self.bar_collection = self.ax.barh(
            range(self.n_players),
            [0] * self.n_players,
            color=ctx.player_colors,
            edgecolor="white",
            linewidth=0.5,
            height=0.75,
        )

        self.player_texts = []
        for i in range(self.n_players):
            txt = self.ax.text(
                0,
                0,
                "",
                va="center",
                ha="left",
                fontsize=8,
                color=ctx.player_colors[i],
                fontweight="bold",
            )
            self.player_texts.append(txt)

        self.recent_matches_text = self.ax.text(
            0.98,
            0.02,
            "",
            transform=self.ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="#444444",
            linespacing=1.5,
        )

        self.ax.set_ylim(-0.6, self.n_players - 0.4)
        self.ax.set_yticks([])
        self.ax.tick_params(axis="x", labelbottom=False)
        self.ax.grid(axis="x", linestyle="--", alpha=0.35)
        # self.ax.set_title("Đua Top Búng Tai", fontsize=14, pad=10, fontweight="bold")
        self.ax.xaxis.set_major_locator(ticker.MultipleLocator(20))

    def draw_frame(self, period_idx: int, step: int):
        cur_vals = self.ctx.df_cumsum_rows[period_idx]
        cur_ranks = self.ctx.all_ranks[period_idx]

        if period_idx == 0 or step == 0:
            interp_vals = cur_vals.copy()
            interp_ranks = cur_ranks.copy()
        else:
            prev_vals = self.ctx.df_cumsum_rows[period_idx - 1]
            prev_ranks = self.ctx.all_ranks[period_idx - 1]

            t_raw = step / self.ctx.steps
            t_val = ease_in_out_cubic(t_raw)
            interp_vals = prev_vals + t_val * (cur_vals - prev_vals)

            t_pos = ease_in_out_cubic(t_raw)
            interp_ranks = prev_ranks + t_pos * (cur_ranks - prev_ranks)

        x_max = max(interp_vals.max(), 1)
        self.ax.set_xlim(0, x_max * 1.25)

        for i, name in enumerate(self.ctx.player_names):
            y = interp_ranks[i]
            val = interp_vals[i]

            self.bar_collection[i].set_width(val)
            self.bar_collection[i].set_y(y - 0.375)

            self.player_texts[i].set_position((val + x_max * 0.008, y))
            self.player_texts[i].set_text(f"{name}: {val:.0f}")

        start_idx = max(0, period_idx - 5)
        recent = self.ctx.match_list[start_idx : period_idx + 1]
        self.recent_matches_text.set_text("\n".join(recent))

    def save_frame(self, period_idx: int, step: int, path: str):
        self.draw_frame(period_idx, step)
        self.fig.savefig(path, facecolor="white")

    def close(self):
        plt.close(self.fig)


def render_chunk(args):
    """Entry point for each multiprocessing pool worker."""
    chunk_idx, frames_chunk, temp_dir, ctx = args
    renderer = FrameRenderer(ctx)
    for global_idx, period_idx, step in frames_chunk:
        frame_path = os.path.join(temp_dir, f"frame_{global_idx:05d}.png")
        renderer.save_frame(period_idx, step, frame_path)
    renderer.close()


def main():
    # --- Config ---
    STEPS = 25
    FPS = 30
    HOLD_S = 1.5
    EXCEL_FILE = "wc.xlsx"
    OUT_VIDEO = "race.mp4"
    AUDIO_FILE = "./audio.opus"
    TEMP_DIR = "temp_frames"

    # --- Data Preparation ---
    player_names, match_list, df_cumsum_rows = load_data(EXCEL_FILE)
    n_players = len(player_names)
    n_periods = len(df_cumsum_rows)

    all_ranks = compute_all_ranks(df_cumsum_rows, n_players)
    player_colors = generate_player_colors(n_players)

    ctx = RaceContext(
        player_names=player_names,
        match_list=match_list,
        df_cumsum_rows=df_cumsum_rows,
        all_ranks=all_ranks,
        player_colors=player_colors,
        steps=STEPS,
        fps=FPS,
    )

    # --- Frames Generation ---
    frames = [(0, 0)]
    start_hold_frames = int(10 * FPS)
    frames += [(0, 0)] * start_hold_frames

    for p in range(1, n_periods):
        for s in range(1, STEPS + 1):
            frames.append((p, s))

    hold_frames = int(HOLD_S * FPS)
    frames += [frames[-1]] * hold_frames

    total = len(frames)
    print(f"Tổng số frame: {total} (~{total / FPS:.1f}s @ {FPS}fps)")

    # --- Multiprocessing ---
    os.makedirs(TEMP_DIR, exist_ok=True)
    indexed_frames = [(i, p, s) for i, (p, s) in enumerate(frames)]

    num_cores = max(1, mp.cpu_count() - 4)
    chunk_size = (total + num_cores - 1) // num_cores

    chunks = []
    for i in range(num_cores):
        chunk = indexed_frames[i * chunk_size : (i + 1) * chunk_size]
        if chunk:
            chunks.append((i, chunk, TEMP_DIR, ctx))

    print(f"Đang render {total} frames bằng {num_cores} luồng (Multiprocessing)...")
    with mp.Pool(num_cores) as pool:
        pool.map(render_chunk, chunks)

    # --- FFmpeg Compilation ---
    print("Gộp các frames thành MP4 bằng FFmpeg...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        os.path.join(TEMP_DIR, "frame_%05d.png"),
    ]

    has_audio = os.path.exists(AUDIO_FILE)
    if has_audio:
        ffmpeg_cmd.extend(["-i", AUDIO_FILE])

    ffmpeg_cmd.extend([
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ])

    if has_audio:
        ffmpeg_cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])

    ffmpeg_cmd.append(OUT_VIDEO)

    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL)

    shutil.rmtree(TEMP_DIR)
    print(f"Đã tạo thành công {OUT_VIDEO} cực nhanh!")


if __name__ == "__main__":
    main()
