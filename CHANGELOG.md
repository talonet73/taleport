# Changelog

## 1.2.0 — 2026-11-09

Post da una reference e profili di tono di voce · Posts from a reference and tone-of-voice profiles

**Italiano**

- Generatore, nuova scheda «Da una reference»: carichi fino a 5 documenti (Word, PDF, PowerPoint o testo), l'AI trova gli argomenti e scrive i post con lo stesso tono di voce dei documenti. Puoi salvare quel tono come profilo con una spunta.
- Nuova pagina «Tono di voce»: profili creati da documenti (l'AI descrive come scrivono e sceglie frasi di esempio, che puoi correggere) o scritti a mano. Ogni profilo si collega a uno o più argomenti e viene proposto da solo per i loro temi.
- Il tono si sceglie anche per i post da un tema e da un contenuto lungo; rigenerando una bozza il tono resta lo stesso.
- Si leggono anche i file PowerPoint (testo delle slide, tabelle e note) e le tabelle dei documenti Word.

**English**

- Generator, new "A reference" tab: upload up to 5 documents (Word, PDF, PowerPoint or text), the AI finds the topics and writes the posts in the same tone of voice as the documents. One tick saves that tone as a profile.
- New "Tone of voice" page: profiles learned from documents (the AI describes how they write and picks example sentences you can edit) or written by hand. Each profile links to one or more topics and is suggested automatically for their themes.
- The tone can also be chosen for posts from a theme and from long content; regenerating a draft keeps the same tone.
- PowerPoint files are now read too (slide text, tables and notes), as are tables in Word documents.

## 1.1.1 — 2026-11-09

Correzioni AI · AI fixes

**Italiano**

- Risolto «Errore interno dell'app» durante la generazione dei post: quando l'AI rispondeva con un errore (per esempio Ollama), l'app andava in crash invece di mostrare il motivo. Valeva per tutte le AI.
- Ollama più affidabile: risposte più ordinate, un tentativo in più e, se Ollama si interrompe, un nuovo tentativo automatico. Messaggio chiaro quando il modello non entra in memoria.
- Le risposte imperfette dei modelli locali (hashtag in una riga, slide come oggetti, numeri fuori scala) vengono corrette invece di essere scartate.
- Credito API esaurito (OpenAI, Anthropic): ora l'app lo dice chiaramente e suggerisce «Apri nella chat» oppure Ollama, invece di «ha limitato le richieste».

**English**

- Fixed "Internal app error" when generating posts: when the AI answered with an error (for example Ollama), the app crashed instead of showing the reason. This affected every AI.
- More reliable Ollama: steadier answers, one more attempt and an automatic retry if Ollama stops mid-answer. Clear message when the model does not fit in memory.
- Imperfect answers from local models (hashtags in one line, slides as objects, out-of-range numbers) are now fixed instead of rejected.
- API credit exhausted (OpenAI, Anthropic): the app now says so clearly and suggests "Open in chat" or Ollama, instead of "rate limited".

## 1.1.0 — 2026-11-08

Analisi video per i clienti · Video analysis for clients

**Italiano**

- Nuova pagina «Analisi video»: crei il cliente, trascini i suoi video e quelli dei concorrenti, premi «Analizza». Ottieni punti di forza, punti deboli, cosa fa la concorrenza, cosa cambiare video per video e idee per i prossimi.
- Ogni video viene misurato sul PC con strumenti open source: durata, formato, tagli di montaggio, pause, volume, parlato e testo dei primi 3 secondi (FFmpeg, faster-whisper; il modello di trascrizione si scarica una volta, circa 145 MB).
- Risultati dei video: trascini gli screenshot delle statistiche (Insight di Instagram, TikTok Studio) e l'AI legge numeri e curva di permanenza, oppure li scrivi a mano. Da qui si vede dove la gente smette di guardare.
- Tabella di confronto con la concorrenza sempre disponibile, anche senza AI; «PDF per il cliente» pronto da mandare; «Messaggio per il cliente» con il testo per chiedere i file giusti.
- Nessun accesso agli account e nessuno scraping: si usano solo i file che il cliente ti manda.

**English**

- New "Video analysis" page: create the client, drop their videos and their competitors', press "Analyze". You get strengths, weaknesses, what competitors do, what to change video by video and ideas for the next ones.
- Every video is measured on your PC with open-source tools: length, format, edit cuts, pauses, loudness, speech and the text of the first 3 seconds (FFmpeg, faster-whisper; the transcription model is downloaded once, about 145 MB).
- Video results: drop screenshots of the statistics (Instagram Insights, TikTok Studio) and the AI reads the numbers and the retention curve, or type them by hand. This shows where people stop watching.
- Comparison table with competitors always available, even without AI; "PDF for the client" ready to send; "Message for the client" with the text to ask for the right files.
- No account access and no scraping: only the files the client sends you are used.

## 1.0.0 — 2026-11-03

Prima versione pubblica · First public release

**Italiano**

- Scansione quotidiana di Google News, feed RSS, YouTube (con chiave gratuita), Reddit e Google Trends su un massimo di 10 argomenti, con recupero se il PC era spento.
- Temi caldi con punteggio spiegato, parole e hashtag in tendenza, schermate Oggi, Settimana e Tendenze parole, casella «Chiedi».
- Bozze di post per LinkedIn, Instagram, Facebook, YouTube e TikTok/Reels con fonti, controllo dei fatti e idea immagine; anche da testi lunghi (PDF, DOCX, TXT). La pubblicazione resta sempre manuale.
- AI a scelta: Ollama (gratis, locale), chiavi API con contatore e tetto di spesa, oppure «Apri nella chat» con il tuo account.
- Calendario con trascinamento, archivio con ricerca, risultati dei post e priorità motivate, notifiche di Windows.
- Report PDF (giornaliero, settimanale, tendenze, risposte di «Chiedi», personalizzati e modelli), tema chiaro o scuro.
- Configurazione guidata, backup senza chiavi, condivisione degli argomenti, registro errori, pulizia automatica, controllo aggiornamenti.
- Interfaccia in italiano, inglese e spagnolo; tutto resta sul PC.

**English**

- Daily scan of Google News, RSS feeds, YouTube (free key), Reddit and Google Trends for up to 10 topics, with catch-up when the PC was off.
- Hot themes with an explained score, trending keywords and hashtags, Today, Week and Keyword trends screens, "Ask" box.
- Post drafts for LinkedIn, Instagram, Facebook, YouTube and TikTok/Reels with sources, fact-check and image idea; also from long texts (PDF, DOCX, TXT). Publishing is always manual.
- AI of your choice: Ollama (free, local), API keys with spending counter and cap, or "Open in chat" with your own account.
- Drag-and-drop calendar, searchable archive, post results with explained priorities, Windows notifications.
- PDF reports (daily, weekly, trends, "Ask" answers, custom reports and templates), light or dark theme.
- Guided setup, backups without keys, topic sharing, error log, automatic clean-up, update check.
- UI in Italian, English and Spanish; everything stays on your PC.

The installer is not code-signed yet: Windows SmartScreen may ask to confirm ("More info" → "Run anyway").
