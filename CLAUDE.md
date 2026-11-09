# TALeport — guida al progetto

App desktop Windows (installer `.exe`) per social media strategist/manager: scansiona notizie, YouTube, Reddit e Google Trends su un massimo di 10 argomenti, analizza i risultati, mostra report e genera bozze di post da pubblicare **a mano**. Locale, gratuita, nessun server, nessun account, nessuna telemetria.

Specifica completa: [prompt-claude-code-taleport.md](prompt-claude-code-taleport.md). Avanzamento: [PIANO.md](PIANO.md).

Nome: sempre **TALeport** nei testi visibili; `taleport` per pacchetti, cartelle e identificativi.

## Regole di lavoro

- Si lavora **per fasi** (vedi PIANO.md). A fine fase: l'app si avvia, i test passano, PIANO.md aggiornato, riepilogo breve. **Non si passa alla fase successiva senza l'ok dell'utente.**
- Codice, commenti, nomi tecnici, messaggi di commit: **inglese**. Interfaccia: **IT / EN / ES** tramite i18n, nessuna stringa visibile scritta nei componenti o nel backend.
- Se un'API o una fonte non si comporta come da specifica: verificare la documentazione attuale, avvisare l'utente, proporre un'alternativa. Mai inventare endpoint.
- Mai scraping con login dell'utente, mai automazione dei siti delle chat AI, mai elusione di limiti o termini d'uso.
- Commit e push solo su richiesta dell'utente.

## Decisioni prese

| Tema | Decisione | Motivo |
|---|---|---|
| Comunicazione UI ↔ backend | **FastAPI** su `127.0.0.1`, porta casuale, token di sessione nell'header `X-TALeport-Token`; **SSE** per avanzamento scansioni e notifiche | Il bridge pywebview è solo chiamata/risposta, poco adatto a flussi continui e difficile da testare. FastAPI permette di sviluppare la UI nel browser (Vite) e testare le API con pytest |
| Finestra | pywebview (WebView2), minimo 1280×720, ridimensionabile; il token viene passato alla pagina all'avvio | — |
| Tray | pystray + Pillow; chiudere la finestra la riduce nella tray (opzione nelle impostazioni) | Le scansioni pianificate girano anche a finestra chiusa |
| Istanza singola | mutex con nome di Windows; un secondo avvio porta in primo piano la finestra esistente | — |
| Dati utente | `%LOCALAPPDATA%\TALeport\` (`taleport.db`, `logs\`, `exports\`) | Installazione per utente, nessun permesso di amministratore |
| Database | SQLite + FTS5; migrazioni SQL numerate (`0001_init.sql`, …) tracciate con `PRAGMA user_version` | Semplice, nessuna dipendenza in più |
| Segreti | `keyring` (Windows Credential Manager), servizio `TALeport`; mai nel DB, nei file o nei backup | — |
| Pianificazione | APScheduler 3.x nel processo dell'app; recupero all'avvio confrontando l'ultima scansione riuscita con l'orario previsto | — |
| Avvio con Windows | chiave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` | Nessun permesso di amministratore |
| Parole chiave | YAKE + stopword IT/EN/ES incluse nel pacchetto | Leggero, multilingua, offline |
| Grafici UI | Apache ECharts (+ `echarts-wordcloud`) | — |
| Report PDF | `reports/builder.py` produce il contenuto come dati (sezioni di blocchi), `reports/pdf.py` lo impagina con ReportLab (copertina, indice con `multiBuild`, segnalibri, piè di pagina); grafici matplotlib → SVG con `svg.fonttype = none` → svglib, font DejaVu Sans di matplotlib registrato sia in ReportLab sia in svglib; file in `exports\`, aperti con `os.startfile`; i report di "Chiedi" rieseguono il piano validato | PDF offline, grafici vettoriali con testo vero, contenuto testabile senza leggere PDF |
| Notifiche | tabella `notifications` (`kind` + `params`, tradotti dalla UI; `dedupe_key` per non ripetere) + campanella aggiornata via SSE; notifica di Windows con `pystray` `Icon.notify` dall'icona nella tray, testi dal catalogo del backend (`resources/i18n`); regole in `notifications/rules.py` | Nessuna libreria in più; Windows-Toasts in un'app non registrata mostrerebbe «Python» come mittente |
| Testi lunghi | `pypdf`, `python-docx` | — |
| Icona `.ico` | script in `packaging/` che rasterizza `taleport-icon.svg` (sharp, Node) → PNG 16–256 → `.ico` con Pillow | cairosvg su Windows richiede librerie native |
| Reddit | **Solo feed RSS pubblici** (ricerca + `r/a+b/new/.rss`), max 2 richieste per argomento, cadenza guidata da `X-Ratelimit-*`; sospeso per la scansione se bloccato | JSON anonimo = 403; niente più chiavi API self-service (verificato 2026-11); RSS anonimo ≈ 1 richiesta/minuto |
| Google Trends | feed RSS pubblico `trends.google.com/trending/rss?geo=XX`, filtrato con le parole chiave; gli hashtag contano solo se uguali al termine | pytrends/trendspy abbandonate; il feed è stabile |
| Analisi statistica | YAKE (n ≤ 2) + elenchi in `resources/stopwords/` (`generic.txt` = parole che da sole non fanno un tema); temi per parola chiave condivisa, mai con le parole dell'argomento; punteggio caldo in `analysis/scoring.py` (pesi documentati lì) | Spiegabile, offline, nessun modello da scaricare |
| Colori dei grafici | ogni colore dei grafici è un token (`--tp-chart-1` per una serie, `--tp-series-1…5` per più serie in ordine fisso: ciano, arancio, viola, giallo, magenta) validato con lo script della skill dataviz su entrambi i temi; un grafico = un asse, legenda solo con ≥ 2 serie, tabella alternativa sempre disponibile; niente etichette di fine linea (si sovrappongono) | Leggibilità e accessibilità |
| Tetto di spesa | `AIService.resolve` controlla il tetto (`spend_cap_usd`): raggiunto, ogni provider a pagamento ripiega su «Apri nella chat» con motivo `ai.spend_cap_reached`; Ollama resta libero | Nessuna chiamata a pagamento oltre il tetto, nessuna funzione bloccata |
| Risultati e priorità | `results/service.py`: interazioni = like + commenti + condivisioni; un social o un tema è suggerito solo se supera gli altri di almeno il 25%, sempre con la metrica e il numero che lo motivano | Spiegabile, mai una classifica senza perché |
| Calendario | `drafts.scheduled_at` (ora locale) è il calendario; orari consigliati = predefiniti → scelta dell'utente → orario «imparato» dai risultati (solo suggerito) | Nessuna tabella in più |
| Archivio | FTS5 a contenuto esterno su `drafts` e `themes`; la ricerca dell'utente diventa parole tra virgolette con prefisso, mai sintassi FTS5 grezza | Sicuro e tollerante |
| Analisi e "Chiedi" | funzioni chiuse in `ask/functions.py` su `keyword_stats`; le parole singole contenute in un'espressione già presente (≥ 70% delle volte) vengono nascoste; le domande pronte (`ask/plan.py` → `PRESETS`) non usano l'AI | Risposte veloci, gratuite e spiegabili |
| Fonti: diritto d'autore e privacy | solo titolo, estratto ≤ 300 caratteri, link, data, editore; commenti YouTube solo testo; da Reddit si rimuove "submitted by /u/…" | §3 e §9 della specifica |
| AI | interfaccia unica `LLMProvider`: Ollama (HTTP locale), Anthropic (**SDK ufficiale `anthropic`**, modello predefinito `claude-opus-5-5`, `fallbacks: "default"`, nessun parametro di campionamento), OpenAI/xAI/Gemini (Chat Completions via httpx), Perplexity (Agent API `/v1/agent`), "Apri nella chat" (appunti di Windows + browser, nessuna automazione dei siti) | Vedi §5 della specifica; endpoint verificati 2026-11-02 |
| Funzioni AI | ogni funzione ha due strade con la stessa validazione: provider oppure prompt + risposta incollata; se il provider non è disponibile si passa da soli alla chat dicendo perché | Degrado con eleganza |
| Generatore | una chiamata per richiesta (≤ 12 post), schema JSON tollerante (post fuori richiesta scartati, non rifiutati); ogni bozza salva un'istantanea delle fonti (`drafts.context`); controllo dei fatti deterministico in `generator/factcheck.py`; testi lunghi letti offline (pypdf, python-docx) | Costi prevedibili, rigenerazione e verifica anche dopo il ricalcolo dei temi |
| Prompt | `ai/prompt_templates/{it,en,es}/{nome}.md`, sezioni `# system` / `# user` / `# retry`, versione in testa; mai prompt nel codice | Versionati e traducibili |
| Output strutturati AI | JSON validato con schemi Pydantic; un nuovo tentativo, poi errore chiaro | — |
| "Chiedi" | l'AI produce un piano JSON validato che usa solo un elenco chiuso di funzioni di analisi; **mai SQL generato** | Sicurezza |
| Errori | il backend restituisce `{code, params}`; la UI li traduce. Mai stack trace nell'interfaccia | i18n e leggibilità |
| GitHub | repository **pubblico e separato** https://github.com/talonet73/taleport (licenza MIT, ramo `main`), distinto da TALedit e TALevent; aggiornamenti dall'ultima Release (`UPDATE_URL` in `core/settings.py`, tag `vX.Y.Z` = `__version__`). La CLI `gh` non è installata: le Release le crea l'utente dal sito, con `Setup-TALeport.exe` allegato e il testo da `CHANGELOG.md` | App gratuita, Releases leggibili senza token |
| Packaging | `packaging/build.ps1` → PyInstaller una cartella (`taleport.spec`: UI, `assets/brand`, dati del pacchetto, yake, metadati APScheduler) → Inno Setup per utente (`taleport.iss`, `AppMutex` = mutex dell'istanza singola, IT/EN/ES, disinstallazione che chiede se cancellare i dati); versione unica in `taleport/__init__.py` | Un comando per l'installer |
| Guida utente | pagina `/guide` con testi i18n (`guide.*`, elenchi con lo stesso numero di voci nelle tre lingue); `docs/guide-*.md` generati da `docs/build_guide.py` | Una sola fonte, sempre offline |
| Firma codice | **nessuna per ora**; la guida spiega l'avviso SmartScreen; in `packaging/` resta un punto di aggancio per `signtool` | Si aggiunge dopo senza toccare il codice |
| Riferimento grafico | nessuna immagine della dashboard: valgono le specifiche del §7 e i loghi | — |
| Tema | scelto dall'utente: Scuro (predefinito) / Chiaro / Come Windows. Logo scuro o chiaro in base al tema attivo | Richiesta dell'utente |
| Token di sessione nella UI | il backend apre `/#t=<token>`; la UI lo salva in `sessionStorage` e lo toglie dall'indirizzo | Funziona uguale nella finestra, in dev (Vite) e nel browser |
| Primo avvio | `first_run_completed` nelle impostazioni; finché è falso `Layout` mostra `FirstRunWizard` (6 passi, riusa `SecretRow` e `NewTopicForm`) | Nessuna configurazione duplicata |
| Backup | JSON `taleport-backup` / `taleport-topic` con `version`; mai chiavi API; si importa senza sovrascrivere; `first_run_completed` e `start_with_windows` non si ripristinano | Portabile e sicuro |
| Aggiornamenti | `update_url` (GitHub Releases API o JSON `{version, url, notes}`), controllo giornaliero all'avvio, stato in `settings._update_state`; si apre solo la pagina della versione | Nessun download o esecuzione automatica |
| File esportati | `core/exports.py`: cartella `exports\`, nomi controllati con regex, `os.startfile` | Un solo punto per PDF, backup, registro |
| Pulizia | `core/maintenance.py`: notizie non viste da `retention_months` mesi, registro e notifiche lette dopo 90 giorni; all'avvio e dopo ogni scansione | Privacy (§9) |
| Analisi video | `video/`: solo file dati dal cliente (nessun account, nessuno scraping); misure offline con FFmpeg di `imageio-ffmpeg` (tagli, pause, volume, fotogrammi) e faster-whisper `base` (modello scaricato una volta in `models\`); risultati a mano o letti dagli screenshot da un'AI con immagini (`LLMProvider.complete(..., images=)`, attributo `vision`); file in `videos\<cliente>\`; worker in coda + SSE `videos.changed` | Le API non danno la curva di permanenza e Instagram blocca i download senza login (verificato 2026-11-08) |
| Tono di voce | `voices/`: profili (istruzioni + frasi di esempio + argomenti collegati, uno per argomento) da documenti (prompt `voice_analysis`) o a mano; il tono scelto entra nei prompt come `tone`/`style_examples` ed è salvato nel contesto della bozza (`ctx.voice`); post da reference: prompt `reference_posts`, bozze `long_content` | Riusa i segnaposto esistenti dei prompt e la rigenerazione mantiene il tono |
| Migrazioni | `0001_init.sql` contiene solo `settings` e `logs`; ogni fase aggiunge la sua migrazione con le tabelle del §8 che usa | Lo schema nasce insieme al codice che lo usa |

## Stack e strumenti

- **Backend:** Python 3.12 (`py -3.12`), virtualenv in `backend/.venv`. FastAPI, uvicorn, pydantic v2, httpx, feedparser, APScheduler, yake, keyring, pystray, Pillow, reportlab, matplotlib, svglib, pypdf, python-docx.
- **Qualità backend:** pytest (+ `respx` per le risposte HTTP registrate), ruff (lint + format).
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS v4, react-router, TanStack Query, react-i18next, ECharts (dalla fase 3), lucide-react (icone). Qualità: `tsc --noEmit`, vitest. Colori solo tramite i token definiti in `src/index.css` (`bg-surface`, `text-muted`, `bg-accent-gradient`, variante `light:`…).
- **Packaging:** PyInstaller (una cartella) + Inno Setup 6 (installato con winget, per utente) → `Setup-TALeport.exe` (per utente, collegamento desktop, menu Start, disinstallazione pulita). Comando: `powershell -ExecutionPolicy Bypass -File packaging\build.ps1`.

## Struttura del progetto

```
TALeport/
├─ CLAUDE.md · PIANO.md · README.md · LICENSE
├─ assets/brand/            # taleport-logo-dark.svg, taleport-logo-light.svg, taleport-icon.svg, taleport.ico
├─ backend/
│  ├─ pyproject.toml
│  ├─ taleport/
│  │  ├─ main.py            # avvio: API, finestra, tray, scheduler, istanza singola
│  │  ├─ window.py · tray.py · autostart.py · server.py · single_instance.py
│  │  ├─ topics/            # modello, edizioni lingua+paese, persistenza
│  │  ├─ core/              # paths, config, logging, secrets, errors (codici errore)
│  │  ├─ db/                # connessione, migrations/NNNN_*.sql, repository
│  │  ├─ api/               # router FastAPI (uno per area) + SSE
│  │  ├─ collectors/        # google_news, rss, youtube, reddit, trends (+ base comune)
│  │  ├─ scan/              # orchestratore, dedup, scheduler, recupero
│  │  ├─ analysis/          # keywords, hot_score, stats, questions
│  │  ├─ ai/                # providers/, prompts/{it,en,es}/*.md, schemas, chat_handoff, usage/costi
│  │  ├─ generator/         # post per piattaforma, fact-check, contenuti lunghi
│  │  ├─ ask/               # schema piano, funzioni di analisi, esecutore
│  │  ├─ reports/           # PDF, grafici, modelli
│  │  ├─ voices/            # profili di tono di voce
│  │  ├─ video/             # analisi video clienti: FFmpeg, trascrizione, misure, analisi AI, PDF
│  │  ├─ notifications/
│  │  └─ resources/         # stopword, valori predefiniti (orari social, prezzi AI)
│  └─ tests/                # fixtures/ con risposte registrate
├─ frontend/
│  ├─ src/
│  │  ├─ app/               # layout (menu laterale, barra in alto), router, tema
│  │  ├─ pages/             # una cartella per voce di menu
│  │  ├─ components/        # UI riutilizzabile, grafici
│  │  ├─ api/               # client tipizzato + SSE
│  │  └─ i18n/locales/      # it.json, en.json, es.json
│  └─ (vite, tailwind, tsconfig)
├─ packaging/               # build_icon, taleport.spec, taleport.iss, script di build
└─ docs/                    # guida utente IT/EN/ES
```

## Convenzioni

- **Python:** type hint ovunque, `snake_case`, moduli piccoli; nessuna logica nei router (vanno nei servizi). Ogni accesso alla rete passa da un client httpx condiviso con timeout e ritentativi con attesa crescente.
- **TypeScript:** componenti in `PascalCase`, hook `useXxx`; tutte le stringhe visibili tramite `t('area.chiave')`; chiavi i18n uguali nei tre file (un test lo verifica).
- **Tema:** colori come token Tailwind/variabili CSS (scuro predefinito, chiaro disponibile): sfondo `#1E1B4B`–`#2E2A78`, riquadri `#2F2C85`–`#3B3A9A`, accenti `#22D3EE` `#38BDF8` `#2DD4BF`, testo `#E0E7FF` `#A5B4FC`; raggio 12–16 px; testo lungo 15–16 px; contrasto WCAG AA.
- **Fonti:** si salvano solo titolo, breve estratto, link, data, fonte, lingua. Dai commenti solo il testo, mai i nomi utente.
- **Prompt AI:** file modello versionati in `backend/taleport/ai/prompts/`, nelle tre lingue; mai prompt scritti nel codice.
- **Database:** ogni modifica allo schema è una nuova migrazione; mai modificare migrazioni già rilasciate.
- **Test:** ogni fase aggiunge i test della sua logica (collettori con risposte registrate, dedup, punteggio caldo, statistiche, piani "Chiedi", PDF).

## Comandi (validi dalla fase 1)

```bash
# backend (dalla cartella backend/)
py -3.12 -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format .
.venv/Scripts/python -m taleport                # app completa (usa frontend/dist)
.venv/Scripts/python -m taleport --dev          # API su :8765 + finestra sul server Vite :5173
.venv/Scripts/python -m taleport --no-window    # solo API, stampa l'URL da aprire nel browser
# frontend (dalla cartella frontend/)
npm install
npm run dev | npm run build | npm run typecheck | npm test
npm run icon       # rigenera assets/brand/taleport.ico e public/favicon.svg
```

`TALEPORT_DATA_DIR` sposta la cartella dati (usato dai test e per le prove manuali).

## Riprendere il lavoro

- Stato delle fasi e cosa resta: [PIANO.md](PIANO.md) (sezione "Stato attuale" in cima). Si riprende dalla prima fase non completata, con l'ok dell'utente.
- **Dati di sviluppo:** le prove manuali usano `devdata/` nella radice del progetto (escluso da git): contiene il database con l'argomento d'esempio, le notizie raccolte, i temi e le bozze. Avviare sempre così, per non toccare la cartella vera dell'utente (`%LOCALAPPDATA%\TALeport`):

```powershell
$env:TALEPORT_DATA_DIR = "$PWD\devdata"   # dalla radice del progetto
backend\.venv\Scripts\python.exe -m taleport --no-window --port 8790
```

- Prima di avviare l'app, chiudere eventuali istanze rimaste aperte (istanza singola).
