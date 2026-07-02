# Makefile for generating the tournament page assets

PYTHON = .venv/bin/python
EXCEL_FILE = wc.xlsx

.PHONY: all ratio race thumbnail chart_thumbnail streak clean format

all: ratio race thumbnail chart_thumbnail streak

ratio: ratio_chart_altair.html

race: race.mp4

thumbnail: thumbnail.jpg

chart_thumbnail: chart_thumbnail.png

streak: gen_streak_table.py $(EXCEL_FILE)
	$(PYTHON) gen_streak_table.py

ratio_chart_altair.html chart_thumbnail.png &: gen_ratio_chart.py $(EXCEL_FILE)
	$(PYTHON) gen_ratio_chart.py

race.mp4: gen_race.py $(EXCEL_FILE)
	$(PYTHON) gen_race.py

thumbnail.jpg: race.mp4
	ffmpeg -y -ss 00:00:30 -i race.mp4 -vframes 1 -q:v 2 thumbnail.jpg

format:
	uvx ruff check --fix .
	uvx ruff format .
	npx -y prettier --write "**/*.{html,css,js,json,md}"

clean:
	rm -f ratio_chart_altair.html race.mp4 thumbnail.jpg chart_thumbnail.png
	rm -rf temp_frames __pycache__ .mypy_cache
