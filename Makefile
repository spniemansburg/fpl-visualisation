.PHONY: presentation fetch analyse export

presentation: analyse export

fetch:
	uv run fpl_fetch.py

analyse:
	uv run fpl_analyse.py

export:
	uv run fpl_export.py
