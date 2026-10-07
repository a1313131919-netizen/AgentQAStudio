# Contributing

Contributions are welcome.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Run:

```powershell
.\.venv\Scripts\python.exe app.py
```

## Tests

```powershell
python -m unittest -v test_engine.py test_manual.py
.\.venv\Scripts\python.exe test_browser_smoke.py
```

The Browser smoke test uses a local HTML fixture and installed Microsoft Edge.

## Pull request checklist

- Keep API / Browser / Manual evaluation semantics consistent.
- Add or update tests for behavior changes.
- Do not commit secrets or local browser profiles.
- Update FIELD_REFERENCE.md when adding a UI field.
- Update screenshots when changing major layout.
- Run the packaged EXE smoke test for release changes.
