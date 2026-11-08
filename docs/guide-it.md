# TALeport — Guida

Come funziona TALeport, in breve.

## Cosa fa TALeport

- Ogni giorno scansiona notizie, video e discussioni su un massimo di 10 argomenti, trova i temi più caldi e le parole in tendenza.
- Ti propone bozze di post per LinkedIn, Instagram, Facebook, YouTube e TikTok, con le fonti e gli avvisi del controllo dei fatti.
- Non pubblica mai nulla al posto tuo: copi la bozza, la pubblichi a mano e la segni come pubblicata.
- Tutto resta sul tuo PC: nessun server, nessun account, nessuna telemetria.

## Fonti e piattaforme non monitorate

- Fonti lette: Google News, i feed RSS che aggiungi, YouTube (con la tua chiave gratuita), Reddit (feed pubblici) e Google Trends.
- Instagram, TikTok, Facebook e LinkedIn non vengono monitorati: non offrono un accesso gratuito e legittimo ai contenuti. TALeport scrive i post per queste piattaforme, ma non legge cosa succede lì.
- X (Twitter) non viene letto in automatico: con «Cerca su X con Grok» prepari una ricerca su grok.com (gratis) o usi una chiave xAI (a pagamento).
- Reddit risponde piano (circa una richiesta al minuto): se blocca le richieste, viene saltato per quella scansione.

## Il lavoro di ogni giorno

- Argomenti: descrivi cosa seguire (Paesi, lingue, parole chiave, fonti, pubblico, tono). «Crea con l'AI» compila i campi da una frase.
- Oggi: i temi più caldi per argomento, con il perché del punteggio. Da un tema apri il Dettaglio o il Generatore.
- Generatore e Calendario: scegli social, lingua e tono, poi trascina le bozze sui giorni. Gli orari consigliati migliorano con i risultati.
- Archivio: cerchi post e temi e inserisci like, commenti, condivisioni e visualizzazioni dei post pubblicati. TALeport ti dice cosa funziona e perché.
- Settimana, Tendenze parole e la casella «Chiedi» mostrano grafici e risposte sui dati raccolti.

## Analisi video per i clienti

- Crea un cliente, trascina i suoi video e quelli dei concorrenti: TALeport misura sul PC durata, tagli di montaggio, pause, volume e parlato (FFmpeg e faster-whisper, open source).
- Su ogni video premi «Aggiungi risultati»: trascina gli screenshot delle statistiche (Insight di Instagram, TikTok Studio) e l'AI legge i numeri e la curva di permanenza, oppure scrivili tu.
- «Analizza» scrive punti di forza, punti deboli, cosa fa la concorrenza e cosa cambiare video per video; «PDF per il cliente» crea il report da mandare.
- Nessun accesso agli account e nessuno scraping: si usano solo i file che ti manda il cliente. «Messaggio per il cliente» ti dà il testo pronto per chiederglieli.

## AI: tre modi

- Ollama: gratis e sul tuo PC. Installalo dal sito ufficiale, avvialo e scarica un modello.
- Chiave API (Claude, ChatGPT, Grok, Perplexity, Gemini): uso automatico a pagamento. Il costo stimato va nel contatore spesa e il tetto mensile blocca le chiamate quando lo raggiungi.
- «Apri nella chat»: usa il tuo account nel browser. TALeport copia il prompt, apre il sito e tu incolli qui la risposta. Gratis, senza chiavi.
- Se l'AI scelta non è disponibile, TALeport passa da sola ad «Apri nella chat» e ti dice perché.

## Report PDF e «Chiedi»

- Esporta in PDF Oggi, Settimana, Tendenze e le risposte di «Chiedi», oppure crea un report personalizzato e salvalo come modello.
- I PDF finiscono nella cartella exports dei dati di TALeport e si aprono col tuo lettore PDF.
- «Chiedi» risponde con analisi dei tuoi dati: le domande pronte non usano l'AI; per le altre l'AI sceglie solo tra funzioni di analisi già previste, senza inventare numeri.

## Dati e privacy

- I dati sono in %LOCALAPPDATA%\TALeport (database, log, export). Le chiavi API sono nel Gestore credenziali di Windows.
- Delle fonti si salvano solo titolo, breve estratto, link, data ed editore; dei commenti solo il testo, mai i nomi utente.
- Le notizie vecchie si cancellano da sole dopo il numero di mesi scelto nelle Impostazioni.
- Dalle Impostazioni crei un backup (senza chiavi) da riportare su un altro PC.

## Installazione, avviso di Windows, aggiornamenti

- Se Windows mostra «Windows ha protetto il PC» (SmartScreen) è perché l'installer non è ancora firmato digitalmente: fai clic su «Ulteriori informazioni» e poi su «Esegui comunque».
- TALeport si installa solo per il tuo utente, senza permessi di amministratore, con collegamento sul desktop e nel menu Start.
- Chiudendo la finestra l'app resta nella barra di sistema per le scansioni pianificate; per uscire usa il menu dell'icona.
- Aggiornamenti: TALeport controlla se c'è una nuova versione e ti propone la pagina per scaricarla. Disinstallando puoi scegliere se tenere o cancellare i tuoi dati.

## Se qualcosa non va

- Una fonte non risponde: lo trovi nella campanella e nel registro errori. Le altre fonti continuano a funzionare.
- YouTube saltato: manca la chiave o è finita la quota del giorno (si azzera ogni notte, ora del Pacifico).
- Ollama non risponde: controlla che sia avviato (icona vicino all'orologio) e che abbia almeno un modello.
- Per una segnalazione esporta il registro errori dalle Impostazioni: non contiene chiavi API.
