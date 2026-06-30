import re
import polars as pl
from pathlib import Path

MARKER_START = "<!-- STREAK_TABLE_START -->"
MARKER_END = "<!-- STREAK_TABLE_END -->"


def load_match_data(filepath="wc.xlsx"):
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

    corrects_per_match = []

    for i in range(2, df.height):
        match_name = df.item(i, 0)
        if match_name is None or str(match_name).strip().lower() in ("nan", ""):
            continue

        sum_val = df.item(i, sum_col_idx)
        try:
            sum_num = float(sum_val)
        except (ValueError, TypeError):
            sum_num = 0.0

        if sum_num == 0:
            continue

        row_vals = df.row(i)[1:sum_col_idx]

        def parse_float(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        scores = [parse_float(v) for v in row_vals]
        corrects = [1 if s == 0.0 else 0 for s in scores]
        corrects_per_match.append(corrects)

    return player_names, corrects_per_match


def compute_streaks(player_names, corrects_per_match):
    n = len(player_names)

    current_win = [0] * n
    max_win = [0] * n
    current_loss = [0] * n
    max_loss = [0] * n

    for match_corrects in corrects_per_match:
        for j in range(n):
            if match_corrects[j] == 1:
                current_win[j] += 1
                max_win[j] = max(max_win[j], current_win[j])
                current_loss[j] = 0
            else:
                current_loss[j] += 1
                max_loss[j] = max(max_loss[j], current_loss[j])
                current_win[j] = 0

    rows = []
    for j, name in enumerate(player_names):
        rows.append(
            {
                "player": name,
                "current_win": current_win[j],
                "max_win": max_win[j],
                "current_loss": current_loss[j],
                "max_loss": max_loss[j],
            }
        )

    rows.sort(key=lambda r: (-r["max_win"], -r["max_loss"]))
    return rows


def build_table_html(rows):
    def badge(val, kind):
        if val > 0:
            return f'<span class="streak-badge streak-{kind}">{val}</span>'
        return f'<span class="streak-dim">{val}</span>'

    trs = ""
    for r in rows:
        trs += (
            f"\n              <tr>"
            f'<td class="streak-player" data-val="{r["player"]}">{r["player"]}</td>'
            f'<td class="streak-center" data-val="{r["current_win"]}">{badge(r["current_win"], "win")}</td>'
            f'<td class="streak-center streak-num" data-val="{r["max_win"]}">{r["max_win"]}</td>'
            f'<td class="streak-center" data-val="{r["current_loss"]}">{badge(r["current_loss"], "loss")}</td>'
            f'<td class="streak-center streak-num" data-val="{r["max_loss"]}">{r["max_loss"]}</td>'
            f"</tr>"
        )

    return f"""<table class="streak-table">
              <thead>
                <tr>
                  <th data-col="0">Người chơi</th>
                  <th class="streak-win-col" data-col="1">Chuỗi thắng<br />hiện tại</th>
                  <th class="streak-win-col" data-col="2">Chuỗi thắng<br />dài nhất</th>
                  <th class="streak-loss-col" data-col="3">Chuỗi thua<br />hiện tại</th>
                  <th class="streak-loss-col" data-col="4">Chuỗi thua<br />dài nhất</th>
                </tr>
              </thead>
              <tbody>{trs}
              </tbody>
            </table>"""


def main():
    player_names, corrects_per_match = load_match_data()
    rows = compute_streaks(player_names, corrects_per_match)
    table_html = build_table_html(rows)

    index_path = Path("index.html")
    content = index_path.read_text(encoding="utf-8")

    replacement = f"{MARKER_START}{table_html}{MARKER_END}"
    new_content = re.sub(
        re.escape(MARKER_START) + ".*?" + re.escape(MARKER_END),
        replacement,
        content,
        flags=re.DOTALL,
    )

    index_path.write_text(new_content, encoding="utf-8")
    print("Đã cập nhật streak table trong index.html")


if __name__ == "__main__":
    main()
