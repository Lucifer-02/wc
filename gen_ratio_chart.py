import altair as alt
import polars as pl


def main():
    filepath = "wc.xlsx"
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

    data_rows = []
    indices = []

    for i in range(2, df.height):
        match_name = df.item(i, 0)
        if match_name is None or str(match_name).strip().lower() in ("nan", ""):
            continue

        sum_val = df.item(i, sum_col_idx)
        try:
            sum_num = float(sum_val)
        except (ValueError, TypeError):
            sum_num = 0.0

        # Bỏ qua các trận chưa diễn ra (Sum == 0)
        if sum_num == 0:
            continue

        row_vals = df.row(i)[1:sum_col_idx]

        def parse_float(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        scores = [parse_float(v) for v in row_vals]
        # 0 điểm (hoặc rỗng) là đoán đúng (1), 20 điểm (hoặc >0) là đoán sai (0)
        corrects = [1 if s == 0.0 else 0 for s in scores]
        data_rows.append(corrects)
        indices.append(str(match_name).strip())

    n_players = len(player_names)

    records = []
    cumulative_correct = [0] * n_players

    # Thêm điểm Bắt đầu
    for j, player in enumerate(player_names):
        records.append(
            {
                "Match": "Bắt đầu",
                "Match_Index": 0,
                "Player": player,
                "Correct_Ratio": 0.0,
            }
        )

    for i, match in enumerate(indices):
        match_idx = i + 1
        corrects = data_rows[i]

        for j in range(n_players):
            cumulative_correct[j] += corrects[j]
            ratio = (cumulative_correct[j] / match_idx) * 100.0

            records.append(
                {
                    "Match": match,
                    "Match_Index": match_idx,
                    "Player": player_names[j],
                    "Correct_Ratio": ratio,
                }
            )

    df_out = pl.DataFrame(records)

    max_match_idx = df_out["Match_Index"].max()

    color_scale = alt.Scale(scheme="category10")

    hover = alt.selection_point(fields=["Player"], on="pointerover", clear="pointerout")
    click = alt.selection_point(fields=["Player"], bind="legend")
    highlight_cond = hover & click

    base = alt.Chart(df_out).encode(
        x=alt.X(
            "Match_Index:Q",
            title="Thứ tự trận",
            scale=alt.Scale(domain=[1, max_match_idx]),
            axis=alt.Axis(labelAngle=0, tickMinStep=1, format="d"),
        ),
        y=alt.Y(
            "Correct_Ratio:Q",
            title="Tỉ lệ đoán đúng (%)",
            scale=alt.Scale(domain=[0, 100]),
            axis=alt.Axis(labelAngle=0),
        ),
        color=alt.Color("Player:N", scale=color_scale, title="Người chơi"),
        tooltip=[
            alt.Tooltip("Player:N", title="Người chơi"),
            alt.Tooltip("Match:N", title="Trận đấu"),
            alt.Tooltip("Correct_Ratio:Q", title="Tỉ lệ đúng", format=".1f"),
        ],
    )

    hover_catch = base.mark_line(strokeWidth=20, opacity=0, clip=True).add_params(hover)

    lines = (
        base.mark_line(point=True, interpolate="monotone", clip=True)
        .encode(
            opacity=alt.condition(highlight_cond, alt.value(1.0), alt.value(0.1)),
            strokeWidth=alt.condition(highlight_cond, alt.value(4), alt.value(2)),
        )
        .add_params(click)
    )

    alt.theme.enable("dark")
    final_chart = (
        (lines + hover_catch)
        .properties(width="container", height=500, background="#1f2937")
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True,
            gridOpacity=0.3,
            gridColor="#374151",
            domainColor="#374151",
            tickColor="#374151",
            labelColor="#9ca3af",
            titleColor="#f9fafb",
        )
        .configure_legend(labelColor="#9ca3af", titleColor="#f9fafb")
        .configure_title(color="#f9fafb", fontSize=20, anchor="middle", dy=-10)
        .interactive()
    )

    output_file = "ratio_chart_altair.html"
    final_chart.save(output_file)
    print(f"Đã tạo {output_file}")


if __name__ == "__main__":
    main()
