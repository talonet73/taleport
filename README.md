# TALeport

Local, free Windows desktop app for social media strategists and managers: it scans news, YouTube, Reddit and Google Trends for up to 10 topics, analyses what is trending and drafts posts for LinkedIn, Instagram, Facebook, YouTube and TikTok. Posts are always published by hand: TALeport never posts on social networks.

All data stays on your PC. No server, no account, no telemetry. UI in Italian, English and Spanish.

## Install

Download `Setup-TALeport.exe` from the [Releases page](https://github.com/talonet73/taleport/releases/latest) and run it. It installs for your Windows user only (no administrator rights), with shortcuts on the desktop and in the Start menu.

The installer is not code-signed yet, so Windows SmartScreen may show "Windows protected your PC": click **More info** → **Run anyway**.

Your data lives in `%LOCALAPPDATA%\TALeport` (API keys in Windows Credential Manager). Uninstalling asks whether to keep it.

User guide: [Italiano](docs/guide-it.md) · [English](docs/guide-en.md) · [Español](docs/guide-es.md) (also inside the app, under the **?** button).

Not monitored: Instagram, TikTok, Facebook and LinkedIn offer no free, legitimate access to their content. TALeport writes posts for them but does not read them.

See [PIANO.md](PIANO.md) for the development history and [CLAUDE.md](CLAUDE.md) for architecture and conventions.

## Development

Requirements: Windows 10/11 64-bit, Python 3.12, Node.js 20+.

```bash
# backend
cd backend
py -3.12 -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest

# frontend
cd frontend
npm install
npm run build        # production UI, served by the backend
npm run dev          # dev server on :5173 (use with `python -m taleport --dev`)
```

Run the app:

```bash
backend/.venv/Scripts/python -m taleport           # uses frontend/dist
backend/.venv/Scripts/python -m taleport --dev     # window points to the Vite dev server
backend/.venv/Scripts/python -m taleport --no-window   # API only, prints the URL to open in a browser
```

## Build the installer

Requirements: the development setup above, plus Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1          # → packaging\output\Setup-TALeport.exe
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipInstaller   # app only, in dist\TALeport
```

The version comes from `backend/taleport/__init__.py`. Optional code signing: set `TALEPORT_SIGN_CERT` (.pfx) and `TALEPORT_SIGN_PASSWORD`; `signtool.exe` must be on PATH.

## License

MIT
