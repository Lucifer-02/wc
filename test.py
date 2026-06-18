import matplotlib
import numpy as np
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.animation import FFMpegWriter, FuncAnimation

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
STEPS = 40  # tăng số frame nội suy để chuyển động chậm hơn (2 giây/nhịp), dễ theo dõi
FPS = 30  # tốc độ chuẩn để xem mượt mà
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
player_colors = [high_contrast_colors[i % len(high_contrast_colors)] for i in range(n_players)]

# ── 7. Figure ─────────────────────────────────────────────────────────────────
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
fig, ax = plt.subplots(figsize=(8, 5.3), dpi=150)
# Tên đã dời sang phải đỉnh bar nên có thể thu nhỏ lề trái
fig.subplots_adjust(top=0.90, left=0.05, right=0.95, bottom=0.08)


# ── 8. Hàm vẽ frame ───────────────────────────────────────────────────────────
def draw_frame(period_idx, step):
    ax.clear()

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

    # Vẽ từng bar theo vị trí Y nội suy
    for i, name in enumerate(player_names):
        y = interp_ranks[i]
        val = interp_vals[i]
        ax.barh(
            y,
            val,
            color=player_colors[i],
            edgecolor="white",
            linewidth=0.5,
            height=0.75,
        )

        # Tên người chơi và điểm đặt ngay trên đỉnh bar (bên phải)
        ax.text(
            val + x_max * 0.008,
            y,
            f"{name}: {val:.0f}",
            va="center",
            ha="left",
            fontsize=8,
            color=player_colors[i],
            fontweight="bold",
        )

    ax.xaxis.set_major_locator(ticker.MultipleLocator(20))
    # Điều chỉnh lại xlim vì tên đã dời sang bên phải đỉnh bar
    ax.set_xlim(0, x_max * 1.25)
    ax.set_ylim(-0.6, n_players - 0.4)
    ax.set_yticks([])  # ẩn ytick mặc định, đã tự vẽ label
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.set_title(
        "Đua Top Tổng Điểm Qua Các Trận Bóng", fontsize=14, pad=10, fontweight="bold"
    )

    # Danh sách 6 trận gần nhất
    start_idx = max(0, period_idx - 5)
    recent = match_list[start_idx : period_idx + 1]
    ax.text(
        0.98,
        0.02,
        "\n".join(recent),
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color="#444444",
        linespacing=1.5,
    )


# ── 9. Danh sách frames ───────────────────────────────────────────────────────
frames = [(0, 0)]
for p in range(1, n_periods):
    for s in range(1, STEPS + 1):
        frames.append((p, s))

hold_frames = int(HOLD_S * FPS)
frames += [frames[-1]] * hold_frames

total = len(frames)
print(f"Tổng số frame: {total} (~{total / FPS:.1f}s @ {FPS}fps)")


def animate(frame_data):
    draw_frame(*frame_data)


anim = FuncAnimation(fig, animate, frames=frames, interval=1000 // FPS, repeat=False)

print("Đang render MP4... (có thể mất vài phút)")
writer = FFMpegWriter(fps=FPS, bitrate=1500)
anim.save(
    "bar_chart_race_test.mp4",
    writer=writer,
    savefig_kwargs={"facecolor": "white"},
)
plt.close(fig)
print("Đã tạo thành công bar_chart_race_test.mp4!")
