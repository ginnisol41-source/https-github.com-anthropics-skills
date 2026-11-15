# Conversazione del 15/11/2026: montaggio video "come fa lui"

## 1. Richiesta
**Utente:** (allega un video `.mp4` verticale, 576×1024, 1:58) *"devi editare i video come fa lui"*

## 2. Analisi del video di riferimento
È un TikTok "explainer" in formato talking head (sfondo LED blu, cuffie e microfono) sul tema *"Come fa Claude a tagliare le pause"*.
Sono stati estratti i frame, analizzato l'audio (volume medio -16,8 dB, nessuna pausa rimasta) e rilevati i cambi di scena.

Stile individuato:
- **Hook (0-5 s)**: bolla "risposta al commento" (*@rocco.montaggio_419: "Perché Claude mi monta male i video?"*) + card terminale nera con `> COME FA CLAUDE A TAGLIARE LE PAUSE`, `>` arancione, cursore a blocco e mini waveform.
- **Sottotitoli**: 1-3 parole alla volta, sans-serif bold bianco con ombra, al ~74,5% dell'altezza.
- **Tagli**: zero pause, jump cut con punch-in di zoom.
- **Pannelli UI in alto**: terminale Claude Code "Update Todos" con i task che si spuntano (Pulisci l'audio con l'API Auphonic → Silence detection con FFmpeg → Durata minima → Trascrizione al millisecondo → J cut + L cut); waveform con etichette "silenzio", "ventilatore", "aria condizionata", "rumore"; zoom sulla parola «doppia» (DO / PP / IA); tabella di trascrizione parola/inizio/fine; chip blu ("API: Claude usa Auphonic senza aprire il sito", "FFmpeg: programma gratis per audio e video"); "CI AZZECCA".
- **Layout split**: sfondo beige, pannelli sopra, sottotitolo scuro, faccia in un cerchio sotto.
- **Chiusura**: end card TikTok.

## 3. Cosa è stato costruito
La skill `talking-head-shorts` (oggi in `.claude/skills/talking-head-shorts/`):
- `scripts/edit.py`: lavora in due passate.
  - `cut`: rileva i silenzi con ffmpeg (soglia automatica), taglia le pause ≥ 0,30 s con margini di 0,06 s prima e 0,10 s dopo, fa il reframe a 1080×1920 alternando zoom 1.0/1.12 a ogni taglio, trascrive (words.json / SRT / faster-whisper) e rimappa i tempi sul video tagliato.
  - `render`: aggiunge hook, titolo, pannelli animati (fade + slide), layout split con il cerchio, sottotitoli ASS con "pop" e loudnorm a -14 LUFS.
  - `auto`: esegue entrambe le passate.
- `scripts/cards.py`: genera le card PNG (commento, titolo, terminale, waveform dall'audio reale, chip, immagine, maschera del cerchio).
- `SKILL.md`: regole dello stile + workflow. `examples/plan.example.json`: esempio di plan.

**Test:** sul video di riferimento sono state inserite 2 pause artificiali (1,3 s e 0,9 s). Sono state rilevate e tagliate entrambe (24,2 s → 22,3 s) e l'output è 1080×1920 con tutti gli elementi.
**Limiti del test:**
- La trascrizione automatica non funziona nel container cloud, perché il download del modello da Hugging Face è bloccato. Per il test sono stati usati tempi delle parole sintetici, quindi i sottotitoli non sono sincronizzati con la voce.
- La sorgente era già montata, per questo nel test si vedono sottotitoli e grafiche doppie.

## 4. "Salva queste informazioni e non te le dimenticare"
- La skill è stata spostata in `.claude/skills/talking-head-shorts/`, che Claude Code carica in automatico.
- È stato creato `CLAUDE.md` con le regole dello stile e l'istruzione di usarle sempre per il montaggio video, rispondendo in italiano.
- Nota: tutto è nel branch `claude/video-editing-like-him-4wtpmw`. Perché le nuove sessioni lo trovino, va unito al branch principale (pull request da aprire su richiesta).

## 5. Prossimi passi
- Mandare il **girato grezzo** (senza tagli) e la domanda o il commento da usare come hook. Facoltativo: un file `.srt`, se la trascrizione automatica non è disponibile.
- Decidere se aprire la pull request verso il branch principale.
