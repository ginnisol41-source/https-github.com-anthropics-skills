---
name: talking-head-shorts
description: Edit a raw talking-head recording into a vertical 9:16 short (TikTok / Reels / Shorts) in the "explainer" style. The edit removes every pause, punches in on every jump cut, shows word-by-word captions, opens with a reply-to-comment hook and a terminal title, puts animated UI panels (terminal, waveform, chips) on top, and switches to a beige split layout with a circular face cam while explaining. Use it when the user asks to edit/cut ("montare", "tagliare", "editare") a video like a TikTok/Reel creator, remove pauses, or add captions and overlays to a vertical talking-head video.
---

# Talking-head shorts (stile "explainer TikTok")

The style was reverse-engineered from a reference video. The rules below are what make it read as *that* style.
Follow them unless the user asks otherwise.

## Le regole dello stile

| Elemento | Regola |
|---|---|
| Formato | 1080×1920, 30 fps. Il cut è a "cover" con il crop sbilanciato verso l'alto (`--focus-y 0.35`), così la faccia resta nel terzo superiore |
| Pause | **Zero pause.** Va tagliato ogni silenzio ≥ 0,30 s. Si tengono 0,06 s prima e 0,10 s dopo ogni frase, così le code delle parole non si mozzano (effetto L-cut naturale) |
| Jump cut | Ogni taglio alterna lo zoom 100% ↔ 112% (punch-in) per nascondere lo stacco |
| Sottotitoli | 1-3 parole alla volta (max 18 caratteri), Inter Bold, ~66 px, bianchi con ombra morbida, centrati al **74,5%** dell'altezza, piccolo "pop" di scala (86→100% in 90 ms). Vanno a capo sulla punteggiatura |
| Hook (0-5 s) | Bolla "risposta al commento" in alto (avatar + @utente + domanda), più una card terminale scura con il titolo in MAIUSCOLO mono, il `>` arancione e il cursore a blocco |
| Pannelli | Card UI che entrano dall'alto (fade + slide di 36 px in 160 ms) nella fascia 140-800 px: terminale "Update Todos" con i task che si spuntano man mano, waveform dell'audio **vero**, etichette "silenzio", chip blu esplicativi. **Ogni concetto nominato a voce ha la sua grafica** |
| Layout split | Quando spiega uno strumento: sfondo beige `#EEEBE6`, pannelli sopra, sottotitolo scuro al 55,5%, faccia in un cerchio Ø380 con bordo bianco al 69% |
| Audio | Loudnorm a -14 LUFS, true peak -1 dB (standard dei social) |
| Ritmo | Un cambio visivo (pannello nuovo, task spuntato, zoom, cambio layout) ogni 2-4 s |

## Workflow (2 passate)

```bash
S=.claude/skills/talking-head-shorts/scripts
# 1) taglio + reframe + trascrizione (whisper se disponibile)
python3 $S/edit.py cut raw.mp4 --work work --lang it
#    -> work/cut.mp4, work/segments.json, work/words.json, work/transcript.txt (tempi già DOPO il taglio)

# 2) leggi work/transcript.txt e scrivi work/plan.json (vedi sotto)
# 3) render finale
python3 $S/edit.py render --work work --plan work/plan.json -o final.mp4
```

Per un montaggio veloce senza plan: `edit.py auto raw.mp4 --lang it --hook-user @utente --hook-text "Domanda?" --title "Titolo" -o final.mp4`.

### Trascrizione
In ordine di priorità: `--words words.json` (`[{"w","s","e"}]` in tempo sorgente), poi `--srt file.srt`, poi `faster-whisper` (`pip install faster-whisper`, che scarica il modello da Hugging Face al primo uso). Se nessuna fonte è disponibile, il video viene montato lo stesso, ma senza sottotitoli: dillo all'utente.

### Come scrivere il plan (compito di Claude)
Leggi `transcript.txt`. I timestamp sono già nel tempo del video tagliato. Poi:
1. **Hook**: se il video risponde a una domanda o a un commento, mettilo in `hook`. `title` riassume la promessa del video in 4-7 parole.
2. Per ogni strumento, concetto o passaggio nominato, aggiungi un pannello che parte **sulla parola** che lo nomina (usa `s` della parola).
3. Tieni un terminale "Update Todos" che evolve: i task sono `[ ]` all'inizio e diventano `[x]` (barrati) quando vengono spiegati. Ogni stato è un pannello con start/end consecutivi.
4. Per le waveform usa `audio_from`/`audio_to` uguali alla finestra del pannello, così le barre si muovono con la voce reale. Con `regions` evidenzi i silenzi, con `bottom_labels` le sillabe (es. DO / PP / IA).
5. Le sezioni "spiegone" (un tool, un concetto tecnico) vanno in `split`. Le parti emotive, l'hook e la CTA restano full-screen sulla faccia.
6. Gli ultimi 2-3 s restano senza pannelli (CTA a voce).

Schema completo in `examples/plan.example.json`. Tipi di pannello:
- `comment {user, text}`
- `title {text}`
- `terminal {lines[], title?}`: la sintassi delle righe è `* header`, `[ ] todo`, `[x] fatto`, `> prompt`, `$ tool call`, testo libero
- `waveform {title, badge?, badge_color?, icon?, audio_from, audio_to, regions?, playhead?, bottom_labels?, height?}`
- `chip {text, dark?}`
- `image {path, width?}`: screenshot o loghi reali

Campi comuni: `start`, `end`, `y` (px dall'alto, default 140), `x` (espressione ffmpeg, default centrato), `anim` (`pop` | `none`).
Più pannelli nello stesso intervallo vanno impilati a mano con `y` (circa 230 px per un terminale di 4 righe, 250 per una waveform).

### Parametri utili del taglio
`--noise` (soglia in dB, auto = volume medio -16), `--min-silence`, `--pre`, `--post`, `--zooms 1.0,1.12`, `--focus-y`, `--no-cut`.
Se taglia troppo (parole mangiate), alza `--post` o abbassa `--noise` (es. -40). Se lascia pause, alza `--noise` (es. -30).

## Verifica prima di consegnare
Estrai 5-6 frame (`ffmpeg -ss T -i final.mp4 -frames:v 1 f.jpg`) e controlla che:
- i pannelli non coprano gli occhi
- i sottotitoli non si sovrappongano ai pannelli
- nel layout split il cerchio inquadri la faccia (altrimenti regola `face {x,y,size}`)

Poi ascolta i tagli: non devono esserci parole troncate.
