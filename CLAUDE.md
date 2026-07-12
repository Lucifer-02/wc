# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a World Cup 2026 prediction game dashboard ("Đua Top Búng Tai") that generates visual assets from an Excel data file and serves them via a static HTML page:

1. **`ratio_chart_altair.html`** — Interactive Altair/Vega-Lite line chart showing each player's cumulative correct-prediction ratio over time (plus `chart_thumbnail.png`, a static PNG fallback for mobile).
2. **`race.mp4`** — Animated bar-chart race video rendered frame-by-frame with matplotlib, then assembled via ffmpeg, with optional `audio.opus` background track (plus `thumbnail.jpg`, a poster frame extracted from the video).
3. **Streak table** — an HTML `<table>` of each player's current/longest win and loss streaks, injected directly into `index.html` between `<!-- STREAK_TABLE_START -->` / `<!-- STREAK_TABLE_END -->` markers.

## Commands

```bash
# Install dependencies
uv sync

# Generate all assets (chart + video + thumbnails + streak table)
make all

# Generate only the ratio chart HTML + chart_thumbnail.png
make ratio

# Generate only the race video
make race

# Generate video poster thumbnail (requires race.mp4)
make thumbnail

# Update the streak table embedded in index.html
make streak

# Format Python + HTML/CSS
make format

# Remove all generated assets
make clean
```

Run scripts directly during development:
```bash
.venv/bin/python gen_ratio_chart.py
.venv/bin/python gen_race.py
.venv/bin/python gen_streak_table.py
```

## Data Format (`wc.xlsx`)

The Excel file has no header row. The layout expected by all three scripts:
- **Row 0**: ignored (metadata/title row)
- **Row 1**: column headers — cell `[1,0]` is blank, cells `[1, 1..N]` are player names, followed by a column named `"sum"` (case-insensitive) that marks the end of the player columns
- **Rows 2+**: one row per match — `[i, 0]` is the match name, `[i, 1..N]` are scores (`<= 0` = correct prediction, `> 0` = wrong), `[i, sum_col]` is the sum

Rows where `sum == 0` mean the match hasn't been played yet: `gen_ratio_chart.py` and `gen_streak_table.py` skip these; `gen_race.py` does not check `sum` and includes every row that has a non-empty match name.

## Architecture

All three Python scripts follow the same data-loading pattern: read `wc.xlsx` with polars, find the `"sum"` sentinel column, extract player names and per-match score rows. This loading logic is duplicated (not shared) across the three files — when changing the Excel schema, update all three.

**`gen_ratio_chart.py`**: Builds a long-format polars DataFrame with cumulative correct-prediction ratios (`1 − cumulative_score / cumulative_max_possible_penalty`), renders an interactive Altair dark-theme chart with hover+click legend highlighting, and saves both an HTML embed (`ratio_chart_altair.html`) and a static PNG thumbnail (`chart_thumbnail.png`).

**`gen_race.py`**: Uses multiprocessing to render matplotlib frames in parallel (`num_cores = cpu_count - 4`), interpolates bar positions/values between matches with `ease_in_out_cubic`, then calls ffmpeg to encode the final MP4. The `RaceContext` dataclass is passed to worker processes (must stay picklable). `STEPS=25`, `FPS=30`, `HOLD_S=1.5` are the animation constants at the top of `main()`. Frames are written to `temp_frames/` and removed after encoding.

**`gen_streak_table.py`**: Computes each player's current/max win and loss streaks from the match score rows, builds an HTML `<table>` (sorted by `max_win` desc, then `max_loss` desc), and does a regex replace of the content between the `STREAK_TABLE_START`/`STREAK_TABLE_END` markers directly inside `index.html`. This script mutates `index.html` in place — re-run `make streak` any time `wc.xlsx` changes if you want the embedded table refreshed.

**`index.html` / `style.css`**: Static page embedding the race video (`race.mp4`, poster `thumbnail.jpg`), the streak table (injected by `gen_streak_table.py`), and the chart iframe (`ratio_chart_altair.html`). On mobile, the interactive chart iframe is hidden and replaced with `chart_thumbnail.png` plus a `.mobile-warning` overlay message.
