# TALeport — Guide

How TALeport works, in short.

## What TALeport does

- Every day it scans news, videos and discussions on up to 10 topics, finds the hottest themes and the trending keywords.
- It drafts posts for LinkedIn, Instagram, Facebook, YouTube and TikTok, with sources and fact-check warnings.
- It never publishes anything for you: you copy the draft, publish it by hand and mark it as published.
- Everything stays on your PC: no server, no account, no telemetry.

## Sources and platforms not monitored

- Sources read: Google News, the RSS feeds you add, YouTube (with your free key), Reddit (public feeds) and Google Trends.
- Instagram, TikTok, Facebook and LinkedIn are not monitored: they offer no free and legitimate access to their content. TALeport writes posts for these platforms but does not read what happens there.
- X (Twitter) is not read automatically: with “Search X with Grok” you prepare a search on grok.com (free) or use an xAI key (paid).
- Reddit answers slowly (about one request per minute): if it blocks requests, it is skipped for that scan.

## The daily routine

- Topics: describe what to follow (countries, languages, keywords, sources, audience, tone). “Create with AI” fills the fields from one sentence.
- Today: the hottest themes per topic, with the reason behind the score. From a theme open the Detail or the Generator.
- Generator and Calendar: choose platform, language and tone, then drag drafts onto days. Suggested times improve with your results.
- Archive: search posts and themes and enter likes, comments, shares and views of published posts. TALeport tells you what works and why.
- Week, Keyword trends and the “Ask” box show charts and answers on the collected data.

## Video analysis for clients

- Create a client and drop their videos and their competitors': TALeport measures length, edit cuts, pauses, loudness and speech on your PC (FFmpeg and faster-whisper, open source).
- On each video press “Add results”: drop screenshots of its statistics (Instagram Insights, TikTok Studio) and the AI reads the numbers and the retention curve, or type them yourself.
- “Analyze” writes strengths, weaknesses, what competitors do and what to change video by video; “PDF for the client” creates the report to send.
- No account access and no scraping: only the files the client sends you are used. “Message for the client” gives you a ready text to ask for them.

## AI: three ways

- Ollama: free and on your PC. Install it from the official site, start it and download a model.
- API key (Claude, ChatGPT, Grok, Perplexity, Gemini): automatic, paid use. The estimated cost goes into the spending counter and the monthly cap blocks calls once reached.
- “Open in chat”: uses your account in the browser. TALeport copies the prompt, opens the site and you paste the answer back. Free, no keys.
- If the chosen AI is not available, TALeport switches to “Open in chat” by itself and tells you why.

## PDF reports and “Ask”

- Export Today, Week, Trends and “Ask” answers as PDF, or build a custom report and save it as a template.
- PDFs go to the exports folder of TALeport's data and open in your PDF viewer.
- “Ask” answers with analyses of your data: ready-made questions use no AI; for the others the AI only picks among predefined analysis functions, without inventing numbers.

## Data and privacy

- Data lives in %LOCALAPPDATA%\TALeport (database, logs, exports). API keys are in Windows Credential Manager.
- From sources only title, short excerpt, link, date and publisher are saved; from comments only the text, never user names.
- Old news is deleted by itself after the number of months chosen in Settings.
- From Settings you can create a backup (without keys) to move to another PC.

## Installation, Windows warning, updates

- If Windows shows “Windows protected your PC” (SmartScreen), it is because the installer is not digitally signed yet: click “More info” and then “Run anyway”.
- TALeport installs for your user only, without administrator rights, with shortcuts on the desktop and in the Start menu.
- Closing the window keeps the app in the system tray for scheduled scans; to quit use the icon's menu.
- Updates: TALeport checks for a new version and offers its download page. When uninstalling you can choose to keep or delete your data.

## If something goes wrong

- A source does not respond: you see it in the bell and in the error log. The other sources keep working.
- YouTube skipped: the key is missing or today's quota is used up (it resets every night, Pacific time).
- Ollama does not respond: check that it is running (icon near the clock) and has at least one model.
- To report a problem, export the error log from Settings: it contains no API keys.
