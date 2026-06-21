from typing import Any, Dict, List, Tuple

import altair as alt
import numpy as np
import polars as pl


def load_data_for_altair(filepath: str) -> Tuple[List[Dict[str, Any]], List[str]]:
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

    n_players = len(player_names)

    # Calculate cumulative scores and ranks
    cumulative_scores = np.zeros(n_players)

    records = []

    # Bắt đầu
    for j, player in enumerate(player_names):
        records.append(
            {
                "Match": "Bắt đầu",
                "Match_Index": 0,
                "Player": player,
                "Score": 0.0,
                "Cumulative_Score": 0.0,
                "Rank": 1,
            }
        )

    for i, match in enumerate(indices):
        match_idx = i + 1
        scores = data_rows[i]
        cumulative_scores += np.array(scores)

        # Calculate ranks (1 is highest score) - using dense ranking
        rounded_scores = np.round(cumulative_scores, 2)
        order = np.argsort(-rounded_scores)
        ranks = np.empty(n_players, dtype=int)

        current_rank = 1
        for j in range(n_players):
            if j > 0 and rounded_scores[order[j]] < rounded_scores[order[j - 1]]:
                current_rank += 1
            ranks[order[j]] = current_rank

        for j, player in enumerate(player_names):
            records.append(
                {
                    "Match": match,
                    "Match_Index": match_idx,
                    "Player": player,
                    "Score": float(scores[j]),
                    "Cumulative_Score": float(cumulative_scores[j]),
                    "Rank": int(ranks[j]),
                }
            )

    return records, player_names


def main():
    filepath = "wc.xlsx"
    records, player_names = load_data_for_altair(filepath)
    df = pl.DataFrame(records)

    (
        df.group_by("Match")
        .agg(pl.col("Match_Index").min())
        .sort("Match_Index")["Match"]
        .to_list()
    )
    max_match_idx = df["Match_Index"].max()

    color_scale = alt.Scale(scheme="category10")

    hover = alt.selection_point(fields=["Player"], on="pointerover", clear="pointerout")
    click = alt.selection_point(fields=["Player"], bind="legend")

    highlight_cond = hover & click

    # --- 1. Bump Chart ---
    base_bump = alt.Chart(df).encode(
        x=alt.X(
            "Match_Index:Q",
            title="Thứ tự trận",
            scale=alt.Scale(domain=[1, max_match_idx]),
            axis=alt.Axis(labelAngle=0, tickMinStep=1, format="d"),
        ),
        y=alt.Y(
            "Rank:Q",
            title="Hạng",
            scale=alt.Scale(reverse=True, domain=[1, 22]),
            axis=alt.Axis(
                tickMinStep=1,
                format="d",
                titleAngle=0,
                titleAlign="right",
                titleY=-15,
                titleX=0,
            ),
        ),
        color=alt.Color("Player:N", scale=color_scale, title="Người chơi"),
        tooltip=[
            alt.Tooltip("Player:N", title="Người chơi"),
            alt.Tooltip("Match:N", title="Trận đấu"),
            alt.Tooltip("Rank:Q", title="Hạng"),
            alt.Tooltip("Cumulative_Score:Q", title="Điểm số tích lũy"),
        ],
    )

    hover_catch_bump = base_bump.mark_line(
        strokeWidth=20, opacity=0, clip=True
    ).add_params(hover)

    bump_lines = (
        base_bump.mark_line(point=True, interpolate="monotone", clip=True)
        .encode(
            opacity=alt.condition(highlight_cond, alt.value(1.0), alt.value(0.1)),
            strokeWidth=alt.condition(highlight_cond, alt.value(4), alt.value(2)),
        )
        .add_params(click)
    )

    alt.theme.enable("dark")
    final_bump = (
        (bump_lines + hover_catch_bump)
        .properties(width="container", height=600, background="#1f2937")
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
        .interactive()
    )

    final_bump.save("bump_chart_altair.html")
    print("Đã tạo bump_chart_altair.html")


if __name__ == "__main__":
    main()
