# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a World Cup 2026 prediction game dashboard ("Đua Top Búng Tai") that generates two visual assets from an Excel data file and serves them via a static HTML page:

1. **`ratio_chart_altair.html`** — Interactive Altair/Vega-Lite line chart showing each player's cumulative correct-prediction ratio over time.
2. **`race.mp4`** — Animated bar-chart race video rendered frame-by-frame with matplotlib, then assembled via ffmpeg, with optional `audio.opus` background track.

## Commands

```bash
# Install dependencies
uv sync

# Generate all assets (chart + video + thumbnails)
make all

# Generate only the ratio chart HTML + chart_thumbnail.png
make ratio

# Generate only the race video
make race

# Generate video thumbnail (requires race.mp4)
make thumbnail

# Format Python + HTML/CSS
make format

# Remove all generated assets
make clean
```

Run scripts directly during development:
```bash
.venv/bin/python gen_ratio_chart.py
.venv/bin/python gen_race.py
```

## Data Format (`wc.xlsx`)

The Excel file has no header row. The layout expected by both scripts:
- **Row 0**: ignored (metadata/title row)
- **Row 1**: column headers — cell `[1,0]` is blank, cells `[1, 1..N]` are player names, followed by a column named `"sum"` (case-insensitive) that marks the end of the player columns
- **Rows 2+**: one row per match — `[i, 0]` is the match name, `[i, 1..N]` are scores (0 = correct prediction, non-zero = wrong), `[i, sum_col]` is the sum (rows where sum == 0 are skipped in the ratio chart as not-yet-played matches)

## Architecture

Both Python scripts follow the same data-loading pattern: read `wc.xlsx` with polars, find the `"sum"` sentinel column, extract player names and per-match score rows.

**`gen_ratio_chart.py`**: Builds a long-format polars DataFrame with cumulative correct-prediction ratios, renders an interactive Altair dark-theme chart with hover+click highlighting, and saves both an HTML embed and a static PNG thumbnail.

**`gen_race.py`**: Uses multiprocessing to render matplotlib frames in parallel (`num_cores = cpu_count - 4`), interpolates bar positions/values with `ease_in_out_cubic`, then calls ffmpeg to encode the final MP4. The `RaceContext` dataclass is passed to worker processes (must be picklable). `STEPS=25`, `FPS=30`, `HOLD_S=1.5` are the animation constants at the top of `main()`.

**`index.html` / `style.css`**: Static page embedding the video and chart iframe. On mobile, the interactive chart is hidden and replaced with `chart_thumbnail.png` + an overlay message.
