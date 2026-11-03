# TALeport — piano di sviluppo

Legenda: `[ ]` da fare · `[x]` fatto · `[~]` in corso · `[!]` bloccato o da verificare

Regola: a fine fase l'app si avvia, i test passano, questo file è aggiornato, segue un riepilogo. Si passa alla fase successiva **solo con l'ok dell'utente**.

## Stato attuale

- [x] Specifica letta, domande poste e risposte ricevute
- [x] `CLAUDE.md` e `PIANO.md` creati
- [x] Loghi ricevuti; nessuna immagine della dashboard a parte → si seguono le specifiche del §7
- [x] **Fase 1 completata** (2026-11-02)
- [x] **Fase 2 completata** (2026-11-02)
- [x] **Fase 3 completata** (2026-11-02)
- [x] **Fase 4 completata** (2026-11-02)
- [x] **Fase 5 completata** (2026-11-02)
- [x] **Fase 6 completata** (2026-11-02)
- [x] **Fase 7 completata** (2026-11-02)
- [x] **Fase 8 completata** (2026-11-02)
- [x] **Fase 9 completata** (2026-11-02)
- [~] **Fase 10** (2026-11-03): installer 1.0.0 pronto e provato, repository collegato; codice e Release 1.0.0 su GitHub; resta solo la prova su un Windows pulito

---

## Fase 1 — Fondamenta ✅
- [x] `git init`, `.gitignore`, `README.md`, `LICENSE` (MIT)
- [x] Loghi in `assets/brand/`; `npm run icon` genera `taleport.ico` (16, 32, 48, 64, 128, 256 px) e la favicon
- [x] Pacchetto backend `taleport` (pyproject, virtualenv, ruff, pytest)
- [x] Percorsi dati in `%LOCALAPPDATA%\TALeport\`, log a rotazione
- [x] SQLite + sistema di migrazioni (`PRAGMA user_version`, una transazione per file) + `0001_init.sql` con `settings` e `logs`. Le tabelle di dominio del §8 arrivano con una migrazione per fase, insieme al codice che le usa
- [x] Impostazioni (tabella `settings` + API, validate; un valore corrotto torna al predefinito)
- [x] Segreti in `keyring` (salva / cancella / "è impostata?"; i valori non escono mai dall'API) — verificato col Gestore credenziali vero
- [x] FastAPI su `127.0.0.1` con porta casuale + token di sessione + controllo dell'header Host + SSE
- [x] Finestra pywebview (minimo 1280×720) + istanza singola (la seconda copia porta in primo piano la prima)
- [x] Frontend: Vite + React + TS + Tailwind v4, token del tema scuro e chiaro
- [x] Layout: menu laterale (10 voci con icone, voce attiva, riquadro stato scansione e spesa API), barra in alto (casella "Chiedi", pillole, campanella, selettore AI attiva)
- [x] i18n IT/EN/ES + test che chiavi e segnaposto coincidano nei tre file
- [x] Pagine segnaposto per ogni voce; Impostazioni con lingua, tema (Scuro / Chiaro / Come Windows), AI predefinita e chiavi API
- [x] Test: migrazioni, impostazioni, segreti (con keyring finto), autenticazione API — 21 test backend + 4 frontend

Note:
- Casella "Chiedi", "Scansiona ora" e "Nuovo post" sono visibili ma disattivate (arrivano nelle fasi 2, 5 e 6).
- La spesa API è mostrata in USD (valuta dei listini dei provider); da decidere in fase 7 se convertirla.

## Fase 2 — Argomenti + scansione ✅
- [x] Migrazione `0002_topics_scans.sql`: `topics`, `topic_keywords`, `topic_sources`, `style_examples`, `scans`, `items`, `item_topics`, `api_quota`
- [x] CRUD argomenti (massimo 10): parole chiave per lingua, esclusioni, hashtag, osservati speciali (feed RSS, canali YouTube, subreddit, normalizzati da link o nomi), edizioni lingua+paese, pubblico, tono, social, fino a 5 esempi di stile
- [x] Client HTTP comune: timeout, 3 tentativi con attesa crescente, `Retry-After` e `X-Ratelimit-*` rispettati, cadenza minima per host
- [x] Google News RSS (12 edizioni IT/EN/ES, verificate dal vivo it-IT, en-US, en-GB, es-ES, es-MX) + feed RSS dell'utente
- [x] YouTube Data API v3 (chiave dell'utente): ricerca per lingua, canali seguiti tramite playlist dei caricamenti (1 unità invece di 100), statistiche, commenti più rilevanti solo come testo; contatore quota con azzeramento a mezzanotte del Pacifico
- [x] Reddit: **solo feed RSS pubblici** (vedi note); una ricerca per argomento + un feed unico per i subreddit seguiti; se bloccato, sospeso per il resto della scansione tenendo i risultati già presi
- [x] Google Trends: **feed RSS pubblico "Tendenze del momento"** per paese, filtrato con le parole chiave (vedi note)
- [x] Deduplicazione: URL canonico (senza parametri di tracciamento, varianti www/m/youtu.be) + titoli identici o quasi (Jaccard ≥ 0,8, numeri sempre considerati, titoli corti mai fusi)
- [x] Orchestratore: un thread per fonte, una fonte che fallisce non blocca le altre, avanzamento per argomento e fonte via SSE, errori nel registro (`logs`)
- [x] Pianificazione giornaliera (APScheduler) + recupero all'avvio se l'orario è stato saltato + "Scansiona ora" (tutto o un argomento) + annullamento
- [x] Icona nella tray (Apri / Scansiona ora / Esci, nelle 3 lingue), chiusura finestra → tray, avvio con Windows ridotto (`--minimized`)
- [x] UI: pagina Argomenti, editor completo, elementi raccolti con link aperti nel browser predefinito, pannello di avanzamento, impostazioni di scansione, quota YouTube
- [x] Test: 61 backend (collettori con risposte registrate dal vivo, deduplicazione, recupero, quota, API) + 4 frontend

Note:
- **Reddit:** il JSON anonimo risponde 403; Reddit non concede più chiavi API in autonomia (approvazione manuale da nov. 2025, accesso pubblico in chiusura). Tolta l'opzione "app Reddit facoltativa". I feed RSS anonimi oggi concedono circa **1 richiesta al minuto**: la cadenza si adatta da sola alle intestazioni di Reddit, quindi con molti argomenti la parte Reddit della scansione può richiedere diversi minuti (le altre fonti finiscono prima).
- **Google Trends:** pytrends e trendspy sono abbandonate; il feed RSS ufficiale delle tendenze è stabile ma dà solo le ricerche di tendenza del giorno per paese, non l'interesse nel tempo di una parola qualsiasi.
- Verificato dal vivo: scansione di un argomento IT+EN in 14 s, 44 notizie e 42 post Reddit; alla seconda scansione 40 notizie su 44 riconosciute come doppioni.
- La riduzione nella tray e l'avvio con Windows non hanno test automatici (servono finestra e registro reali): da provare a mano.

## Fase 3 — Analisi statistica + Oggi ✅
- [x] Migrazione `0003_analysis.sql`: `keyword_stats`, `themes`, `theme_items`, cache `terms`/`hashtags` sugli elementi
- [x] Riconoscimento della lingua (IT/EN/ES, a parole funzione) per gli elementi senza lingua
- [x] Estrazione parole chiave con YAKE (fino a 2 parole, 6 per elemento, ~2 ms/elemento) + pulizia elisioni italiane, parole vuote e parole troppo generiche (`resources/stopwords/`); hashtag da titoli, estratti e commenti
- [x] `keyword_stats` giornaliere per argomento, lingua e fonte (numero di elementi che citano la parola)
- [x] Temi senza AI: raggruppamento per parole chiave condivise, escludendo le parole dell'argomento; titolo, parole correlate, elemento rappresentativo
- [x] Punteggio caldo 0–100 con 4 componenti spiegate (volume vs media dei giorni osservati, crescita su ieri, fonti diverse, volume assoluto) + tendenza In crescita / In calo / Stabile / Nuovo
- [x] Domande della gente da commenti YouTube e post Reddit
- [x] Analisi automatica a fine scansione + `POST /api/analysis/run`
- [x] Schermata Oggi: 4 riquadri numerici + per ogni argomento attivo i 5 temi più caldi, con Genera post / Cerca su X con Grok (visibili, attivi nelle fasi 4–5) / Dettaglio
- [x] Dettaglio tema: riepilogo, "perché è caldo", grafico a 7 giorni (ECharts, crosshair e tooltip, tabella alternativa, colori validati per tema scuro e chiaro), domande, elementi con link
- [x] Plurali corretti nelle 3 lingue
- [x] Test: 74 backend (lingua, termini, domande, punteggio, temi, analisi completa, storico) + 4 frontend

Note:
- **"Già trattato"** richiede i post pubblicati (tabelle `drafts`/`publications`): spostato alla fase 5, quando nascono le bozze.
- **Angolo suggerito** e riassunto scritto: arrivano con l'AI (fase 4); senza AI il dettaglio mostra un riepilogo statistico.
- Con pochi giorni di dati quasi tutti i temi risultano "Nuovo": il confronto con la media diventa significativo dopo qualche giorno di scansioni.
- Verificato su dati reali (90 elementi): 8 temi in 0,25 s, es. Instagram, Freelance work, TikTok, Black Friday, Hong Kong/HSBC.

## Fase 4 — Livello AI ✅
- [x] Interfaccia unica `LLMProvider` (`ai/providers/`) + registro dei provider (`ai/registry.py`)
- [x] Ollama: rilevamento (installato / non avviato / senza modelli), elenco modelli, chiamate locali gratuite
- [x] Anthropic con l'SDK ufficiale `anthropic` (modello predefinito `claude-opus-5-5`, fallback lato server `fallbacks: "default"` sui rifiuti, gestione `stop_reason: refusal`)
- [x] OpenAI, xAI e Gemini via Chat Completions (Gemini tramite il livello compatibile OpenAI); Perplexity via **Agent API** (`/v1/agent`, la vecchia Sonar Chat Completions è confluita qui); elenco modelli dove l'API lo offre
- [x] "Apri nella chat": prompt sempre copiato negli appunti (via Windows, nessun permesso del browser), sito aperto nel browser predefinito, casella "Incolla qui la risposta" con la stessa validazione; precompilazione via URL solo come opzione sperimentale (non verificabile senza account)
- [x] Prompt in file modello versionati IT/EN/ES (`ai/prompt_templates/`)
- [x] Risposte JSON validate con schema, un nuovo tentativo con l'errore, poi messaggio chiaro; risposte incollate tollerate anche dentro blocchi di codice
- [x] Temi: titolo, riassunto, angolo suggerito e unione dei temi doppi; conservati se l'analisi del giorno viene ricalcolata; automatici dopo ogni scansione se l'AI predefinita è Ollama o una chiave API
- [x] "Crea con l'AI" nell'editor argomenti (compila i campi, l'utente rivede e salva)
- [x] "Cerca su X con Grok": prompt per grok.com (gratis) con risposta incollata, oppure API xAI con lo strumento `x_search` (a pagamento); salvata come fonte "X via Grok" del tema
- [x] Registro uso e costi (`ai_usage`) con stima da listino (`resources/ai_pricing.json`) o costo reale quando il provider lo comunica; spesa del mese nel menu laterale
- [x] Impostazioni AI: AI predefinita, sito di chat, modello per provider, prova di connessione, indirizzo Ollama
- [x] Degrado: senza AI disponibile si passa da soli ad "Apri nella chat" spiegando il motivo
- [x] Test: 98 backend (prompt nelle 3 lingue, estrazione JSON, nuovo tentativo, forme HTTP dei provider, fallback Anthropic, funzioni AI complete) + 4 frontend

Note:
- **Non provato con chiamate reali** a nessun provider: sul PC non ci sono Ollama né chiavi API. Le forme delle richieste seguono la documentazione ufficiale (verificata il 2026-11-02) e sono coperte da test con risposte simulate. Primo controllo consigliato: Impostazioni → Prova.
- Prezzi e modelli predefiniti presi dal listino Anthropic e dalla tabella modelli di Perplexity (che riporta anche i prezzi di OpenAI, Google e xAI): sono stime modificabili; il tetto di spesa arriva nella fase 7.
- Verificato nell'app: "Migliora con l'AI" in modalità chat (prompt copiato, risposta incollata, 3 temi aggiornati) e "Cerca su X" con risposta salvata.
- Corretti durante la prova: doppioni con stesso titolo ed estratto (post ripetuti su più subreddit), ricerca su X basata sulla parola chiave invece che sul titolo lungo scritto dall'AI, nomi dei provider nei messaggi.

## Fase 5 — Generatore post ✅
- [x] Migrazione `0005_drafts.sql`: `drafts` (con istantanea delle fonti per rigenerare e ricontrollare) e `publications`; etichetta "Già trattato" sui temi simili a post pubblicati negli ultimi 30 giorni (stessa parola chiave o titolo simile), anche dopo il ricalcolo dei temi
- [x] Scelte: tema (preselezionato da "Genera post" in Oggi), social, lingue di uscita, varianti 1–3, tono, AI; massimo 12 post per richiesta
- [x] Formati per LinkedIn, Instagram (carosello), Facebook, YouTube (titolo, scaletta, miniatura), TikTok/Reels (gancio dei primi 3 secondi e script scena per scena)
- [x] Prompt `post_generation` / `long_content` versionati IT/EN/ES con scheda argomento, esempi di stile, temi già trattati, regole per piattaforma e fonti numerate
- [x] Fonti usate (link), controllo dei fatti locale (numeri, citazioni e nomi assenti dalle fonti; hashtag, tempi degli script e numeri piccoli esclusi), idea immagine con prompt da copiare
- [x] Copia, Rigenera (versione diversa dalla precedente), Modifica (avvisi ricalcolati), Aggiungi al calendario (data e ora salvate; la vista calendario è nella fase 7), Segna come pubblicato (con link facoltativo) e annulla
- [x] Da contenuto lungo: testo incollato o file PDF / DOCX / TXT (estratto offline, max 15 MB), serie da 1 a 10 post per social, stile da un argomento; testo oltre 60.000 caratteri accorciato con avviso
- [x] Statistiche reali in Oggi: post generati oggi, post pubblicati in settimana; "Nuovo post" nella barra in alto apre il Generatore
- [x] Test: 109 backend (controllo dei fatti, rendering, estrazione da TXT/DOCX/PDF, ciclo di vita delle bozze, "già trattato", serie da contenuto lungo, API) + 4 frontend

Note:
- Verificato nell'app (modalità chat, risposte incollate): tema → 3 bozze LinkedIn / Instagram / TikTok; modifica, calendario, pubblicazione con link, "Già trattato" e statistiche aggiornati; contenuto lungo → serie di 2 post con il dato inventato segnalato.
- Corretti durante la prova: «Il Sole 24 Ore» spezzato in nome + numero, hashtag letti come nomi, tempi degli script TikTok letti come numeri, hashtag ripetuti due volte nella scheda TikTok; una risposta con un post in lingua inattesa non fa più ripetere tutta la chiamata.
- Il controllo dei fatti è prudente: segnala anche sigle non presenti nelle fonti (es. «PMI» se il testo diceva «piccole e medie imprese»). Gli avvisi delle bozze create prima di una correzione si aggiornano quando la bozza viene modificata o rigenerata.
- Il caricamento di un file vero è coperto dai test (TXT, DOCX, PDF senza testo) ma non provato a mano: il selettore file non si può pilotare dal browser di prova.

## Fase 6 — Settimana, Tendenze parole, Chiedi ✅
- [x] Schermata Settimana: 4 riquadri (elementi, temi, post generati, pubblicati), elementi al giorno, per fonte, temi più caldi, parole principali
- [x] Tendenze parole: filtri in una riga (7 / 30 giorni / personalizzato, lingua, argomenti); 20 parole e 20 hashtag con percentuale; emergenti / in calo rispetto al periodo precedente; andamento delle 5 principali; nuvola di parole; confronto per lingua e per fonte
- [x] Funzioni di analisi chiuse (`ask/functions.py`): `top_keywords`, `emerging_keywords`, `topic_trend`, `compare_periods`, `compare_languages`, `compare_sources` (in più, per il confronto per fonte), `top_themes`, `post_performance`, più `daily_items` per la Settimana
- [x] Casella "Chiedi" nella barra in alto: 7 domande pronte che rispondono subito senza AI; domande libere → l'AI produce un piano JSON validato (schema chiuso, max 4 passi, nessun SQL) → grafici + risposta scritta generata dai dati; funziona anche con "Apri nella chat"
- [x] Palette per grafici a più serie validata con lo script dataviz su entrambi i temi (ciano, arancio, viola, giallo, magenta); legenda, tooltip e tabella sempre presenti
- [x] Test: 119 backend (periodi, funzioni su dati di 14 giorni, piani validi e rifiutati, domande pronte, AI e risposta incollata, API) + 4 frontend

Note:
- Verificato nell'app su `devdata/`: Settimana, Tendenze, domanda pronta dal menu della barra in alto, domanda libera con piano incollato (confronto per fonte).
- Corretti durante la prova: parole singole ripetute sotto la loro espressione («intelligenza», «artificiale» sotto «intelligenza artificiale»), tutte le parole «nuove» quando non c'è storico, etichette delle linee sovrapposte (tolte: restano legenda, tooltip e tabella), menu delle domande pronte che si riapriva da solo.
- Con un solo giorno di dati i grafici a 7/30 giorni sono quasi vuoti e le parole emergenti non compaiono: diventano utili dopo qualche giorno di scansioni.
- Esportazione PDF delle risposte di "Chiedi": fase 8. Like e commenti dei post in `post_performance`: fase 7.

## Fase 7 — Archivio, risultati, calendario, notifiche, spesa ✅
- [x] Migrazione `0006_archive_results_notifications.sql`: `post_results`, `notifications`, indici FTS5 su bozze e temi (tenuti allineati da trigger, accenti ignorati)
- [x] Archivio: schede Post e Temi, ricerca a testo libero (parole come prefissi: «intel artif» trova «intelligenza artificiale»), filtri per stato, social, argomento e periodo, «Mostra altri»
- [x] Risultati inseriti a mano (like, commenti, condivisioni, visualizzazioni) dall'Archivio o dalla scheda della bozza; riquadro «Cosa funziona» con le medie per social; motivazione sempre scritta coi numeri («Suggerito perché i post su LinkedIn hanno avuto più commenti (in media 13)») nel Generatore, e «Priorità» sui temi di Oggi simili a post andati bene; "Chiedi" → `post_performance` ora usa i risultati
- [x] Calendario settimanale e mensile: bozze trascinate sui giorni (anche dalla lista «Da programmare»), clic su una bozza per scegliere giorno e ora da tastiera, post pubblicati come promemoria; orari consigliati per social (predefiniti in `resources/posting_times.json`, modificabili nelle Impostazioni) e orario «imparato» dai risultati (l'ora con più interazioni, da 3 post in su)
- [x] Notifiche: campanella con contatore aggiornato in diretta (SSE), segna come lette, cancella le lette, clic che apre la pagina giusta; notifica di Windows dall'icona nella tray (attivabile nelle Impostazioni). Eventi: scansione completata o recuperata (per le scansioni avviate a mano solo campanella), fonte non funzionante (una volta al giorno per fonte), picco su un argomento (almeno 10 elementi e il doppio della media dei 7 giorni prima, con almeno 3 giorni di storico), tetto di spesa vicino o raggiunto (una volta al mese)
- [x] Spesa API: riquadro nelle Impostazioni con totale del mese, barra rispetto al tetto, spesa per provider, ultime chiamate con costo stimato o reale; tetto mensile e soglia di avviso; raggiunto il tetto le funzioni AI passano da sole ad «Apri nella chat» (la ricerca X via API e la prova di connessione danno un errore chiaro), Ollama resta disponibile; tetto visibile anche nel menu laterale
- [x] Test: 131 backend (ricerca e filtri dell'archivio, risultati e motivazioni, priorità dei temi, calendario e orari imparati, notifiche e duplicati, picchi, tetto di spesa, API) + 4 frontend

Note:
- Notifiche di Windows tramite pystray (icona già presente nella tray) invece di Windows-Toasts: nessuna libreria in più, e Windows-Toasts in un'app non registrata come pacchetto mostrerebbe «Python» come mittente. Funziona solo con la finestra (la modalità `--no-window` non ha tray); provato con uno script a parte.
- Verificato nell'app su `devdata/`: trascinamento (eventi di trascinamento inviati via JavaScript: lo strumento di prova non simula il drag-and-drop nativo) e spostamento da tastiera, vista mensile, ricerca nell'archivio, risultati salvati, tetto di spesa, scansione vera → «Scansione completata» nella campanella in diretta, clic che apre Oggi.
- Corretti durante la prova: medie a 0 per le metriche non inserite (ora «–»), nome del social tagliato nelle caselle del calendario, campi dei filtri senza nome per gli screen reader, collegamento «Modifica gli orari» che non scorreva al riquadro, spesa del mese ripetuta in due riquadri delle Impostazioni.
- Le chiamate AI a pagamento bloccate dal tetto sono coperte dai test ma non provate dal vivo (sul PC non ci sono chiavi API). Priorità e orari imparati diventano visibili quando ci sono risultati su più post.

## Fase 8 — Report PDF ✅
- [x] Pacchetto `reports/`: contenuto come dati (`model.py`, `builder.py`) separato dall'impaginazione (`pdf.py` con ReportLab, `charts.py` con matplotlib → SVG → svglib); dipendenze aggiunte: reportlab, matplotlib, svglib
- [x] Report giornaliero, settimanale e Tendenze parole; pulsante «Esporta PDF» su Oggi, Settimana, Tendenze e nelle risposte di "Chiedi" (il piano validato viene rieseguito sul server, mai fidandosi dei dati inviati dalla pagina)
- [x] Report personalizzato: titolo, periodo (7/30 giorni, questo mese, settimana scorsa, date a scelta), argomenti, lingue, 8 sezioni (riepilogo, temi caldi, parole e hashtag, emergenti/in calo, andamento, confronto per lingua e fonte, post generati e pubblicati, risultati dei post) in ordine fisso
- [x] Copertina con logo (TALeport o quello dell'utente: PNG/JPG/SVG fino a 2 MB, controllato prima di salvarlo), nome in copertina, periodo e data di creazione; indice con numeri di pagina; segnalibri del PDF; piè di pagina con titolo, periodo e «Pagina N»; link alle fonti cliccabili; grafici vettoriali con il testo vero (selezionabile) e la palette validata dell'app
- [x] Tema chiaro predefinito, scuro a scelta (predefinito nelle Impostazioni, modificabile per ogni PDF); font DejaVu Sans incluso in matplotlib (accenti, «», virgolette in IT/EN/ES, offline)
- [x] Modelli salvati (migrazione `0007_report_templates.sql`): salva, modifica, elimina, «Rigenera» con un clic (i periodi relativi si spostano da soli); ultima generazione mostrata
- [x] PDF salvati in `exports\` della cartella dati, aperti col lettore PDF di Windows («Apri», «Mostra nella cartella»); elenco degli ultimi 20; nomi di file controllati (niente percorsi)
- [x] Test: 143 backend (contenuto di ogni report, ordine delle sezioni e filtri, report di "Chiedi" dal piano, PDF con copertina/indice/numeri di pagina/link/segnalibri nei due temi, periodo vuoto, file e nomi non sicuri, modelli, logo, API) + 4 frontend

Note:
- Verificato nell'app su `devdata/`: report settimanale (chiaro), personalizzato «ultimi 30 giorni» salvato come modello e rigenerato (scuro), risposta di "Chiedi" esportata; pagine controllate convertendole in immagini.
- Corretti durante la prova: riquadri dei numeri e tabelle che sporgevano dal margine, conteggio dei temi fermo a 10, date sovrapposte sull'asse dei grafici (ora «2 nov»), lettere dei grafici disegnate male (ora testo vero col font registrato), legenda che restringeva il grafico, periodo in copertina di "Chiedi" che mostrava solo il secondo periodo, confronto tra periodi con parole spezzate («intelligenza» accanto a «intelligenza artificiale»), campo nascosto del logo che faceva scorrere la pagina delle Impostazioni.
- Il riepilogo usa i riassunti dei temi già scritti dall'AI: creare un report non fa mai chiamate all'AI.
- Nel pannello del browser i PDF non si aprono (finestra «Salva con nome»); nell'app vera si aprono col lettore PDF di Windows.

## Fase 9 — Primo avvio, backup, aggiornamenti, registro errori ✅
- [x] Primo avvio guidato in 6 passi, finché non è completato o saltato («Esci dalla configurazione»); ripetibile dalle Impostazioni:
  1. lingua e tema (applicati subito);
  2. AI: rileva Ollama (installato, avviato, modelli) e spiega come installarlo con il link ufficiale; AI predefinita; chiavi API facoltative;
  3. chiave YouTube facoltativa con guida in 5 passi e link a Google Cloud (senza chiave YouTube viene saltato);
  4. orario della scansione e avvio con Windows;
  5. primo argomento (nome, Paesi/lingue, parole chiave, «Crea con l'AI»), o quelli già presenti;
  6. scansione di prova con barra di avanzamento e risultato.
- [x] Backup in un unico file JSON (impostazioni, argomenti, modelli di report; mai chiavi API, notizie o bozze), anteprima prima di importare, importazione senza sovrascrivere (nomi doppi → «Nome (2)», limite di 10 argomenti rispettato, modelli identici non duplicati, modelli collegati agli argomenti per nome); «Condividi» e «Importa da file» per un singolo argomento nella pagina Argomenti
- [x] Controllo aggiornamenti: indirizzo configurabile (API di GitHub Releases o file JSON semplice, solo https), controllo manuale o automatico una volta al giorno all'avvio, notifica «Nuova versione», pulsante che apre la pagina della versione; l'app non scarica né esegue nulla da sola
- [x] Registro errori nelle Impostazioni: filtro per livello, messaggi tradotti, svuota, esporta in un file .txt (versione, Windows, eventi con dettagli tecnici, ultime 500 righe del log tecnico)
- [x] Pulizia automatica all'avvio e dopo ogni scansione: notizie non più viste da N mesi (3/6/12/24, oppure «sempre»; predefinito 6), registro e notifiche lette dopo 90 giorni; statistiche delle parole, temi, bozze e report restano; «Pulisci ora»
- [x] File esportati (PDF, backup, argomenti, registro) gestiti in un unico modulo `core/exports.py`: cartella `exports\`, nomi controllati, apertura con il programma di Windows
- [x] Test: 151 backend (pulizia, backup senza segreti e ripristino su un altro database, file non validi, limite argomenti, condivisione di un argomento, modelli non duplicati, versioni e formati delle release, controllo aggiornamenti con risposte simulate, registro, API) + 4 frontend

Note:
- Verificato nell'app su `devdata/`: configurazione guidata completa (anche in inglese), rilevamento di Ollama assente, scansione di prova (92 elementi, 5 nuovi), backup creato e reimportato (argomento e modello duplicati poi rimossi dai dati di prova), registro con messaggi tradotti. La lettura di una risposta vera dell'API di GitHub Releases è stata provata a parte.
- Corretti durante la prova: pulsante «Salta questo passo» anche con argomenti già presenti, etichetta «Finisci senza scansione» durante la scansione (ora «Vai alla dashboard»), modelli di report duplicati reimportando lo stesso backup.
- L'indirizzo degli aggiornamenti è vuoto finché il repository `taleport` non esiste su GitHub: si imposta nella fase 10.
- [!] Una volta la suite backend ha dato 1 test fallito, che non si è più ripresentato in 8 esecuzioni successive: probabile test instabile, da tenere d'occhio.

## Fase 10 — Packaging
- [x] Inno Setup 6.7 installato con winget (per utente)
- [x] PyInstaller una cartella (`packaging/taleport.spec`, avvio da `packaging/launcher.py`): UI compilata, loghi, risorse del pacchetto, dati di yake, metadati di APScheduler; finestra senza console; dati di versione nel `.exe` (Proprietà → Dettagli); versione 1.0.0 da `backend/taleport/__init__.py`
- [x] Inno Setup (`packaging/taleport.iss`) → `packaging/output/Setup-TALeport.exe` (46,5 MB): per utente senza permessi di amministratore, in `%LOCALAPPDATA%\Programs\TALeport`; collegamento sul desktop (facoltativo) e nel menu Start; installer in italiano, inglese e spagnolo; chiede di chiudere l'app se è aperta (mutex); la disinstallazione rimuove programma, collegamenti e avvio con Windows, e chiede se eliminare anche i dati (predefinito: no)
- [x] `packaging/build.ps1`: UI, icona se manca, PyInstaller, firma facoltativa (`TALEPORT_SIGN_CERT` / `TALEPORT_SIGN_PASSWORD`, signtool), Inno Setup
- [x] Guida utente IT/EN/ES dentro l'app (pulsante «?» nella barra in alto): cosa fa, fonti e piattaforme non monitorate (Instagram, TikTok, Facebook, LinkedIn, X), lavoro quotidiano, AI, report, dati e privacy, avviso SmartScreen, problemi comuni; stessa guida in `docs/guide-{it,en,es}.md` generata da `docs/build_guide.py`; README aggiornato
- [x] Repository GitHub pubblico separato creato dall'utente: https://github.com/talonet73/taleport (ramo `main`); indirizzo degli aggiornamenti predefinito `https://api.github.com/repos/talonet73/taleport/releases/latest` (si può svuotare per spegnere il controllo); link nell'installer e nel README; `CHANGELOG.md` con le note della 1.0.0
- [x] Push su GitHub (2026-11-03, ramo `main`); commit con l'indirizzo privato di GitHub `178192068+talonet73@users.noreply.github.com` (impostato in `.git/config` del progetto)
- [x] Prima Release pubblicata dall'utente (2026-11-03): https://github.com/talonet73/taleport/releases/tag/v1.0.0 con `Setup-TALeport.exe` (48.712.420 byte, uguale al file compilato); il controllo aggiornamenti dell'app la legge e la riconosce come versione attuale
- [~] Test di accettazione: provato su questo PC con una cartella dati vuota (non su un Windows pulito)

Note:
- Provato l'eseguibile compilato: primo avvio con la configurazione guidata, Ollama rilevato come assente, Gestore credenziali, creazione di un argomento, scansione vera (62 elementi), Oggi con 4 temi, PDF personalizzato scuro con grafici e logo, ripresa della scansione mancata.
- Provato l'installer: installazione silenziosa per utente (programma, disinstallatore, desktop, menu Start, voce in «App installate» 1.0.0), avvio dell'app installata con la finestra, istanza singola (il secondo avvio porta in primo piano la finestra), disinstallazione pulita senza residui. La cartella dati reale `%LOCALAPPDATA%\TALeport` non è mai stata toccata: tutte le prove hanno usato cartelle temporanee.
- Corretto durante la prova: il messaggio innocuo di Windows quando una pagina chiude la connessione («ConnectionResetError») finiva nel log come errore; ora viene ignorato.
- Non provati: la domanda «eliminare anche i dati?» della disinstallazione (in modalità silenziosa viene saltata), la firma del codice (nessun certificato), l'avviso SmartScreen (compare solo su file scaricati da internet), un Windows senza WebView2 (preinstallato su Windows 10 aggiornato e Windows 11).
- Criterio di accettazione completo (10 argomenti, post tramite «Apri nella chat», Tendenze, PDF personalizzato su un Windows pulito): da fare installando `Setup-TALeport.exe` su un altro PC o in una macchina virtuale.
