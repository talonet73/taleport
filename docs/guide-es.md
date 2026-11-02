# TALeport — Guía

Cómo funciona TALeport, en breve.

## Qué hace TALeport

- Cada día analiza noticias, vídeos y debates sobre un máximo de 10 temas, encuentra los temas más calientes y las palabras en tendencia.
- Te propone borradores de posts para LinkedIn, Instagram, Facebook, YouTube y TikTok, con las fuentes y los avisos de verificación.
- Nunca publica nada por ti: copias el borrador, lo publicas a mano y lo marcas como publicado.
- Todo se queda en tu PC: sin servidores, sin cuentas, sin telemetría.

## Fuentes y plataformas no monitorizadas

- Fuentes leídas: Google News, los feeds RSS que añadas, YouTube (con tu clave gratuita), Reddit (feeds públicos) y Google Trends.
- Instagram, TikTok, Facebook y LinkedIn no se monitorizan: no ofrecen un acceso gratuito y legítimo a sus contenidos. TALeport escribe posts para estas plataformas, pero no lee lo que pasa en ellas.
- X (Twitter) no se lee automáticamente: con «Buscar en X con Grok» preparas una búsqueda en grok.com (gratis) o usas una clave de xAI (de pago).
- Reddit responde despacio (una petición por minuto aprox.): si bloquea las peticiones, se omite en ese análisis.

## El trabajo de cada día

- Temas: describe qué seguir (países, idiomas, palabras clave, fuentes, público, tono). «Crear con IA» rellena los campos a partir de una frase.
- Hoy: los temas más calientes por tema, con el porqué de la puntuación. Desde un tema abre el Detalle o el Generador.
- Generador y Calendario: elige red, idioma y tono, y arrastra los borradores a los días. Los horarios recomendados mejoran con los resultados.
- Archivo: busca posts y temas e introduce me gusta, comentarios, compartidos y visualizaciones de los posts publicados. TALeport te dice qué funciona y por qué.
- Semana, Tendencias de palabras y la casilla «Preguntar» muestran gráficos y respuestas sobre los datos recogidos.

## IA: tres formas

- Ollama: gratis y en tu PC. Instálalo desde el sitio oficial, ábrelo y descarga un modelo.
- Clave API (Claude, ChatGPT, Grok, Perplexity, Gemini): uso automático de pago. El coste estimado va al contador de gasto y el límite mensual bloquea las llamadas al alcanzarlo.
- «Abrir en el chat»: usa tu cuenta en el navegador. TALeport copia el prompt, abre el sitio y tú pegas aquí la respuesta. Gratis, sin claves.
- Si la IA elegida no está disponible, TALeport pasa sola a «Abrir en el chat» y te dice por qué.

## Informes PDF y «Preguntar»

- Exporta a PDF Hoy, Semana, Tendencias y las respuestas de «Preguntar», o crea un informe personalizado y guárdalo como plantilla.
- Los PDF se guardan en la carpeta exports de los datos de TALeport y se abren con tu lector de PDF.
- «Preguntar» responde con análisis de tus datos: las preguntas listas no usan IA; para las demás la IA solo elige entre funciones de análisis previstas, sin inventar cifras.

## Datos y privacidad

- Los datos están en %LOCALAPPDATA%\TALeport (base de datos, registros, exportaciones). Las claves API están en el Administrador de credenciales de Windows.
- De las fuentes solo se guardan título, extracto breve, enlace, fecha y editor; de los comentarios solo el texto, nunca los nombres de usuario.
- Las noticias antiguas se borran solas tras el número de meses elegido en los Ajustes.
- Desde los Ajustes creas una copia de seguridad (sin claves) para llevarla a otro PC.

## Instalación, aviso de Windows, actualizaciones

- Si Windows muestra «Windows protegió tu PC» (SmartScreen) es porque el instalador aún no está firmado digitalmente: haz clic en «Más información» y luego en «Ejecutar de todas formas».
- TALeport se instala solo para tu usuario, sin permisos de administrador, con acceso directo en el escritorio y en el menú Inicio.
- Al cerrar la ventana la app sigue en la bandeja del sistema para los análisis programados; para salir usa el menú del icono.
- Actualizaciones: TALeport comprueba si hay una versión nueva y te propone su página de descarga. Al desinstalar puedes elegir si conservar o borrar tus datos.

## Si algo no va bien

- Una fuente no responde: lo ves en la campana y en el registro de errores. Las demás fuentes siguen funcionando.
- YouTube omitido: falta la clave o se acabó la cuota del día (se reinicia cada noche, hora del Pacífico).
- Ollama no responde: comprueba que esté abierto (icono junto al reloj) y que tenga al menos un modelo.
- Para avisar de un problema exporta el registro de errores desde los Ajustes: no contiene claves API.
