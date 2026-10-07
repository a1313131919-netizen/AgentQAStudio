# Installation Guide

## Recommended: Windows Setup EXE

1. Go to the GitHub **[Releases](https://github.com/a1313131919-netizen/AgentQAStudio/releases/latest)** page.
2. Download `AgentQAStudio_Setup.exe`.
3. Double-click it.
4. Press **安裝 Agent QA Studio**.
5. The app is installed per-user, so administrator rights are normally not required.
6. Launch it from:
   - Desktop shortcut, or
   - Windows Start Menu → Agent QA Studio.

The installer places the application under the current user's local application directory.

## Portable version

Download `AgentQAStudio.exe` from Releases and run it directly.

Use the Portable build when you do not want to create Start Menu / Desktop shortcuts.

## Windows SmartScreen

Unsigned open-source executables may trigger Windows SmartScreen.

If Windows shows a warning:

1. Verify that you downloaded the file from this project's GitHub Release.
2. Check the release notes and file name.
3. Choose **More info** only if you trust the downloaded release.
4. Run the app.

Do not disable SmartScreen system-wide.

## First launch

The first launch can take a few seconds because the release is a single-file packaged application.

Recommended first steps:

1. Open **4 Test Cases**.
2. Load or create a few cases.
3. Use the built-in Demo under **1 API Auto**.
4. Go to **5 執行與結果**.
5. Select **API Auto** and run.

## Browser Auto prerequisites

Browser Auto uses an installed browser rather than downloading a separate browser.

Supported channels:

- `msedge` — Microsoft Edge
- `chrome` — Google Chrome

If Browser Auto cannot launch:

1. Confirm Edge or Chrome is installed.
2. Try the other Browser value.
3. Confirm no security policy blocks browser automation.
4. See [Browser Auto Guide](BROWSER_AUTO.md).

## Source installation

Clone the repository and create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Run:

```powershell
.\.venv\Scripts\python.exe app.py
```

## Build from source

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The build script packages Playwright with the app but uses the locally installed Edge/Chrome browser channel.

Generated files:

```text
dist\AgentQAStudio.exe
dist\AgentQAStudio_Setup.exe
```

## Application data

Agent QA Studio stores local data in:

```text
%LOCALAPPDATA%\AgentQAStudio
```

Typical files:

- `config.json` — API mapping/config except Bearer token.
- `browser_config.json` — Browser Auto selectors/settings.
- `test_cases.json` — Test Cases.
- `history.db` — SQLite execution history.
- `browser_profile\` — dedicated browser login/profile state.

## Uninstall

The installer creates an uninstall command inside the application directory.

Before uninstalling:

1. Close Agent QA Studio.
2. Close Browser Auto browser windows.
3. Run the uninstall command.

The local QA data directory may be retained so reports/history are not accidentally destroyed. Delete it manually only when you intentionally want to remove your stored Test Cases and history.
