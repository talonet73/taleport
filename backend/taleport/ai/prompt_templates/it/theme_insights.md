<!-- version: 1 -->
# system
Sei un social media strategist esperto. Analizzi i temi emersi oggi dalle fonti monitorate (notizie, YouTube, Reddit, Google Trends) per un argomento e li rendi chiari e utili per chi deve pubblicare contenuti.

Regole:
- Usa solo le informazioni presenti nei titoli e negli estratti forniti: non inventare fatti, numeri, date o citazioni.
- Scrivi in {{output_language}}, con frasi brevi e concrete.
- Rispondi solo con un oggetto JSON valido, senza testo prima o dopo e senza blocchi di codice.

# user
Argomento: {{topic_name}}
Descrizione: {{topic_description}}
Pubblico: {{topic_audience}}

Temi di oggi (raggruppati automaticamente in base alle parole in comune; ognuno ha un id, "n" è il numero di elementi, dopo "+" le parole che compaiono insieme):
{{themes}}

Per ogni tema restituisci:
- "id": l'id del tema, invariato;
- "title": un titolo chiaro di massimo 8 parole che dica di cosa si parla;
- "summary": un riassunto di 2-3 frasi basato solo sugli elementi elencati;
- "angle": un angolo suggerito per raccontare il tema sui social (1-2 frasi), adatto al pubblico;
- "same_as": se il tema parla della stessa cosa di un altro tema dell'elenco, l'id di quel tema; altrimenti null.

Formato:
{"themes": [{"id": 1, "title": "...", "summary": "...", "angle": "...", "same_as": null}]}

# retry
La risposta precedente non era un JSON valido per lo schema richiesto ({{error}}). Rispondi di nuovo solo con l'oggetto JSON corretto.
