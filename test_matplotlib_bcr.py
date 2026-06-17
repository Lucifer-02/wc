import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.animation import FuncAnimation

# Đọc file excel (tương tự logic cũ)
df = pd.read_excel('wc.xlsx', header=None)
df = df.dropna(how='all')
player_row = df.iloc[1].tolist()
sum_col_idx = -1
for idx, val in enumerate(player_row):
    if str(val).strip().lower() == 'sum':
        sum_col_idx = idx
        break
if sum_col_idx == -1:
    sum_col_idx = df.shape[1]

player_names = [str(name).strip() for name in df.iloc[1, 1:sum_col_idx].tolist()]
data_rows, indices = [], []

for i in range(2, len(df)):
    match_name = df.iloc[i, 0]
    if pd.isna(match_name) or str(match_name).strip().lower() in ('nan', ''):
        continue
    scores_series = pd.to_numeric(df.iloc[i, 1:sum_col_idx], errors='coerce')
    if scores_series.isna().all():
        continue
    data_rows.append(scores_series.fillna(0).tolist())
    indices.append(str(match_name).strip())

df_clean = pd.DataFrame(data_rows, columns=player_names, index=indices)
start_row = pd.DataFrame([[0] * len(player_names)], columns=player_names, index=['Bắt đầu'])
df_clean = pd.concat([start_row, df_clean])
df_cumsum = df_clean.cumsum()
match_list = df_cumsum.index.tolist()

# Chuẩn bị dữ liệu cho Animation
steps_per_period = 30
df_values = df_cumsum.reset_index(drop=True)
df_values.index = df_values.index * steps_per_period
# Nhu cầu của user là interpolate_period=False nên value nhảy bậc (hoặc ffill)
df_values_interp = df_values.reindex(range(df_values.index.max() + 1)).ffill()

# Tính rank (vị trí y)
df_ranks = df_cumsum.rank(axis=1, method='first', ascending=True)
df_ranks_expanded = df_ranks.reset_index(drop=True)
df_ranks_expanded.index = df_ranks_expanded.index * steps_per_period
# Ranks luôn được interpolate để thanh di chuyển mượt mà
df_ranks_interp = df_ranks_expanded.reindex(range(df_ranks_expanded.index.max() + 1)).interpolate()

# Lấy colors
cmap = plt.get_cmap('tab20')
colors = cmap(range(len(player_names)))
color_map = dict(zip(player_names, colors))

fig, ax = plt.subplots(figsize=(10, 8))
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']

def update(frame):
    ax.clear()
    ax.set_title('Đua Top Tổng Điểm Qua Các Trận Bóng', fontsize=20, pad=20)
    
    # Lấy dữ liệu của frame hiện tại
    frame_values = df_values_interp.iloc[frame]
    frame_ranks = df_ranks_interp.iloc[frame]
    
    # Vẽ các thanh (barh)
    # y là rank, width là value
    bars = ax.barh(frame_ranks, frame_values, color=[color_map[x] for x in frame_values.index])
    
    # Thêm text cho các thanh
    for rank, name, value in zip(frame_ranks, frame_values.index, frame_values):
        ax.text(value + 0.5, rank, name, va='center', ha='left', fontsize=8)
        ax.text(value - 0.5, rank, f'{int(value)}', va='center', ha='right', color='white', fontsize=8)
        
    # Thiết lập trục
    ax.xaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.set_yticks([]) # Ẩn yticks vì đã có label trên thanh
    
    # Trận đấu hiện tại
    period_idx = frame // steps_per_period
    current_match = match_list[period_idx]
    
    # Custom summary logic
    start_idx = max(0, period_idx - 5)
    recent_matches = match_list[start_idx:period_idx+1]
    summary_text = "\n".join(recent_matches)
    
    ax.text(0.95, 0.1, summary_text, transform=ax.transAxes, 
            ha='right', va='bottom', fontsize=14, color='#333333')
            
    # Xoá viền
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(True, axis='x', color='white', alpha=0.5)
    ax.set_facecolor('.9')
    
fig.subplots_adjust(top=0.9, left=0.15, right=0.85, bottom=0.1)

anim = FuncAnimation(fig, update, frames=len(df_values_interp), interval=1500/steps_per_period)
anim.save('matplotlib_race.mp4', writer='ffmpeg', fps=steps_per_period/(1500/1000))
print("Saved matplotlib_race.mp4")
