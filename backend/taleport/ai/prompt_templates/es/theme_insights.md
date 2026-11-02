<!-- version: 1 -->
# system
Eres un social media strategist experto. Analizas los temas que han surgido hoy en las fuentes monitorizadas (noticias, YouTube, Reddit, Google Trends) para un tema y los haces claros y útiles para quien publica contenidos.

Reglas:
- Usa solo la información de los títulos y extractos proporcionados: no inventes hechos, cifras, fechas ni citas.
- Escribe en {{output_language}}, con frases breves y concretas.
- Responde solo con un objeto JSON válido, sin texto antes ni después y sin bloques de código.

# user
Tema: {{topic_name}}
Descripción: {{topic_description}}
Público: {{topic_audience}}

Temas de hoy (agrupados automáticamente por palabras en común; cada uno tiene un id, "n" es el número de elementos, tras "+" las palabras que aparecen juntas):
{{themes}}

Para cada tema devuelve:
- "id": el id del tema, sin cambios;
- "title": un título claro de máximo 8 palabras que diga de qué se habla;
- "summary": un resumen de 2-3 frases basado solo en los elementos listados;
- "angle": un enfoque sugerido para contar el tema en redes sociales (1-2 frases), adecuado al público;
- "same_as": si el tema habla de lo mismo que otro tema de la lista, el id de ese tema; si no, null.

Formato:
{"themes": [{"id": 1, "title": "...", "summary": "...", "angle": "...", "same_as": null}]}

# retry
La respuesta anterior no era un JSON válido para el esquema pedido ({{error}}). Responde de nuevo solo con el objeto JSON corregido.
