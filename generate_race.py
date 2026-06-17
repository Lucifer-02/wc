import pandas as pd
import bar_chart_race as bcr
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Đọc file excel
df = pd.read_excel('wc.xlsx', header=None)
df = df.dropna(how='all')

# Tìm cột 'Sum' để xác định giới hạn cột của người chơi một cách linh hoạt
player_row = df.iloc[1].tolist()
sum_col_idx = -1
for idx, val in enumerate(player_row):
    if str(val).strip().lower() == 'sum':
        sum_col_idx = idx
        break

if sum_col_idx == -1:
    # Nếu không tìm thấy cột 'Sum', lấy tất cả các cột trừ cột tên trận đấu đầu tiên
    sum_col_idx = df.shape[1]

# Lấy tên người chơi từ hàng 1 (index 1), từ cột 1 đến cột trước 'Sum'
player_names = df.iloc[1, 1:sum_col_idx].tolist()
player_names = [str(name).strip() for name in player_names]

data_rows = []
indices = []

# Bỏ qua hàng 0 vì nó chứa tổng điểm của cả giải (đã được tính sẵn)
# Lấy dữ liệu từng trận từ hàng 2 trở đi
for i in range(2, len(df)):
    match_name = df.iloc[i, 0]
    if pd.isna(match_name) or str(match_name).strip().lower() in ('nan', ''):
        continue
    
    # Lấy điểm số của trận đấu này
    scores_series = pd.to_numeric(df.iloc[i, 1:sum_col_idx], errors='coerce')
    
    # Bỏ qua các trận đấu chưa diễn ra (toàn bộ điểm của người chơi đều là NaN)
    if scores_series.isna().all():
        continue
        
    scores = scores_series.fillna(0).tolist()
    data_rows.append(scores)
    indices.append(str(match_name).strip())

# Tạo DataFrame
df_clean = pd.DataFrame(data_rows, columns=player_names, index=indices)

# Tạo hàng khởi đầu với tất cả điểm số bằng 0
start_row = pd.DataFrame([[0] * len(player_names)], columns=player_names, index=['Bắt đầu'])
df_clean = pd.concat([start_row, df_clean])

# Tính tổng cộng dồn (cumulative sum)
df_cumsum = df_clean.cumsum()

# Xử lý font chữ tiếng Việt cho matplotlib
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']

match_list = df_cumsum.index.tolist()

def custom_summary(values, ranks):
    current_match = values.name
    try:
        idx = match_list.index(current_match)
    except ValueError:
        idx = 0
        
    start_idx = max(0, idx - 5)
    recent_matches = match_list[start_idx:idx+1]
    
    # Hiển thị danh sách trận đấu liên tiếp
    # Trận cũ ở trên, trận mới nhất ở dưới
    s = "\n".join(recent_matches)
    
    return {'x': 0.95, 'y': 0.1, 's': s, 'ha': 'right', 'va': 'bottom', 'size': 14, 'color': '#333333'}

# Thiết lập Figure và cấu hình trục hoành chia vạch mỗi 20 điểm
fig, ax = plt.subplots(figsize=(10, 8))
ax.set_title('Đua Top Tổng Điểm Qua Các Trận Bóng', fontsize=20, pad=20)
fig.subplots_adjust(top=0.9, left=0.15, right=0.95, bottom=0.1)
ax.xaxis.set_major_locator(ticker.MultipleLocator(20))

# Tạo video bar chart race
bcr.bar_chart_race(
    df=df_cumsum,
    filename='bar_chart_race.mp4',
    orientation='h',
    sort='desc',
    n_bars=len(player_names), # Hiển thị tất cả người chơi
    fixed_order=False,
    fixed_max=False,
    steps_per_period=30,
    period_length=1500,
    title='Đua Top Tổng Điểm Qua Các Trận Bóng',
    fig=fig,
    cmap='tab20',
    bar_label_size=8,
    tick_label_size=8,
    period_label=False, # Tắt nhãn mặc định để dùng custom_summary
    period_summary_func=custom_summary,
    interpolate_period=False # Tắt nội suy điểm số để nhảy trực tiếp theo mốc 20 điểm
)
print("Đã tạo thành công bar_chart_race.mp4 với danh sách các trận!")
