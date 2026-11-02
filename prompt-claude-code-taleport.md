# Prompt per Claude Code — App desktop "TALeport"

> Copia tutto quello che segue in Claude Code. Allega anche l'immagine di riferimento della dashboard (look and feel).

Il nome dell'app è **TALeport** (scritto esattamente così: "TAL" maiuscolo, "eport" minuscolo). Usalo nel titolo della finestra, nell'installer, nel menu Start, nella copertina dei PDF e nei nomi interni (`taleport` per pacchetti e cartelle).

**Logo:** nella scritta TALeport la lettera "p" è disegnata come una **lente di ingrandimento**: l'anello con il vetro è la pancia della "p", il manico verticale è la sua asta (azzurro/verde acqua). Ti allego i file:
- `taleport-logo-dark.svg` → per l'interfaccia (tema scuro): in alto nel menu laterale e nella schermata di avvio;
- `taleport-logo-light.svg` → per il tema chiaro e la copertina dei PDF;
- `taleport-icon.svg` → solo la "p"-lente, per l'icona dell'app: genera da qui `taleport.ico` (16, 32, 48, 64, 128, 256 px) per eseguibile, installer, collegamenti, tray e notifiche.
Il testo nei file SVG è già convertito in tracciati, quindi non serve nessun font. Mettili in `assets/brand/`.

---

## Ruolo e modo di lavorare

Sei uno sviluppatore senior. Devi costruire da zero un'applicazione desktop per Windows, distribuita come installer `.exe`, per social media strategist e social media manager.

Regole di lavoro:
1. **Prima di scrivere codice**, leggi tutto questo documento, poi fammi al massimo 5 domande sui punti davvero ambigui. Dopo le mie risposte, crea un file `CLAUDE.md` con decisioni, struttura del progetto e convenzioni, e un file `PIANO.md` con le fasi e le checklist qui sotto.
2. Lavora **per fasi** (vedi "Piano di sviluppo"). Alla fine di ogni fase: l'app deve avviarsi, i test devono passare, aggiorni `PIANO.md` e mi fai un riepilogo breve. Non passare alla fase successiva senza il mio ok.
3. Codice, commenti e nomi tecnici in inglese; **tutta l'interfaccia utente in italiano, inglese e spagnolo** (i18n, nessuna stringa scritta direttamente nei componenti).
4. Se una fonte o un'API non funziona come descritto qui (le piattaforme cambiano spesso), verifica la documentazione attuale, avvisami e proponi un'alternativa: non inventare endpoint.
5. **Mai** scraping con login dell'utente, mai automazione dei siti delle chat AI, mai elusione di limiti o termini d'uso delle piattaforme.

---

## 1. Cos'è l'app

Un'app **locale e gratuita**: ognuno la installa sul proprio PC e i dati restano lì (nessun server, nessun account, nessun profilo utente, nessuna condivisione).

Ogni mattina (o a richiesta) l'app:
1. **scansiona** notizie, YouTube, Reddit e Google Trends per **fino a 10 argomenti** configurati dall'utente;
2. **analizza** i risultati con l'AI scelta (temi caldi, parole in tendenza, domande della gente);
3. mostra un **report** in una dashboard;
4. **genera bozze di post** per LinkedIn, Instagram, Facebook, YouTube e TikTok, che l'utente copia e pubblica **a mano** (l'app non pubblica mai sui social).

Lingue delle fonti e dei post: **italiano, inglese, spagnolo**.

---

## 2. Stack tecnico (proposta — puoi motivare alternative prima di iniziare)

- **Backend:** Python 3.12.
- **Interfaccia:** UI web (React + TypeScript + Vite + Tailwind CSS) mostrata in una finestra desktop nativa con **pywebview** (motore WebView2 di Windows). Comunicazione UI ↔ backend tramite API locale (FastAPI su `127.0.0.1` con porta casuale e token di sessione) oppure bridge JS di pywebview: scegli e motiva.
- **Grafici:** Apache ECharts.
- **Database:** SQLite locale (con FTS5 per la ricerca nell'archivio), migrazioni versionate.
- **Pianificazione:** APScheduler.
- **HTTP/feed:** httpx, feedparser.
- **Estrazione parole chiave:** YAKE (o equivalente leggero e multilingua) + liste di stopword IT/EN/ES. Niente modelli pesanti da scaricare.
- **PDF:** ReportLab + grafici generati lato server (matplotlib o export SVG/PNG di ECharts), così il PDF funziona offline.
- **Segreti:** chiavi API salvate nel Windows Credential Manager tramite `keyring`, mai in chiaro nel database o nei file.
- **Packaging:** PyInstaller + Inno Setup → `Setup-TALeport.exe` (installazione per utente, collegamento sul desktop, voce nel menu Start, disinstallazione pulita).
- **Icona nella barra di sistema (tray):** l'app può restare ridotta lì, così le scansioni pianificate partono anche a finestra chiusa.

Requisiti: deve funzionare su Windows 10/11 64 bit anche **senza Ollama** e senza nessuna chiave API.

---

## 3. Fonti dati (solo canali legittimi e gratuiti)

| Fonte | Come | Note |
|---|---|---|
| Notizie | RSS di Google News per query (`hl`/`gl`/`ceid` per IT, EN, ES) + feed RSS aggiunti dall'utente | Fonte principale |
| YouTube | YouTube Data API v3 con **chiave gratuita fornita dall'utente** | Ricerca video recenti, statistiche, commenti più rilevanti. Rispetta la quota giornaliera e mostra quanta ne resta |
| Reddit | Feed pubblici RSS/JSON di ricerca e subreddit, con User-Agent corretto e limiti di frequenza | Se non è disponibile, disattiva la fonte con un avviso chiaro |
| Google Trends | Libreria non ufficiale (es. pytrends) | **Opzionale e fragile**: se fallisce, l'app continua senza e lo segnala nel registro |
| X (Twitter) | **Nessuna API.** Pulsante "Cerca su X con Grok" (vedi §6) | Gratis, con un clic dell'utente |

Instagram, TikTok, Facebook e LinkedIn **non vengono monitorati** (nessun accesso gratuito legittimo): dillo chiaramente nella guida dell'app.

Regole per tutte le fonti:
- **Diritto d'autore:** salva solo titolo, breve estratto o riassunto, link, data, fonte e lingua. Mai il testo integrale degli articoli.
- **Doppioni:** elimina gli elementi duplicati (stesso URL canonico, titoli quasi identici).
- **Resilienza:** timeout, ritentativi con attesa crescente, una fonte che fallisce non blocca le altre.

---

## 4. Funzionalità

### 4.1 Primo avvio guidato
1. Lingua dell'interfaccia (IT/EN/ES).
2. Scelta AI: rileva se Ollama è installato e quali modelli ha; se manca, spiega come installarlo (link) oppure permette di saltare. Inserimento facoltativo delle chiavi API.
3. Chiave YouTube facoltativa, con una guida passo passo per ottenerla gratis.
4. Orario della scansione giornaliera e opzione "avvia con Windows".
5. Creazione del primo argomento (con l'assistente AI di §4.2).
6. Prima scansione di prova, con l'avanzamento visibile.

### 4.2 Argomenti (massimo 10)
Ogni scheda argomento contiene:
- nome, descrizione, interruttore attivo/pausa;
- parole chiave **per lingua** (IT, EN, ES) e parole da escludere;
- hashtag da monitorare;
- **osservati speciali**: feed RSS, canali YouTube e subreddit da seguire sempre;
- lingue e paesi delle fonti;
- pubblico, tono di voce, social di destinazione;
- **esempi di stile**: 3–5 post scritti dall'utente, che l'AI deve imitare.

Pulsante **"Crea con l'AI"**: l'utente scrive una frase e l'AI propone tutti i campi (parole chiave nelle 3 lingue, esclusioni, hashtag, fonti suggerite). L'utente rivede e salva.

### 4.3 Scansione
- Pianificata all'orario scelto, più il pulsante "Scansiona ora" (tutto o un argomento solo).
- **Recupero:** se all'orario previsto il PC era spento, la scansione parte all'avvio successivo.
- Avanzamento in tempo reale per fonte e argomento; registro degli errori.

### 4.4 Analisi (con l'AI scelta)
Per ogni argomento e giorno:
- **Temi caldi:** raggruppa gli elementi per tema e dai a ogni tema un titolo e un riassunto.
- **Punteggio "caldo" (0–100):** volume di oggi rispetto alla media dei 7 giorni precedenti, più velocità di crescita e numero di fonti diverse. Freccia ↑/↓.
- **Domande della gente** (dai commenti YouTube e da Reddit).
- **Angolo suggerito** per raccontare il tema.
- **Statistiche parole/hashtag** salvate giorno per giorno (servono per Tendenze e PDF).
- Etichetta **"già trattato"** se l'utente ha già pubblicato un post su un tema simile.

La parte statistica (conteggi, punteggi, parole chiave) deve funzionare **anche senza AI**; l'AI aggiunge raggruppamenti, titoli e riassunti.

### 4.5 Report giornaliero — schermata "Oggi"
Riquadri numerici in alto (elementi trovati, temi caldi, post generati, post pubblicati nella settimana), poi una sezione per ogni argomento attivo con 3–5 temi caldi. Ogni tema ha i pulsanti **Genera post**, **Cerca su X con Grok** e **Dettaglio**.

### 4.6 Dettaglio tema
Riassunto, elenco di notizie/video/discussioni con link, domande della gente, angolo suggerito, grafico dell'andamento a 7 giorni.

### 4.7 Generatore di post
- Scelte: social (spunte multiple), lingua o lingue di uscita (anche diverse da quella delle fonti), AI da usare, tono, numero di varianti (1–3).
- Formato per piattaforma:
  - **LinkedIn:** post lungo e autorevole, gancio iniziale, domanda finale, 3–5 hashtag.
  - **Instagram:** testo breve, hashtag, idea di carosello slide per slide.
  - **Facebook:** testo colloquiale.
  - **YouTube:** titolo, descrizione, scaletta, idea per la miniatura.
  - **TikTok/Reels:** script di 30–60 secondi con il gancio dei primi 3 secondi e le indicazioni di scena.
- Ogni bozza mostra: **fonti usate** (link), **avvisi del controllo dei fatti** (numeri, date, nomi o citazioni non presenti negli estratti delle fonti), **idea immagine con prompt** per un generatore di immagini.
- Pulsanti: Copia, Rigenera, Modifica, Aggiungi al calendario, Segna come pubblicato.
- Prompt di sistema che usano: scheda argomento, esempi di stile, temi già trattati (da non ripetere), regole della piattaforma.

### 4.8 Da contenuto lungo
L'utente incolla un testo o carica PDF/DOCX/TXT e sceglie quanti post e su quali social. Ottiene una serie di post coerenti (stesso flusso e stesse funzioni del generatore).

### 4.9 Calendario
Vista settimanale e mensile; le bozze si trascinano sui giorni; orari consigliati per ogni social (valori predefiniti modificabili dall'utente, poi affinati dai risultati inseriti).

### 4.10 Archivio e risultati
Storico di report, temi e post con ricerca a testo libero e filtri. Sui post pubblicati l'utente inserisce a mano like, commenti, condivisioni e visualizzazioni. Questi dati servono a dare la priorità a temi e formati che funzionano (mostra il perché: "suggerito perché i post su X hanno avuto più commenti").

### 4.11 Tendenze parole (dashboard grafica)
Filtri: argomento/i, periodo (7 giorni, 30 giorni, personalizzato), lingua. Grafici:
- le 20 parole e i 20 hashtag principali (barre orizzontali con percentuale);
- parole **emergenti** (nuove o in forte crescita rispetto al periodo precedente) e parole **in calo**;
- andamento giornaliero delle 5 parole principali (linee);
- nuvola di parole;
- confronto per lingua (IT/EN/ES) e per fonte (notizie, YouTube, Reddit).

### 4.12 Casella "Chiedi"
Campo di testo in alto in tutta l'app ("Quali parole sono state in tendenza questa settimana?"), con domande pronte cliccabili.
**Sicurezza:** l'AI **non** genera SQL. Traduce la domanda in un piano JSON validato che usa solo un elenco chiuso di funzioni di analisi (es. `top_keywords`, `emerging_keywords`, `topic_trend`, `compare_periods`, `compare_languages`, `top_themes`, `post_performance`). Il risultato è una dashboard di grafici e/o una risposta scritta, esportabile in PDF.

### 4.13 Report PDF
- Esportabili: report giornaliero, settimanale, Tendenze parole, risposte di "Chiedi" e **report personalizzati**.
- Report personalizzato: scegli argomenti, periodo, lingue e sezioni (riepilogo AI, temi caldi, parole e hashtag in tendenza, emergenti/in calo, grafici di andamento, confronto per lingua e per fonte, post generati e pubblicati, risultati dei post).
- Grafici veri (vettoriali o ad alta risoluzione), copertina, indice, numeri di pagina, data, link alle fonti cliccabili.
- Tema chiaro predefinito con gli accenti dell'app; tema scuro opzionale. Logo e nome per la copertina nelle impostazioni.
- Report personalizzati salvabili come **modelli** e rigenerabili con un clic.

### 4.14 Notifiche
Notifiche di Windows (e campanella nell'app) per: picco improvviso su un argomento durante le scansioni del giorno, scansione completata o recuperata, fonte non funzionante, tetto di spesa API vicino.

### 4.15 Impostazioni
- AI predefinita, chiavi API, modello Ollama, test della connessione per ogni AI.
- Orario della scansione, avvio con Windows, ridotta nella tray.
- Lingua dell'interfaccia, tema chiaro/scuro.
- **Contatore della spesa API** (stima per chiamata, totale mensile, tetto massimo che blocca le chiamate a pagamento).
- **Backup/esportazione/importazione** di impostazioni e argomenti in un unico file (le chiavi API sono escluse per sicurezza); importazione di singoli argomenti condivisi da un collega.
- Controllo aggiornamenti (verifica una nuova versione da un URL configurabile, es. GitHub Releases, e propone il download).
- Registro errori consultabile ed esportabile.

---

## 5. Livello AI (selettore multi-provider)

Un'unica interfaccia interna (`LLMProvider`) con queste modalità, scelte dall'utente ogni volta (con un predefinito):

1. **Ollama** (locale, gratis): `http://localhost:11434`, l'utente sceglie il modello.
2. **Chiave API**: Anthropic (Claude), OpenAI (ChatGPT), xAI (Grok), Perplexity, Google Gemini. Uso automatico, con il costo registrato nel contatore spesa.
3. **"Apri nella chat"** (usa l'account personale dell'utente, gratuito o a pagamento): l'app prepara il prompt completo, lo **copia negli appunti** e apre nel browser predefinito il sito scelto (claude.ai, chatgpt.com, grok.com, perplexity.ai). Se il sito supporta il precompilato via URL, usalo (verifica quali lo supportano oggi); altrimenti solo gli appunti, con un messaggio "Prompt copiato: incollalo e invia". Poi una casella **"Incolla qui la risposta"** riporta il risultato nell'app (le bozze tornano nell'archivio e nel calendario).

Requisiti:
- Le funzioni che richiedono AI devono degradare con eleganza: senza AI disponibile, l'app propone la modalità "Apri nella chat".
- Le risposte che devono essere strutturate (temi, piani di "Chiedi", proposte di argomenti) vanno chieste in JSON e validate con uno schema; in caso di errore, un nuovo tentativo e poi un messaggio chiaro.
- Prompt centralizzati in file modello versionati (non sparsi nel codice), nelle 3 lingue.

---

## 6. "Cerca su X con Grok"

Pulsante su ogni tema e su ogni argomento. Prepara un prompt del tipo:
"Cerca su X i post degli ultimi giorni su [tema/parole chiave, nelle lingue scelte]. Dimmi: temi più discussi, post e account più rilevanti con link, sentiment generale, hashtag ricorrenti, domande frequenti. Rispondi in [lingua]."
Lo copia e apre grok.com (piano gratuito dell'utente). La risposta incollata nella casella viene salvata come fonte "X via Grok" del tema e usata nella generazione dei post.
Opzione avanzata: se l'utente ha una chiave xAI, eseguire la ricerca X via API in automatico (a pagamento, dentro il tetto di spesa).

---

## 7. Look and feel

Riferimento: l'immagine della dashboard allegata. Stile **dashboard scura** su tutte le schermate:
- sfondo blu notte/indaco (indicativo `#1E1B4B`–`#2E2A78`), riquadri leggermente più chiari (`#2F2C85`–`#3B3A9A`), angoli arrotondati 12–16 px, ombre morbide;
- accenti azzurro/ciano (`#22D3EE`, `#38BDF8`) e verde acqua (`#2DD4BF`) con sfumature su barre, anelli e pulsanti;
- testo bianco e grigio chiaro (`#E0E7FF`, `#A5B4FC`), numeri grandi in grassetto;
- **menu laterale sinistro** con icone e voce attiva evidenziata; riquadro in basso con lo stato della scansione (ultima e prossima) e la spesa API del mese;
- **barra in alto** con casella "Chiedi", pulsanti a pillola, campanella delle notifiche, **selettore dell'AI attiva** al posto dell'utente;
- grafici: anelli percentuali, barre orizzontali con percentuale, linee sfumate, istogrammi.

L'app è soprattutto testo: per Generatore, Dettaglio e Argomenti usa riquadri ampi, testo di 15–16 px, buon contrasto (WCAG AA) e larghezza di riga leggibile. Tema chiaro disponibile nelle impostazioni. Finestra ridimensionabile, minimo 1280×720.

Voci del menu: Oggi · Settimana · Tendenze parole · Generatore · Da contenuto lungo · Calendario · Argomenti · Archivio · Report PDF · Impostazioni.

---

## 8. Modello dati (indicativo)

`topics`, `topic_keywords` (per lingua), `topic_sources` (osservati speciali), `style_examples`, `scans` (esecuzioni e stato), `items` (elementi raccolti: fonte, url, titolo, estratto, lingua, data, metriche), `item_topics`, `themes` (per argomento e giorno, con punteggio), `theme_items`, `keyword_stats` (parola/hashtag, argomento, lingua, fonte, giorno, conteggio), `drafts`, `publications` (data, social, url facoltativo), `post_results`, `calendar_entries`, `report_templates`, `ai_usage` (provider, token, costo stimato), `settings`, `logs`.

---

## 9. Qualità, sicurezza, privacy

- Test automatici (pytest) per: collettori (con risposte registrate), deduplicazione, punteggio caldo, statistiche parole, validazione dei piani "Chiedi", generazione PDF.
- Nessun dato inviato a terzi tranne: le richieste alle fonti e le chiamate all'AI scelta dall'utente. Nessuna telemetria.
- Dati personali minimi: dai commenti salva il testo, non i nomi utente; pulizia automatica degli elementi più vecchi di N mesi (configurabile).
- Gestione errori leggibile dall'utente, in italiano/inglese/spagnolo, mai tracce di errore grezze nell'interfaccia.
- Prestazioni: scansione di 10 argomenti in pochi minuti; interfaccia sempre reattiva (il lavoro pesante gira in background).

---

## 10. Piano di sviluppo (fasi)

1. **Fondamenta:** struttura del progetto, finestra pywebview con il layout (menu, barra in alto, tema scuro), i18n IT/EN/ES, database e migrazioni, impostazioni, archiviazione sicura delle chiavi.
2. **Argomenti + scansione:** CRUD degli argomenti, collettori Google News/RSS, YouTube, Reddit, Trends; deduplicazione; pianificazione + recupero; tray.
3. **Analisi statistica + Oggi:** parole chiave, punteggio caldo, schermata Oggi e Dettaglio (senza AI).
4. **Livello AI:** Ollama, chiavi API, "Apri nella chat", temi e riassunti, "Crea con l'AI", "Cerca su X con Grok".
5. **Generatore post:** formati per piattaforma, varianti, stile, controllo dei fatti, idee immagini; Da contenuto lungo.
6. **Settimana, Tendenze parole, Chiedi:** dashboard grafiche e piani JSON validati.
7. **Archivio, risultati, calendario, notifiche, contatore spesa.**
8. **Report PDF:** standard, personalizzati, modelli.
9. **Primo avvio guidato, backup/importazione, aggiornamenti, registro errori.**
10. **Packaging:** PyInstaller + Inno Setup, test su Windows pulito, guida utente breve (IT/EN/ES) dentro l'app.

Criterio di accettazione finale: su un Windows 10/11 pulito, l'utente scarica `Setup-TALeport.exe`, installa, completa il primo avvio senza Ollama e senza chiavi, crea 10 argomenti, ottiene una scansione con report, genera post tramite "Apri nella chat", vede Tendenze parole ed esporta un PDF personalizzato.
