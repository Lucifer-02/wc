import multiprocessing as mp
import os
import shutil
import subprocess

import matplotlib
import numpy as np
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── 1. Đọc file excel ──────────────────────────────────────────────────────────
df = pl.read_excel("wc.xlsx", has_header=False)
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

# ── 2. Xây dựng DataFrame điểm cộng dồn ───────────────────────────────────────
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
start_row = pl.DataFrame([[0.0] * len(player_names)], schema=player_names, orient="row")
df_clean = pl.concat([start_row, df_clean])
df_cumsum = df_clean.select(pl.all().cum_sum())

n_players = len(player_names)
n_periods = df_cumsum.height
match_list = ["Bắt đầu"] + indices

# ── 3. Cấu hình ───────────────────────────────────────────────────────────────
STEPS = 50  # tăng số frame nội suy để chuyển động chậm hơn (2 giây/nhịp), dễ theo dõi
FPS = 50  # tốc độ chuẩn để xem mượt mà
HOLD_S = 3  # giữ frame cuối bao nhiêu giây


# ── 4. Easing functions ───────────────────────────────────────────────────────
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


# ── 5. Tính rank (vị trí Y) cho mỗi period ───────────────────────────────────
# rank[p][i] = vị trí Y (0 = dưới cùng) của player i tại period p
def compute_ranks(period_idx):
    vals = np.array(df_cumsum.row(period_idx), dtype=float)
    order = np.argsort(vals)  # tăng dần → index 0 = bar dưới cùng
    ranks = np.empty(n_players, dtype=float)
    for rank, player_i in enumerate(order):
        ranks[player_i] = rank
    return ranks


all_ranks = [compute_ranks(p) for p in range(n_periods)]

# ── 6. Màu sắc ────────────────────────────────────────────────────────────────
# Chọn các bảng màu có độ tương phản cao (màu đậm, rõ nét trên nền trắng)
tab10 = plt.get_cmap("tab10")
dark2 = plt.get_cmap("Dark2")
high_contrast_colors = [tab10(i) for i in range(10)] + [dark2(i) for i in range(8)]
player_colors = [
    high_contrast_colors[i % len(high_contrast_colors)] for i in range(n_players)
]

# ── 7. Figure ─────────────────────────────────────────────────────────────────
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
fig, ax = plt.subplots(figsize=(8, 5.3), dpi=100)
# Tên đã dời sang phải đỉnh bar nên có thể thu nhỏ lề trái
fig.subplots_adjust(top=0.90, left=0.05, right=0.95, bottom=0.08)


# ── 8. Hàm vẽ frame ───────────────────────────────────────────────────────────
# Khởi tạo trước các đối tượng đồ họa (Artists) để không phải vẽ lại từ đầu ở mỗi frame
bar_collection = ax.barh(
    range(n_players),
    [0] * n_players,
    color=player_colors,
    edgecolor="white",
    linewidth=0.5,
    height=0.75,
)

player_texts = []
for i in range(n_players):
    txt = ax.text(
        0,
        0,
        "",
        va="center",
        ha="left",
        fontsize=8,
        color=player_colors[i],
        fontweight="bold",
    )
    player_texts.append(txt)

recent_matches_text = ax.text(
    0.98,
    0.02,
    "",
    transform=ax.transAxes,
    ha="right",
    va="bottom",
    fontsize=9,
    color="#444444",
    linespacing=1.5,
)

# Cấu hình tĩnh cho trục toạ độ
ax.set_ylim(-0.6, n_players - 0.4)
ax.set_yticks([])  # ẩn ytick
ax.tick_params(axis="x", labelsize=8)
ax.grid(axis="x", linestyle="--", alpha=0.35)
ax.set_title("Đua Top Búng Tai", fontsize=14, pad=10, fontweight="bold")
ax.xaxis.set_major_locator(ticker.MultipleLocator(20))


def draw_frame(period_idx, step):
    cur_vals = np.array(df_cumsum.row(period_idx), dtype=float)
    cur_ranks = all_ranks[period_idx]

    if period_idx == 0 or step == 0:
        interp_vals = cur_vals.copy()
        interp_ranks = cur_ranks.copy()
    else:
        prev_vals = np.array(df_cumsum.row(period_idx - 1), dtype=float)
        prev_ranks = all_ranks[period_idx - 1]

        t_raw = step / STEPS

        # Giá trị: ease-in-out → tăng chậm lúc đầu & cuối
        t_val = ease_in_out_cubic(t_raw)
        interp_vals = prev_vals + t_val * (cur_vals - prev_vals)

        # Vị trí Y: ease-in-out → di chuyển mượt mà ở cả đầu và cuối, không bị giật nhanh
        t_pos = ease_in_out_cubic(t_raw)
        interp_ranks = prev_ranks + t_pos * (cur_ranks - prev_ranks)

    x_max = max(interp_vals.max(), 1)
    # Điều chỉnh lại xlim vì tên đã dời sang bên phải đỉnh bar
    ax.set_xlim(0, x_max * 1.25)

    # Cập nhật thông số cho từng bar thay vì xóa đi vẽ lại
    for i, name in enumerate(player_names):
        y = interp_ranks[i]
        val = interp_vals[i]

        # Cập nhật chiều dài và vị trí Y của bar (y là toạ độ tâm, set_y cần toạ độ đáy)
        bar_collection[i].set_width(val)
        bar_collection[i].set_y(y - 0.375)

        # Cập nhật vị trí và nội dung text
        player_texts[i].set_position((val + x_max * 0.008, y))
        player_texts[i].set_text(f"{name}: {val:.0f}")

    # Cập nhật danh sách 6 trận gần nhất
    start_idx = max(0, period_idx - 5)
    recent = match_list[start_idx : period_idx + 1]
    recent_matches_text.set_text("\n".join(recent))


# ── 9. Danh sách frames ───────────────────────────────────────────────────────
frames = [(0, 0)]
for p in range(1, n_periods):
    for s in range(1, STEPS + 1):
        frames.append((p, s))

hold_frames = int(HOLD_S * FPS)
frames += [frames[-1]] * hold_frames

total = len(frames)
print(f"Tổng số frame: {total} (~{total / FPS:.1f}s @ {FPS}fps)")


# ── 10. Render bằng Multiprocessing ───────────────────────────────────────────
def render_chunk(args):
    chunk_idx, frames_chunk, temp_dir = args
    for local_idx, (global_idx, period_idx, step) in enumerate(frames_chunk):
        draw_frame(period_idx, step)
        frame_path = os.path.join(temp_dir, f"frame_{global_idx:05d}.png")
        fig.savefig(frame_path, facecolor="white")


if __name__ == "__main__":
    temp_dir = "temp_frames"
    os.makedirs(temp_dir, exist_ok=True)

    indexed_frames = [(i, p, s) for i, (p, s) in enumerate(frames)]

    num_cores = max(1, mp.cpu_count() - 4)
    chunk_size = (total + num_cores - 1) // num_cores

    chunks = []
    for i in range(num_cores):
        chunk = indexed_frames[i * chunk_size : (i + 1) * chunk_size]
        if chunk:
            chunks.append((i, chunk, temp_dir))

    print(f"Đang render {total} frames bằng {num_cores} luồng (Multiprocessing)...")
    with mp.Pool(num_cores) as pool:
        pool.map(render_chunk, chunks)

    print("Gộp các frames thành MP4 bằng FFmpeg...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        os.path.join(temp_dir, "frame_%05d.png"),
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",  # Tự động làm tròn kích thước ảnh thành số chẵn
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        "3000k",
        "race.mp4",
    ]
    # Bỏ chặn stderr để nếu có lỗi FFmpeg thì sẽ báo chi tiết trên màn hình
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL)

    shutil.rmtree(temp_dir)
    print("Đã tạo thành công bar_chart_race_test.mp4 cực nhanh!")
