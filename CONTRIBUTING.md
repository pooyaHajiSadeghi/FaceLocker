# Contributing

Use Windows 11 x64 and Python 3.10 x64 for runtime and packaging changes. Keep application Python files in `src/`, BAT scripts in `scripts/`, and dependency pins in `requirements/`.

Install runtime dependencies and run `python -m unittest discover -s tests -v` from the project root. Run the separate GUI checks for interface changes, then verify camera behavior and folder attributes on a real Windows machine. Use temporary folders for visibility checks.

Pull requests should explain the concrete behavior change and relevant validation. Update installation or architecture documentation when changing payload layout, provisioning, verification rules, or storage. Preserve the existing license notice and third-party attribution requirements.

Do not commit enrolled embeddings, personal folder paths, model downloads, environments, logs, or build output. Report reproducible failures with environment details and redacted logs.
