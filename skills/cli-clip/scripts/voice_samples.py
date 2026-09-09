#!/usr/bin/env python3
# Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
"""ナレーター候補の聞き比べサンプル（VOICEVOX・ローカル）。

使い方: python3 voice_samples.py [出力dir] [style_id ...] | all | styles
  引数なし＝config/voices.json の narrators。all＝全話者×代表1スタイル。styles＝全スタイル（個別のみ）。
  各候補で「話者名＋同じセリフ」を読み、NN_<話者>_<スタイル>.mp3 と結合 all_voices.mp3 を出力する。
  出力dir 既定: ./voice-samples
"""
import sys, json, pathlib, subprocess, urllib.request, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tts_voicevox as v
from env import resolve
E = resolve(); FFMPEG = E.get("ffmpeg") or "ffmpeg"
LINE = "思っていた方向と違うと感じたら、Escキーを一回。それだけで、その場で止まって、次の指示を待ってくれる。"

def synth(sid, text, out, speed=1.05):
    q = urllib.parse.urlencode({"text": v.apply_readings(text), "speaker": sid})
    query = json.load(urllib.request.urlopen(urllib.request.Request(f"{v.HOST}/audio_query?{q}", method="POST"), timeout=60))
    query.update({"speedScale": speed, "outputSamplingRate": 24000, "outputStereo": False, "prePhonemeLength": 0.1, "postPhonemeLength": 0.3})
    req = urllib.request.Request(f"{v.HOST}/synthesis?speaker={sid}", data=json.dumps(query).encode(), headers={"Content-Type": "application/json"}, method="POST")
    pathlib.Path(out).write_bytes(urllib.request.urlopen(req, timeout=180).read())

def main():
    args = sys.argv[1:]
    out = pathlib.Path(args.pop(0)) if args and not args[0].isdigit() and args[0] not in ("all","styles") else pathlib.Path("voice-samples")
    v.ensure_engine(); speakers = v._get("/speakers")
    styles = {st["id"]: (s["name"], st["name"]) for s in speakers for st in s["styles"]}
    mode = args[0] if args and args[0] in ("all","styles") else "pick"
    if mode == "all": ids = [s["styles"][0]["id"] for s in speakers]; out = out/"all-speakers"
    elif mode == "styles": ids = [st["id"] for s in speakers for st in s["styles"]]; out = out/"all-styles"
    else: ids = [int(x) for x in args] or [n["id"] for n in v.NARRATORS.values()]
    out.mkdir(parents=True, exist_ok=True); wavs, rows = [], []
    safe = lambda t: t.replace("/","-").replace("／","-").replace(" ","")
    for i, sid in enumerate(ids, 1):
        name, style = styles[sid]; wav = out/f"{i:02d}_{safe(name)}_{safe(style)}.wav"
        synth(sid, f"{name}、{style}。{LINE}", wav)
        subprocess.run([FFMPEG,"-y","-loglevel","error","-i",wav,"-c:a","libmp3lame","-q:a","3",wav.with_suffix(".mp3")], check=True)
        wavs.append(wav); rows.append(f"{i:02d}  {name}／{style}  (id={sid})"); print(rows[-1])
    if mode != "styles":
        (out/"list.txt").write_text("\n".join(f"file '{w.name}'" for w in wavs))
        subprocess.run([FFMPEG,"-y","-loglevel","error","-f","concat","-safe","0","-i",out/"list.txt","-af","aresample=48000","-c:a","libmp3lame","-q:a","3",out/"all_voices.mp3"], check=True)
    (out/"README.txt").write_text("VOICEVOX ナレーター候補（同じセリフ）\n" + "\n".join(rows) + f"\n\nセリフ: {LINE}\n")
    print(f"\n-> {out}")

if __name__ == "__main__":
    main()
