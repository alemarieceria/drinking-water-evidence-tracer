# Drinking Water Evidence Tracer

A research tool for tracing Zone I1 drinking water results to their source reports.
The application includes a labeled demonstration and a one-page extraction experiment.
Extraction outputs remain unconfirmed; live accuracy and manual browser checks must
be assessed separately from offline tests.

Run `uv run fastapi dev app/main.py`, then follow the extraction link or open
`/extract`. Configure the archive and model using `.env.example`; see the project
map for setup, limits, run records, and outstanding verification.

Start with the [visual project map](docs/project-map.md) for current capabilities,
processing diagrams, file responsibilities, setup, and design decisions.
The [proposal](docs/proposal.md) describes the intended research workflow.
