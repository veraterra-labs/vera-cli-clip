#!/usr/bin/env python3
# Copyright (c) 2026 Tsuyoshi Hemmi
"""cli-clip 実行環境の解決（macOS / WSL Ubuntu 共通）。

優先順: 環境変数 > config/env.json（cli-clip-setup が書く） > 既定パス（~/.local/opt/cli-clip/...） > PATH。
`python3 env.py` で現在の解決結果を表で出す（setup の check と同じ）。
"""
import os, sys, json, shutil, pathlib, platform

SKILL = pathlib.Path(__file__).resolve().parent.parent      # skills/cli-clip
CONFIG = SKILL / "config"
OPT = pathlib.Path(os.environ.get("CLI_CLIP_HOME", pathlib.Path.home() / ".local/opt/cli-clip"))
OS = "macos" if platform.system() == "Darwin" else "linux"

def _envjson():
    f = CONFIG / "env.json"
    try: return json.loads(f.read_text()) if f.exists() else {}
    except Exception: return {}

def _first(*cands):
    for c in cands:
        if not c: continue
        p = pathlib.Path(str(c)).expanduser()
        if p.exists(): return str(p)
    return None

def resolve():
    e = _envjson()
    r = {
        "os": OS,
        "ffmpeg": os.environ.get("FFMPEG") or e.get("ffmpeg") or shutil.which("ffmpeg"),
        "ffprobe": os.environ.get("FFPROBE") or e.get("ffprobe") or shutil.which("ffprobe"),
        "node": os.environ.get("NODE") or e.get("node") or shutil.which("node"),
        "tmux": shutil.which("tmux"),
        "claude": shutil.which("claude"),
        "whisper_cli": _first(os.environ.get("WHISPER_CLI"), e.get("whisper_cli"),
                              OPT / "whisper.cpp/build/bin/whisper-cli", shutil.which("whisper-cli")),
        "whisper_model": _first(os.environ.get("WHISPER_MODEL"), e.get("whisper_model"),
                                OPT / "whisper.cpp/models/ggml-base.bin", "~/.cache/whisper-cpp/ggml-base.bin"),
        "voicevox_run": _first(os.environ.get("VOICEVOX_ENGINE_BIN"), e.get("voicevox_run"),
                               OPT / "voicevox/engine/run", "~/.local/opt/voicevox/engine/run"),
        "voicevox_host": os.environ.get("VOICEVOX_HOST") or e.get("voicevox_host") or "http://127.0.0.1:50021",
        "playwright": _first(SKILL / "node_modules/playwright/package.json"),
        "review_copy_dir": os.environ.get("CLI_CLIP_REVIEW_DIR") or e.get("review_copy_dir") or "",
    }
    return r

def check(verbose=True):
    r = resolve(); ok = True
    need = ["ffmpeg", "ffprobe", "node", "playwright", "whisper_cli", "whisper_model", "voicevox_run"]
    opt = ["tmux", "claude", "review_copy_dir"]
    rows = []
    for k in need + opt:
        v = r.get(k); good = bool(v)
        if k in need and not good: ok = False
        rows.append(f"  {'OK ' if good else ('-- ' if k in opt else 'NG ')} {k:16s} {v or '(not found)'}")
    if verbose:
        print(f"cli-clip env ({r['os']})"); print("\n".join(rows))
        print("RESULT:", "READY" if ok else "MISSING（cli-clip-setup を実行）")
    return ok, r

if __name__ == "__main__":
    ok, _ = check(); sys.exit(0 if ok else 1)
