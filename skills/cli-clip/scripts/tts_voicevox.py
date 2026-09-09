#!/usr/bin/env python3
# Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
"""cli-clip の音声＝VOICEVOX ENGINE（ローカル・無料）。macOS / WSL Ubuntu 共通。

使い方: python3 tts_voicevox.py "<text>" <out.wav> [voice_key|style_id]
  - エンジン未起動なら env.py が解決した run バイナリを自動起動（--host 127.0.0.1 --port 50021）。
  - 読み辞書 config/readings.tsv ＋ 呼び出し側の追加辞書を TTS 直前にだけ適用（字幕は原文のまま）。
  - 出力 24kHz mono 16bit wav。
  - ナレーター候補は config/voices.json（narrators）。環境変数 VOICEVOX_STYLE で style_id を強制上書き可。

クレジット: 概要欄に「VOICEVOX:<話者名>」を必ず表記（各キャラの利用規約は https://voicevox.hiroshiba.jp/ を確認）。
"""
import sys, os, json, time, pathlib, subprocess, urllib.request, urllib.parse
from env import resolve, CONFIG

_E = resolve()
HOST = _E["voicevox_host"]
ENGINE_BIN = _E.get("voicevox_run")
VOICES = json.loads((CONFIG / "voices.json").read_text())
NARRATORS = VOICES["narrators"]

# ---- 読み辞書（順序保持）
def load_readings(extra=None):
    d = {}
    if extra: d.update(extra)                       # 呼び出し側（clip.json）の辞書を先に＝優先
    for ln in (CONFIG / "readings.tsv").read_text().splitlines():
        if not ln.strip() or ln.startswith("#"): continue
        k, _, v = ln.partition("\t")
        if k and v and k not in d: d[k] = v
    return d
READINGS = load_readings()
def apply_readings(t, readings=None):
    for k, v in (readings or READINGS).items(): t = t.replace(k, v)
    return t

def _get(path):
    return json.load(urllib.request.urlopen(HOST + path, timeout=30))

def ensure_engine():
    try: _get("/version"); return
    except Exception: pass
    if not ENGINE_BIN or not pathlib.Path(ENGINE_BIN).exists():
        raise SystemExit(f"VOICEVOX engine not running and binary not found ({ENGINE_BIN}). run: cli-clip-setup")
    port = HOST.rsplit(":", 1)[-1]
    subprocess.Popen([ENGINE_BIN, "--host", "127.0.0.1", "--port", port],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(180):
        time.sleep(1)
        try: _get("/version"); return
        except Exception: continue
    raise SystemExit("VOICEVOX engine failed to start within 180s")

_STYLES = None
def style_label(sid):
    """style_id → (話者名, スタイル名)"""
    global _STYLES
    if _STYLES is None:
        ensure_engine()
        _STYLES = {st["id"]: (sp["name"], st["name"]) for sp in _get("/speakers") for st in sp["styles"]}
    return _STYLES.get(int(sid), ("?", "?"))

def voice_params(key):
    """voice_key or style_id → dict(name, style, id, speed, pitch, intonation)"""
    if str(key) in NARRATORS: return dict(NARRATORS[str(key)])
    sid = int(key); n, s = style_label(sid)
    return {"name": n, "style": s, "id": sid, "speed": 1.05, "pitch": 0.0, "intonation": 1.1}

def tts(text, out, voice="kurono", readings=None):
    ensure_engine()
    sp = voice_params(os.environ.get("VOICEVOX_STYLE", voice))
    sid = sp["id"]
    q = urllib.parse.urlencode({"text": apply_readings(text, readings), "speaker": sid})
    query = json.load(urllib.request.urlopen(urllib.request.Request(f"{HOST}/audio_query?{q}", method="POST"), timeout=60))
    query.update({"speedScale": sp["speed"], "pitchScale": sp["pitch"], "intonationScale": sp["intonation"],
                  "outputSamplingRate": 24000, "outputStereo": False, "prePhonemeLength": 0.1, "postPhonemeLength": 0.1})
    req = urllib.request.Request(f"{HOST}/synthesis?speaker={sid}", data=json.dumps(query).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    wav = urllib.request.urlopen(req, timeout=180).read()
    pathlib.Path(out).write_bytes(wav)
    print(f"[VOICEVOX ok] {pathlib.Path(out).name}  {sp['name']}/{sp['style']}(id={sid})  ({(len(wav)-44)/48000:.2f}s)")
    return sp

def credit(voice):
    return "VOICEVOX:" + voice_params(voice)["name"]

if __name__ == "__main__":
    tts(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else VOICES.get("default_key", "kurono"))
