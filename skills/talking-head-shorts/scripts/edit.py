#!/usr/bin/env python3
"""Talking-head shorts editor.

Two passes, so Claude can read the transcript in between and write the plan:

  1) cut     raw.mp4 -> work/cut.mp4  (silences removed, 9:16 1080x1920, punch-in zoom on every jump cut)
             + work/segments.json, work/words.json (word timestamps in *cut* time, if a transcript is available)
  2) render  work/ + plan.json -> final.mp4  (hook, title, UI panels, split layout, word-by-word captions)

`auto` runs both with a default plan (hook/title only if given on the command line).

Transcript sources, in order: --words words.json | --srt file.srt | faster-whisper (if installed and the model is
available) | none (video is still cut, zoomed and composed, just without captions).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cards  # noqa: E402

W, H, FPS = 1080, 1920, 30
BEIGE = "0xEEEBE6"


def run(cmd: list[str], **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-4000:])
        raise SystemExit(f"command failed: {' '.join(cmd[:6])} ...")
    return r


def probe(path: str) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = abs(int(sd["rotation"]))
    w, h = int(v["width"]), int(v["height"])
    if rot in (90, 270):
        w, h = h, w
    return {"w": w, "h": h, "dur": float(j["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in j["streams"])}


# ----------------------------------------------------------------------------------------------- silence cutting

def mean_volume(path: str) -> float:
    r = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else -25.0


def detect_silences(path: str, noise_db: float, min_sil: float) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-i", path, "-af", f"silencedetect=n={noise_db}dB:d={min_sil}", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    sil = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        sil.append((max(0.0, s), e))
    return sil


def speech_segments(dur: float, silences, pre: float, post: float, min_seg: float) -> list[list[float]]:
    segs, cur = [], 0.0
    for s, e in silences:
        if s > cur:
            segs.append([cur, s])
        cur = e if e is not None else dur
    if cur < dur:
        segs.append([cur, dur])
    # pad: a little pre-roll (breath/onset) and a longer post-roll (word tails never get clipped)
    padded = [[max(0.0, a - pre), min(dur, b + post)] for a, b in segs]
    merged: list[list[float]] = []
    for a, b in padded:
        if merged and a <= merged[-1][1] + 0.02:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [s for s in merged if s[1] - s[0] >= min_seg]


def cover_geometry(iw: int, ih: int, zoom: float, focus_y: float):
    s = max(W / iw, H / ih) * zoom
    sw, sh = int(math.ceil(iw * s / 2) * 2), int(math.ceil(ih * s / 2) * 2)
    x = (sw - W) // 2
    y = int(max(0, min(sh - H, (sh - H) * focus_y)))
    return sw, sh, x, y


def cut(args) -> None:
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    info = probe(args.input)
    dur = info["dur"]
    if args.no_cut or not info["has_audio"]:
        segs = [[0.0, dur]]
    else:
        thr = args.noise if args.noise is not None else max(-45.0, min(-28.0, mean_volume(args.input) - 16))
        sil = detect_silences(args.input, thr, args.min_silence)
        segs = speech_segments(dur, sil, args.pre, args.post, args.min_segment)
        print(f"silence threshold {thr:.1f} dB, {len(sil)} pauses, {len(segs)} kept segments")
    zooms = [float(z) for z in args.zooms.split(",")]

    lines, vlabels, alabels = [], [], []
    out_t = 0.0
    seg_map = []
    for i, (a, b) in enumerate(segs):
        z = zooms[i % len(zooms)]
        sw, sh, x, y = cover_geometry(info["w"], info["h"], z, args.focus_y)
        lines.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,fps={FPS},"
                     f"scale={sw}:{sh}:flags=lanczos,crop={W}:{H}:{x}:{y},setsar=1[v{i}]")
        vlabels.append(f"[v{i}]")
        if info["has_audio"]:
            d = b - a
            f = min(0.012, d / 4)
            lines.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                         f"afade=t=in:d={f:.3f},afade=t=out:st={d - f:.3f}:d={f:.3f}[a{i}]")
            alabels.append(f"[a{i}]")
        seg_map.append({"src_start": a, "src_end": b, "out_start": round(out_t, 3), "zoom": z})
        out_t += b - a
    n = len(segs)
    if info["has_audio"]:
        inter = "".join(v + a for v, a in zip(vlabels, alabels))
        lines.append(f"{inter}concat=n={n}:v=1:a=1[vout][aout]")
    else:
        lines.append(f"{''.join(vlabels)}concat=n={n}:v=1:a=0[vout]")
    fc = work / "cut_filter.txt"
    fc.write_text(";\n".join(lines))
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", args.input, "-filter_complex_script", str(fc), "-map", "[vout]"]
    if info["has_audio"]:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(work / "cut.mp4")]
    run(cmd)
    (work / "segments.json").write_text(json.dumps({"source": os.path.abspath(args.input), "segments": seg_map,
                                                    "duration": round(out_t, 3)}, indent=1))
    print(f"cut: {dur:.1f}s -> {out_t:.1f}s  ({100 * (1 - out_t / dur):.0f}% removed)")

    words = load_words(args, seg_map)
    if words is not None:
        (work / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0))
        (work / "transcript.txt").write_text(transcript_text(words))
        print(f"words: {len(words)} -> {work / 'transcript.txt'}")
    else:
        print("no transcript: captions will be skipped (pass --words / --srt or install faster-whisper)")


# ----------------------------------------------------------------------------------------------- transcript

def parse_srt(path: str) -> list[dict]:
    """SRT -> pseudo word timings (each cue's duration split by character count)."""
    def ts(s):
        h, m, rest = s.split(":")
        sec, ms = rest.replace(".", ",").split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000
    words = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8-sig").strip()):
        ls = block.strip().splitlines()
        tl = next((l for l in ls if "-->" in l), None)
        if not tl:
            continue
        a, b = [ts(x.strip().split()[0]) for x in tl.split("-->")]
        text = " ".join(ls[ls.index(tl) + 1:]).split()
        total = sum(len(t) + 1 for t in text) or 1
        t = a
        for tok in text:
            d = (b - a) * (len(tok) + 1) / total
            words.append({"w": tok, "s": round(t, 3), "e": round(t + d, 3)})
            t += d
    return words


def whisper_words(path: str, lang: str | None, model: str) -> list[dict] | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None
    try:
        m = WhisperModel(model, device="auto", compute_type="int8")
        segs, _ = m.transcribe(path, language=lang, word_timestamps=True, vad_filter=False)
        return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]
    except Exception as e:  # model download blocked, etc.
        print(f"faster-whisper unavailable: {e.__class__.__name__}: {str(e)[:120]}")
        return None


def remap(words: list[dict], seg_map: list[dict]) -> list[dict]:
    out = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        for sg in seg_map:
            if sg["src_start"] <= mid <= sg["src_end"]:
                off = sg["out_start"] - sg["src_start"]
                s = max(w["s"], sg["src_start"]) + off
                e = min(w["e"], sg["src_end"]) + off
                out.append({"w": w["w"], "s": round(s, 3), "e": round(e, 3)})
                break
    return out


def load_words(args, seg_map) -> list[dict] | None:
    if args.words:
        words = json.loads(Path(args.words).read_text())
        if args.words_in_cut_time:
            return words
    elif args.srt:
        words = parse_srt(args.srt)
    elif not args.no_transcribe:
        words = whisper_words(args.input, args.lang, args.whisper_model)
    else:
        words = None
    return remap(words, seg_map) if words else None


def transcript_text(words: list[dict]) -> str:
    """Readable transcript with a timestamp every ~6 words, used by Claude to write the plan."""
    lines, cur = [], []
    for i, w in enumerate(words):
        if not cur:
            cur.append(f"[{w['s']:6.2f}]")
        cur.append(w["w"])
        if len(cur) > 7 or re.search(r"[.?!]$", w["w"]):
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------------------- captions (ASS)

def chunk_words(words: list[dict], max_words: int, max_chars: int) -> list[dict]:
    chunks, cur = [], []
    for i, w in enumerate(words):
        nxt = cur + [w]
        text = " ".join(x["w"] for x in nxt)
        gap = (w["s"] - cur[-1]["e"]) if cur else 0
        if cur and (len(nxt) > max_words or len(text) > max_chars or gap > 0.45):
            chunks.append(cur)
            cur = [w]
        else:
            cur = nxt
        if re.search(r"[.,?!:;]$", w["w"]) and cur:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        s = c[0]["s"]
        e = c[-1]["e"] + 0.25
        if i + 1 < len(chunks):
            e = min(max(e, c[-1]["e"]), chunks[i + 1][0]["s"])
            if chunks[i + 1][0]["s"] - c[-1]["e"] < 0.6:
                e = chunks[i + 1][0]["s"]
        out.append({"text": " ".join(x["w"] for x in c), "s": s, "e": max(e, s + 0.12)})
    return out


def ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def write_ass(path: Path, chunks: list[dict], split_ranges, style: dict) -> None:
    font = style.get("font", "Inter")
    size = style.get("size", 66)
    y_norm = int(H * style.get("y", 0.745))
    y_split = int(H * style.get("y_split", 0.555))
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,-1,0,1,0,3,5,60,60,0,1
Style: CapDark,{font},{size},&H001A1A1A,&H001A1A1A,&H00000000,&H00000000,-1,0,0,0,100,100,-1,0,1,0,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pop = r"{\blur0.6\fscx86\fscy86\t(0,90,\fscx100\fscy100)}"
    for c in chunks:
        mid = (c["s"] + c["e"]) / 2
        in_split = any(a <= mid < b for a, b in split_ranges)
        st, y = ("CapDark", y_split) if in_split else ("Cap", y_norm)
        ev.append(f"Dialogue: 0,{ass_time(c['s'])},{ass_time(c['e'])},{st},,0,0,0,,{{\\pos({W // 2},{y})}}{pop}{ass_escape(c['text'])}")
    path.write_text(hdr + "\n".join(ev) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------------------------- render

def build_card(p: dict, cut_path: str, tmp: Path, idx: int) -> Path:
    t = p["type"]
    if t == "comment":
        im = cards.comment_card(p["user"], p["text"])
    elif t == "title":
        im = cards.title_card(p["text"])
    elif t == "terminal":
        im = cards.terminal_card(p["lines"], p.get("title", "claude — ~/video"), min_lines=p.get("min_lines", 0))
    elif t == "waveform":
        a, b = p.get("audio_from", p["start"]), p.get("audio_to", p["end"])
        env = cards.audio_envelope(cut_path, a, b, p.get("bars", 90))
        icon = tuple(p["icon"]) if p.get("icon") else None
        badge_color = tuple(p["badge_color"]) if p.get("badge_color") else None
        im = cards.waveform_card(env, p.get("title", "audio.wav"), height=p.get("height", 210), badge=p.get("badge"),
                                 badge_color=badge_color, icon=icon, regions=p.get("regions"),
                                 playhead=p.get("playhead"), bottom_labels=p.get("bottom_labels"))
    elif t == "chip":
        im = cards.label_chip(p["text"], dark=p.get("dark", False))
    elif t == "image":
        im = cards.image_card(p["path"], width=p.get("width", cards.CARD_W))
    else:
        raise SystemExit(f"unknown panel type {t}")
    out = tmp / f"card{idx:03d}.png"
    im.save(out)
    return out


def render(args) -> None:
    work = Path(args.work)
    cut_path = str(work / "cut.mp4")
    meta = json.loads((work / "segments.json").read_text())
    total = meta["duration"]
    plan = json.loads(Path(args.plan).read_text()) if args.plan else {}
    tmp = Path(tempfile.mkdtemp(prefix="ths_"))

    panels = list(plan.get("panels", []))
    if plan.get("hook"):
        hk = plan["hook"]
        panels.insert(0, {"type": "comment", "user": hk["user"], "text": hk["text"], "start": 0, "end": hk.get("end", 3.0),
                          "y": hk.get("y", 150), "anim": "none" if hk.get("static") else "pop"})
    if plan.get("title"):
        tt = plan["title"]
        panels.insert(1 if plan.get("hook") else 0,
                      {"type": "title", "text": tt["text"], "start": tt.get("start", 0), "end": tt.get("end", 2.5),
                       "y": tt.get("y", 320)})
    split_ranges = [tuple(r) for r in plan.get("split", [])]

    inputs = ["-i", cut_path]
    fl = []
    base = "[0:v]"
    # --- split layout: beige background, panels on top, circular face cam below
    if split_ranges:
        face = plan.get("face", {})
        fx, fy, fs = face.get("x", 0.5), face.get("y", 0.36), face.get("size", 0.42)  # crop box in fractions of W
        side = int(W * fs) // 2 * 2
        cx, cy = int(W * fx - side / 2), int(H * fy - side / 2)
        diam = plan.get("circle_size", 380)
        mask = tmp / "mask.png"
        cards.circle_mask(diam).save(mask)
        ring = tmp / "ring.png"
        cards.circle_ring(diam, 6).save(ring)
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(mask), "-loop", "1", "-t", f"{total:.3f}", "-i", str(ring)]
        ccx, ccy = (W - diam) // 2, int(H * plan.get("circle_y", 0.69)) - diam // 2
        en = "+".join(f"between(t,{a},{b})" for a, b in split_ranges)
        fl += [f"[0:v]split[m0][f0]",
               f"[f0]crop={side}:{side}:{max(0, cx)}:{max(0, cy)},scale={diam}:{diam},format=rgba[fc]",
               f"[1:v]format=gray,scale={diam}:{diam}[mk]",
               f"[fc][mk]alphamerge[circ]",
               f"color=c={BEIGE}:s={W}x{H}:r={FPS}:d={total}[bg]",
               f"[bg][circ]overlay={ccx}:{ccy}:shortest=1[bgc]",
               f"[bgc][2:v]overlay={ccx}:{ccy}:shortest=1[splitv]",
               f"[m0][splitv]overlay=0:0:enable='{en}'[b0]"]
        base = "[b0]"
    # --- overlay cards
    n_in = 1 + (2 if split_ranges else 0)
    for i, p in enumerate(panels):
        png = build_card(p, cut_path, tmp, i)
        s, e = float(p["start"]), float(p["end"])
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(png)]
        k = n_in
        n_in += 1
        y0 = p.get("y", 140 if not p.get("stack") else 140 + p["stack"])
        x = p.get("x", "(W-w)/2")
        anim = p.get("anim", "pop")
        lbl = f"p{i}"
        chain = f"[{k}:v]format=rgba"
        if anim != "none":
            chain += f",fade=t=in:st={s:.3f}:d=0.12:alpha=1"
        fl.append(chain + f"[{lbl}]")
        if anim == "pop":
            yexpr = f"{y0}-36*max(0\\,1-(t-{s:.3f})/0.16)"
        else:
            yexpr = str(y0)
        nb = f"[o{i}]"
        fl.append(f"{base}[{lbl}]overlay=x={x}:y='{yexpr}':enable='between(t,{s:.3f},{e:.3f})':eof_action=pass{nb}")
        base = nb
    # --- captions
    words_path = work / "words.json"
    if words_path.exists() and not plan.get("no_captions"):
        words = json.loads(words_path.read_text())
        st = plan.get("captions", {})
        chunks = chunk_words(words, st.get("max_words", 3), st.get("max_chars", 18))
        ass = tmp / "captions.ass"
        write_ass(ass, chunks, split_ranges, st)
        fontsdir = str(Path(cards.font_path("Inter:bold")).parent)
        fl.append(f"{base}ass={ass}:fontsdir={fontsdir}[vc]")
        base = "[vc]"
    fl.append(f"{base}format=yuv420p[vout]")
    fc = tmp / "render_filter.txt"
    fc.write_text(";\n".join(fl))
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex_script", str(fc), "-map", "[vout]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-t", f"{total:.3f}", "-movflags", "+faststart", args.output]
    run(cmd)
    if not args.keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"rendered {args.output} ({total:.1f}s)")


# ----------------------------------------------------------------------------------------------- cli

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cut_opts(p):
        p.add_argument("input")
        p.add_argument("--work", default="work")
        p.add_argument("--noise", type=float, help="silence threshold dB (default: mean volume - 16, clamped -45..-28)")
        p.add_argument("--min-silence", type=float, default=0.30, help="pauses shorter than this are kept")
        p.add_argument("--pre", type=float, default=0.06, help="seconds kept before each phrase")
        p.add_argument("--post", type=float, default=0.10, help="seconds kept after each phrase")
        p.add_argument("--min-segment", type=float, default=0.18)
        p.add_argument("--zooms", default="1.0,1.12", help="zoom cycled on each jump cut")
        p.add_argument("--focus-y", type=float, default=0.35, help="vertical crop bias when zoomed/reframed (0 top, 1 bottom)")
        p.add_argument("--no-cut", action="store_true")
        p.add_argument("--words", help="word timestamps JSON [{w,s,e}] in source time")
        p.add_argument("--words-in-cut-time", action="store_true")
        p.add_argument("--srt", help="SRT transcript in source time")
        p.add_argument("--lang", default=None, help="language for whisper, e.g. it")
        p.add_argument("--whisper-model", default="small")
        p.add_argument("--no-transcribe", action="store_true")

    p1 = sub.add_parser("cut")
    cut_opts(p1)
    p2 = sub.add_parser("render")
    p2.add_argument("--work", default="work")
    p2.add_argument("--plan")
    p2.add_argument("-o", "--output", default="final.mp4")
    p2.add_argument("--keep-tmp", action="store_true")
    p3 = sub.add_parser("auto")
    cut_opts(p3)
    p3.add_argument("--plan")
    p3.add_argument("-o", "--output", default="final.mp4")
    p3.add_argument("--hook-user")
    p3.add_argument("--hook-text")
    p3.add_argument("--title")
    p3.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args()
    if a.cmd == "cut":
        cut(a)
    elif a.cmd == "render":
        render(a)
    else:
        cut(a)
        if not a.plan and (a.hook_text or a.title):
            plan = {}
            if a.hook_text:
                plan["hook"] = {"user": a.hook_user or "@utente", "text": a.hook_text, "end": 3.0}
            if a.title:
                plan["title"] = {"text": a.title, "end": 2.5}
            pp = Path(a.work) / "plan.auto.json"
            pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
            a.plan = str(pp)
        render(a)


if __name__ == "__main__":
    main()
