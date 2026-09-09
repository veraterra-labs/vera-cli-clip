# Copyright (c) 2026 Tsuyoshi Hemmi / License: CC BY-NC-SA 4.0
"""字幕の強制アライメント（whisper.cpp）。cli-clip 版＝kirin-ai-lab/pipeline/ds_align.py から移植。

用途は文字起こしではなく、台本の字幕チャンク境界を実発話の時刻（実ポーズ）に合わせること。文字は台本が正。

方針（先日までの「文字数比で全体に均等割り」がズレた根本原因への対処）:
  日本語の発話は「文末（。！？）＝長い無音、読点（、）＝短い無音」で区切られる。
  字幕chunkは split_caption がまさにこの句読点で割っている。だから chunk境界は
  「実際の無音（ポーズ）」に一致させるのが正しい。均等割りはポーズの偏りを無視するのでズレる。

実装:
  1) whisper.cpp(-ojf) のトークン時刻で、台本chunkの境界時刻を推定（実発話タイムライン）。
     ※認識テキストは誤変換を含むが、時刻だけ使う。台本側は読み辞書適用後の文字数で内挿。
  2) 推定境界を、ffmpeg silencedetect が見つけた実ポーズの中心へスナップ（近傍のみ）。
     → 字幕が「無音の最中」に切り替わる＝視覚的にピタッと合う。
  3) 単調増加・尺Tにクランプして表示秒(durs)と表示窓(windows)を返す。

検証（verify_windows）: 各境界が実ポーズ上にあるか／whisper推定窓と表示窓の中心ズレを数値化。
"""
import json, os, subprocess, pathlib
from env import resolve as _resolve
_ENV = _resolve()
WHISPER = _ENV.get("whisper_cli") or "whisper-cli"
MODEL = _ENV.get("whisper_model") or os.path.expanduser("~/.cache/whisper-cpp/ggml-base.bin")
_DN = subprocess.DEVNULL


def _token_times(wav):
    """whisper.cpp のトークン (累積認識文字数, 開始秒) 列。結果は a.wtok.json にキャッシュ。失敗で []。"""
    wav = pathlib.Path(wav)
    jf = wav.parent / (wav.stem + ".wtok.json")
    if not jf.exists():
        try:
            subprocess.run([WHISPER, "-m", MODEL, "-l", "ja", "-ojf",
                            "-of", str(wav.parent / (wav.stem + ".wtok")), str(wav)],
                           stdout=_DN, stderr=_DN, check=True)
        except Exception:
            return []
    try:
        d = json.loads(jf.read_bytes().decode("utf-8", "replace"))  # 日本語トークンが多バイト途中で割れUTF-8破損→寛容デコード
    except Exception:
        return []
    pts, acc = [], 0
    for s in d.get("transcription", []):
        for t in s.get("tokens", []):
            txt = t.get("text", ""); off = t.get("offsets") or {}
            if not txt or txt[0] in "[<" or off.get("from") is None:  # 特殊トークン除外
                continue
            acc += len(txt); pts.append((acc, off["from"] / 1000.0))
    return pts


def pauses(wav, noise=-32, d=0.12):
    """無音区間 [(start,end),...]（実ポーズ）。silencedetect。"""
    err = subprocess.run([_ENV.get("ffmpeg") or "ffmpeg", "-hide_banner", "-i", str(wav),
                          "-af", f"silencedetect=noise={noise}dB:d={d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    gaps, cur = [], None
    for ln in err.splitlines():
        if "silence_start" in ln:
            cur = float(ln.split("silence_start:")[1].strip())
        elif "silence_end" in ln and cur is not None:
            gaps.append((cur, float(ln.split("silence_end:")[1].split("|")[0].strip()))); cur = None
    return gaps


def _interp(pts, frac):
    """認識タイムラインの frac(0..1) に対応する実時刻（トークン時刻で内挿）。"""
    totw = pts[-1][0] or 1
    tgt = frac * totw; pc, pt = 0, 0.0
    for c, t in pts:
        if c >= tgt:
            span = c - pc
            return pt + (t - pt) * ((tgt - pc) / span if span else 0)
        pc, pt = c, t
    return pts[-1][1]


def whisper_chunk_windows(wav, chunks, readings_fn=lambda x: x):
    """whisperトークン時刻から、台本chunkの実発話窓 [(s,e),...] を推定。失敗時 None。"""
    pts = _token_times(wav)
    if len(pts) < 2 or len(chunks) <= 1:
        return None
    slen = [max(1, len(readings_fn(c))) for c in chunks]; tot = sum(slen)
    edges, F = [0.0], 0
    for w in slen:
        F += w; edges.append(_interp(pts, F / tot))
    return [(edges[i], edges[i + 1]) for i in range(len(chunks))]


def caption_windows(wav, chunks, D, T, readings_fn=lambda x: x, snap_tol=0.9):
    """字幕chunkの表示窓 [(start,end),...]（beatローカル秒, 末尾はTまで）と durs を返す。

    1) whisper推定境界 → 2) 近傍ポーズ中心へスナップ → 3) 単調＆Tクランプ。
    whisper不可なら文字数比[0,D]で代替。
    """
    slen = [max(1, len(readings_fn(c))) for c in chunks]; tot = sum(slen)
    w = whisper_chunk_windows(wav, chunks, readings_fn)
    if w:
        bounds = [w[i][1] for i in range(len(chunks) - 1)]   # 各chunkの推定終了＝境界
    else:
        bounds, F = [], 0
        for s in slen[:-1]:
            F += s; bounds.append(D * F / tot)
    mids = sorted((a + b) / 2 for a, b in pauses(wav))
    snapped, used, prev = [], set(), 0.0
    for est in bounds:   # 左→右に消費（同一ポーズへの二重スナップを防ぐ）
        cand = [m for m in mids if id(m) not in used and m > prev + 0.10 and abs(m - est) <= snap_tol]
        if cand:
            m = min(cand, key=lambda m: abs(m - est)); used.add(id(m)); snapped.append(m); prev = m
        else:
            snapped.append(max(est, prev + 0.15)); prev = snapped[-1]
    edges = [0.0]
    for b in snapped:
        edges.append(min(T - 0.05, max(b, edges[-1] + 0.15)))   # 単調増加＆尺内
    edges.append(T)
    windows = [(edges[i], edges[i + 1]) for i in range(len(chunks))]
    durs = [e - s for s, e in windows]
    return durs, windows


def verify_windows(wav, chunks, windows, readings_fn=lambda x: x):
    """表示窓の整合を数値化。返り値 dict:
       max_start_drift: 「字幕の表示開始」と「whisper実発話の開始」のズレ最大(秒, Noneで判定不能)
       off_pause: 実ポーズ上に無い境界の数（少ないほど良い）
       n: chunk数
    """
    res = {"n": len(chunks), "max_start_drift": None, "off_pause": 0, "worst": None}
    w = whisper_chunk_windows(wav, chunks, readings_fn)
    if w:
        # 「字幕の表示開始」と「実発話の開始」のズレで評価。中心比較は最終chunkが余韻でホールド
        # される(窓が長い)ぶん中心が後ろにズレて誤検知するため、開始時刻で比べる＝同期の本質。
        mx, worst = 0.0, None
        for i, (ws, _we) in enumerate(w):
            ds, _de = windows[i]
            drift = abs(ws - ds)
            if drift > mx:
                mx, worst = drift, i
        res["max_start_drift"] = round(mx, 3); res["worst"] = worst
    gaps = pauses(wav)
    for s, _e in windows[1:]:   # 各境界(=次chunk開始)が実ポーズ内か
        if not any(a - 0.12 <= s <= b + 0.12 for a, b in gaps):
            res["off_pause"] += 1
    return res
