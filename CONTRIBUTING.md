# Contributing to edumints SCORM MCP

Thanks for your interest in contributing! This project is open-source and developed by the
[edumints.com](https://edumints.com) platform. Issues, ideas, and pull requests are all welcome.

## Ways to contribute
- **Report bugs** or request features via [Issues](../../issues) (use the templates).
- **Improve docs** (including translations of the README).
- **Add screen types, themes, or tools** — keep changes additive and backward-compatible.

## Development setup
```bash
git clone https://github.com/kemalyy/edumints-scorm-mcp.git
cd edumints-scorm-mcp
python -m venv .venv && source .venv/bin/activate
pip install ".[dev]"          # add ".[tts]" for the Piper TTS feature
pytest -q                     # run the test suite
```
Optional features need extra tooling: **video** (Node 22+ and HyperFrames via `npm i -g hyperframes`,
plus ffmpeg) and **TTS** (`pip install ".[tts]"` + a Piper voice). Tests skip these when the tooling
isn't present, so a plain `pip install ".[dev]"` is enough to run CI-equivalent checks locally.

## Guidelines
- **Small, focused modules.** Files that change together live together; one clear responsibility each.
- **Additive & backward-compatible.** New capabilities are opt-in/lazy — nothing should load or change
  behavior for courses that don't use it (the "zero-load" contract).
- **Tests first.** Add or update tests for any behavior change; keep the suite green (`pytest`).
- **No secrets** in code, tests, or docs. Never commit credentials, tokens, or private infrastructure
  details. `.env` is gitignored; only `.env.example` is tracked.
- **Style.** `ruff` is used for linting (`ruff check .`). Match the surrounding code's idioms.
- **Language.** Code, comments, commit messages, and `CHANGELOG.md` are written in English; `docs/`
  and README files are multilingual, with `README.tr.md` treated as a first-class citizen alongside
  `README.md`.

## Pull requests
1. Branch from `main`, make your change with tests.
2. Run `pytest -q` (and `ruff check .`) locally.
3. Open a PR using the template; describe the change and link any issue.
4. CI (GitHub Actions) runs the test suite on your PR.

## Code of Conduct
By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License
Contributions are accepted under the project's [MIT License](LICENSE).
