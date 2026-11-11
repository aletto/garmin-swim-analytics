# Contributing

Use Python 3.12 or newer and install the project with `python -m pip install -e '.[fit,dev]'`. Run the checks from the project root:

```sh
ruff check .
mypy
python -m unittest discover -s tests -v
pip-audit
```

Use English for issues, code, documentation and commits. For ingestion bugs, share an invented reproducer and describe the FIT message types involved. Keep real exports, account identifiers, logs, screenshots, tokens and user settings private. Add synthetic regression cases for quality changes and explain their effects on each stroke. Follow the [privacy review](docs/privacy.md) before staging. Contributions are licensed under MIT.
