# TALeport

Local, free Windows desktop app for social media strategists and managers: it scans news, YouTube, Reddit and Google Trends for up to 10 topics, analyses what is trending and drafts posts for LinkedIn, Instagram, Facebook, YouTube and TikTok. Posts are always published by hand: TALeport never posts on social networks.

All data stays on your PC. No server, no account, no telemetry. UI in Italian, English and Spanish.

> Work in progress — see [PIANO.md](PIANO.md) for the development plan and [CLAUDE.md](CLAUDE.md) for architecture and conventions.

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

## License

MIT
