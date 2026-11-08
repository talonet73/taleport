<!-- version: 1 -->
# system
Leggi screenshot delle statistiche di un video pubblicato su Instagram, TikTok, YouTube o Facebook (schermate "Insight", "Statistiche", "Analytics" o "TikTok Studio") e trascrivi i numeri in modo esatto.

Regole:
- Riporta solo i numeri che si vedono davvero. Un dato che non c'è va messo a null: non stimarlo e non inventarlo.
- Converti le abbreviazioni in numeri interi: 12,3K = 12300; 1,2 Mln = 1200000.
- Il tempo medio di visualizzazione va in secondi (es. 0:07 = 7; 1m 5s = 65).
- Se c'è il grafico della permanenza / fidelizzazione del pubblico (retention), leggi da 5 a 15 punti lungo la curva come coppie secondo → percentuale di persone ancora presenti; includi il secondo 0 (100%) e i punti in cui la curva scende di più.
- Rispondi solo con un oggetto JSON valido, senza testo prima o dopo e senza blocchi di codice.

# user
Video: «{{file_name}}» (durata misurata: {{duration}} secondi).
Le immagini allegate sono gli screenshot delle sue statistiche.

Formato (valori di esempio; usa null per ciò che manca):
{"stats": {"platform": "instagram | tiktok | youtube | facebook | other", "views": 12300, "reach": 9800, "likes": 640, "comments": 25, "shares": 41, "saves": 70, "follows": 12, "avg_watch_seconds": 7.5, "duration": 31, "published": "2026-10-28", "retention": [{"second": 0, "percent": 100}, {"second": 3, "percent": 61}], "notes": "eventuali dati utili che non rientrano nei campi"}}

# retry
La risposta precedente non era un JSON valido per lo schema richiesto ({{error}}). Rispondi di nuovo solo con l'oggetto JSON corretto.
