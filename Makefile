# Makefile for generating the tournament page assets

PYTHON = .venv/bin/python
EXCEL_FILE = wc.xlsx

.PHONY: all bump race thumbnail clean format

all: bump race thumbnail

bump: bump_chart_altair.html

race: race.mp4

thumbnail: thumbnail.jpg

bump_chart_altair.html: gen_bump.py $(EXCEL_FILE)
	$(PYTHON) gen_bump.py

race.mp4: gen_race.py $(EXCEL_FILE)
	$(PYTHON) gen_race.py

thumbnail.jpg: race.mp4
	ffmpeg -y -ss 00:00:30 -i race.mp4 -vframes 1 -q:v 2 thumbnail.jpg

format:
	uvx ruff check --fix .
	uvx ruff format .
	npx -y prettier --write "**/*.{html,css,js,json,md}"

clean:
	rm -f bump_chart_altair.html race.mp4 thumbnail.jpg
	rm -rf temp_frames __pycache__ .mypy_cache
