# Istruzioni permanenti per Claude

## Montaggio video: usa SEMPRE lo stile "talking-head-shorts"
Quando l'utente chiede di montare, tagliare o editare un video, usa la skill
`.claude/skills/talking-head-shorts/` (leggi prima `SKILL.md`). È lo stile dei video
di riferimento (stesso creator, 2 video) che l'utente ha indicato ("devi editare i video come fa lui").

In sintesi:
- 9:16, 1080×1920, 30 fps. Si tagliano **tutte** le pause ≥ 0,30 s, con 0,06 s di margine prima e 0,10 s dopo ogni frase.
- Zoom alternato 100% ↔ 112% a ogni jump cut.
- Sottotitoli di 1-3 parole, Inter Bold bianco con ombra, al 74,5% dell'altezza, con un "pop" di scala.
- Hook iniziale: bolla "risposta al commento" + card terminale col titolo in MAIUSCOLO (`>` arancione, cursore a blocco).
- Card UI animate in alto (terminale "Update Todos" con task che si spuntano, waveform dell'audio vero,
  etichette "silenzio", chip blu): ogni concetto detto a voce ha la sua grafica, con un cambio visivo ogni 2-4 s.
- Le spiegazioni tecniche vanno in layout split: sfondo beige #EEEBE6, sottotitoli scuri al 55,5%, faccia in un cerchio.
- Elenchi di strumenti/app → layout "stack": faccia in alto in una finestra macOS "● LIVE", sfondo blu notte,
  icona grande dello strumento al centro sulla parola esatta, poi l'icona passa in un dock a capsula che si riempie.
- Quando mostra un sito → layout "pip": screenshot in una finestra in alto, dock, faccia in una finestrella "LIVE" sotto.
- Sottotitoli con dissolvenza rapida (80 ms) + pop.
- Audio normalizzato a -14 LUFS.

Workflow: `edit.py cut` → leggere `transcript.txt` → scrivere `plan.json` → `edit.py render`.
Prima di consegnare, verifica sempre i frame e i tagli.

## Lingua
L'utente scrive in italiano: rispondi in italiano.
