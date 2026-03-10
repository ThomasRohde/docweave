# Installation

Docweave requires **Python 3.12 or later**.

## With uv (Recommended)

[uv](https://github.com/astral-sh/uv) is the recommended installer:

```bash
uv tool install docweave
```

This installs the `docweave` command globally without polluting your system Python.

## From the Repository

Install the latest development version directly from GitHub:

```bash
uv tool install git+https://github.com/ThomasRohde/docweave.git
```

## Development Install

For contributing or modifying docweave:

```bash
git clone https://github.com/ThomasRohde/docweave.git
cd docweave
pip install -e ".[dev]"
```

Or with uv:

```bash
uv sync --extra dev
```

## Verify

After installation, check everything works:

```bash
docweave --version
docweave guide
```

## Python Dependencies

| Package | Minimum Version | Purpose |
| ------- | --------------- | ------- |
| typer | 0.15 | CLI framework |
| pydantic | 2.0 | Data validation |
| orjson | 3.9 | JSON serialization |
| markdown-it-py | 3.0 | Markdown parsing |
| pyyaml | 6.0 | Patch file parsing |
| rich | 13.0 | Terminal output |
