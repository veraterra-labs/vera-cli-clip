#!/usr/bin/env python3
# Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
"""cli-clip ビルダ：clip.json（台本＋画面ステップ＋パネル文言の正本）→ mp4。macOS / WSL Ubuntu 共通。

  TTS(VOICEVOX) → 字幕を whisper.cpp で実発話に同期 → templates/clip_frame.html を Playwright で録画
  → カットmux → 連結 → ラウドネス整合 → プレビューPNG → 検査レポート →（設定があれば）レビュー用コピー

使い方（スキルの scripts/ から）:
  python3 build_clip.py <clips/<id>/clip.json>                 # 声が未指定なら 3声＋all の選択を出す
  python3 build_clip.py <clip.json> --voices kurono            # 1声だけ（キー or style_id、カンマ区切り可）
  python3 build_clip.py <clip.json> --lint                     # 台本ルール検査のみ
  python3 build_clip.py <clip.json> --only d2                  # 指定カットだけ作り直し（全声）
  python3 build_clip.py <clip.json> --force --tag v2           # 全カット作り直し
  python3 build_clip.py <clip.json> --align prop               # 字幕を文字数比例に（whisper を使わない）
出力: <clip.jsonのフォルダ>/build/<voice>/<id>_<tag>_<話者名>.mp4 ／ preview/*.png ／ report.txt

確定パラメータ: 有声カット尺＝音声開始遅延(≤150ms)+音声+100ms+tail_ms ／ 無声カード＝fixed_ms ／ 字幕26字チャンク
              音声 aac 48kHz 2ch ／ BGM・エンディングなし（構成＝タイトル→説明スライド→デモ）／ 最終 I=theme.loudness_lufs
"""
import sys, os, json, re, pathlib, subprocess, urllib.parse, hashlib, shutil, argparse
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from env import resolve, SKILL, CONFIG
import tts_voicevox as tv
import align as ds_align

ENV = resolve()
FFMPEG = ENV.get("ffmpeg") or "ffmpeg"; FFPROBE = ENV.get("ffprobe") or "ffprobe"; NODE = ENV.get("node") or "node"
THEME = json.loads((CONFIG / "theme.json").read_text())
FRAME = SKILL / "templates" / "clip_frame.html"
CAP = HERE / "cap_frame.mjs"
FPS = 30
LOUD = "acompressor=threshold=-24dB:ratio=3:attack=10:release=250:makeup=9,alimiter=limit=0.95"
EP_REF = float(THEME.get("loudness_lufs", -10.4))

def sh(cmd, check=False):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(map(str,cmd))}\n{r.stderr[-800:]}")
    return r
def adur(p): return float(sh([FFPROBE,"-v","error","-show_entries","format=duration","-of","csv=p=0",p]).stdout.strip())
def lufs(p):
    err = sh([FFMPEG,"-hide_banner","-i",p,"-af","ebur128","-f","null","-"]).stderr
    ms = re.findall(r"I:\s+(-?[\d.]+) LUFS", err); return float(ms[-1]) if ms else None

def split_caption(text, maxlen=26):
    text = text.strip("「」 ")
    sents = [s for s in re.split(r'(?<=[。！？…])', text) if s.strip()]
    out = []
    for s in sents:
        if len(s) > maxlen:
            cur = ""
            for p in re.split(r'(?<=、)', s):
                if len(cur)+len(p) > maxlen and cur: out.append(cur); cur = p
                else: cur += p
            if cur: out.append(cur)
        elif out and len(out[-1])+len(s) <= maxlen and out[-1][-1] in "。！？…": out[-1] += s
        else: out.append(s)
    return [c.strip("、 ") for c in out if c.strip("、 ")] or [text]

def sub_windows(text, total_ms, wav=None, align="whisper", readings=None):
    """字幕チャンク→表示ms。既定は whisper.cpp（実発話→実ポーズへスナップ）。失敗時は文字数比例。"""
    chunks = split_caption(text)
    if wav is not None and align == "whisper" and len(chunks) > 1 and ENV.get("whisper_cli"):
        try:
            D = total_ms/1000.0
            durs, _ = ds_align.caption_windows(wav, chunks, D, D, lambda t: tv.apply_readings(t, readings))
            ms = [max(200, int(round(d*1000))) for d in durs]; ms[-1] += total_ms - sum(ms)
            if ms[-1] > 200: return [[c, m] for c, m in zip(chunks, ms)]
        except Exception as e: print(f"  [align] whisper 失敗→文字数比例: {e}")
    n = sum(len(c) for c in chunks) or 1
    ms = [int(round(total_ms*len(c)/n)) for c in chunks]; ms[-1] += total_ms - sum(ms)
    return [[c, m] for c, m in zip(chunks, ms)]

# ---------------------------------------------------------------- lint（台本ルール）
NIN = re.compile(r"あなた|君は|君が|君の|君も"); DANTEI = re.compile(r"必ず|絶対|100%|決して")
POLITE = re.compile(r"(です|ます|ません|でした|ましょう|ください|でしょう|ですね|ますね|ますか|ですか|ますよ|ですよ)$")   # ですます調の文末
TERMS = []   # 用語の平易化辞書 config/terms.tsv（語, 言い換え）
_tp = CONFIG / "terms.tsv"
if _tp.exists():
    for _ln in _tp.read_text().splitlines():
        if _ln.strip() and not _ln.startswith("#"):
            _w, *_r = _ln.split("\t"); TERMS.append((_w.strip(), (_r[0].strip() if _r else "")))
def lint(spec):
    warns, total = [], 0
    for c in spec["cuts"]:
        cid = c["id"]; t = c.get("text") or ""
        if t:
            total += len(t)
            if NIN.search(t): warns.append(f"[{cid}] 二人称（あなた/君）: {NIN.search(t).group()}")
            if DANTEI.search(t): warns.append(f"[{cid}] 断定語: {DANTEI.search(t).group()}（『〜ことが多いです』等へ）")
            for sent in re.split(r"[。！？]", t):                       # 文体: ですます調（講師スタイル）
                sent = sent.strip().rstrip("」』）)")
                if sent and not POLITE.search(sent): warns.append(f"[{cid}] 文体（ですます調でない文末）: …{sent[-14:]}")
        ok = set(spec["meta"].get("terms_ok") or [])
        fields = " ".join(str(c.get(k) or "") for k in ("text","cap","prompt","note","badge","left_html"))
        for w, alt in TERMS:                                            # 用語の平易化（警告のみ）
            if w not in ok and re.search(re.escape(w), fields, re.I): warns.append(f"[{cid}] 専門用語「{w}」→「{alt}」（meta.terms_ok で除外可）")
        b = c.get("badge") or ""
        if len(b) > 14: warns.append(f"[{cid}] 右パネルのバッジ {len(b)}字 > 14字: {b}")
        if c.get("type") == "demo" and not c.get("S") and not c.get("left_html"): warns.append(f"[{cid}] demo なのに S も left_html も無い")
        if c.get("type") == "demo" and c.get("S") and not any(s.get("t") == "beat" for s in c["S"]): warns.append(f"[{cid}] S に beat が無い")
    kinds = [c.get("type") + ":" + str(c.get("kind") or ("slide" if c.get("left_html") else "term")) for c in spec["cuts"]]
    if not kinds or kinds[0] != "card:title": warns.append("構成: 先頭はタイトルカード（type=card）にする")
    if len(kinds) > 1 and kinds[1] != "demo:slide": warns.append("構成: 2番目は説明スライド（left_html）にする")
    est = total/5.5 + sum((c.get("fixed_ms",0)+c.get("tail_ms",0))/1000 for c in spec["cuts"]) + 0.5*len(spec["cuts"])
    mx = spec["meta"].get("max_sec", THEME.get("max_sec_default", 130))
    info = f"セリフ {total}字 ≈ 音声 {total/5.5:.0f}s ／ 想定フル尺 ≈ {est:.0f}s（上限 {mx}s。基本1〜2分、最長5分）"
    if est > mx: warns.append(f"尺超過見込み: {info}")
    if est < 45: warns.append(f"尺不足見込み: {info}")
    return warns, info

# ---------------------------------------------------------------- 誤読チェック（whisper で聞き戻して原文と比較。目安であり最終判断は AI が両方を読む）
def reading_check(spec, VOX, readings):
    import difflib
    _P = re.compile(r"[\s、。「」『』（）()・,.!?！？…―—\-]")
    out = []
    for c in spec["cuts"]:
        t = c.get("text"); wav = VOX/f"{c['id']}.wav"
        if not t or not wav.exists() or not ENV.get("whisper_cli"): continue
        try:
            ds_align._token_times(wav)                       # wtok.json を作る／キャッシュを使う
            jf = wav.with_suffix(".wtok.json")
            d = json.loads(jf.read_bytes().decode("utf-8", "replace"))
            heard = "".join(x.get("text", "") for x in d.get("transcription", []))
        except Exception as e:
            out.append(f"  {c['id']:8s} whisper 不可: {e}"); continue
        a = _P.sub("", tv.apply_readings(t, readings)); b = _P.sub("", heard)
        r = difflib.SequenceMatcher(None, a, b).ratio()
        flag = "要確認" if r < 0.55 else "ok"
        out.append(f"  {c['id']:8s} 類似度 {r:.2f} {flag}\n           原文: {t}\n           聞取: {heard.strip()}")
    return out

# ---------------------------------------------------------------- build
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--lint", action="store_true")
    ap.add_argument("--only", default=""); ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag", default="v1"); ap.add_argument("--no-copy", action="store_true", help="レビュー用コピーをしない")
    ap.add_argument("--align", default="whisper", choices=["whisper","prop"])
    ap.add_argument("--voices", default="", help="all（3声セット）／キー or style_id をカンマ区切り。未指定なら meta.voices、それも無ければ対話で選択（非対話なら終了）")
    a = ap.parse_args()
    spec_path = pathlib.Path(a.spec).resolve(); spec = json.loads(spec_path.read_text())
    ids = [c["id"] for c in spec["cuts"]]; assert len(set(ids)) == len(ids), "cut id が重複"
    warns, info = lint(spec); print(f"[lint] {info}")
    for w in warns: print(f"  ⚠ {w}")
    if a.lint: print("[lint] done"); return
    if any("二人称" in w or "断定語" in w for w in warns): print("[lint] 二人称/断定の警告がある間はビルドしない"); sys.exit(2)
    ok, _ = __import__("env").check(verbose=False)
    if not ok: print("[env] 依存が足りない。cli-clip-setup を実行（python3 scripts/env.py で確認）"); sys.exit(3)
    sel = a.voices or spec["meta"].get("voices") or choose_voices()
    keys = list(tv.NARRATORS) if sel == "all" else [k.strip() for k in sel.split(",") if k.strip()]
    for key in keys: build_one(a, spec, spec_path, key)

def choose_voices():
    """--voices も meta.voices も無いときの選択。端末なら対話、非対話なら明示を求めて終了。"""
    items = list(tv.NARRATORS.items())
    print("\nナレーターの声を選んでください（--voices で指定も可）:")
    for i, (k, v) in enumerate(items, 1): print(f"  {i}) {k:8s} {v['name']}／{v['style']}  (id={v['id']})")
    print(f"  {len(items)+1}) all      3声セット（全部作って聞き比べ）")
    if not sys.stdin.isatty():
        print("非対話実行のため選べません。--voices all または --voices kurono|no7|metan を指定してください。"); sys.exit(4)
    while True:
        ans = input(f"番号 or キー [{len(items)+1}]: ").strip() or str(len(items)+1)
        if ans in tv.NARRATORS or ans == "all": return ans
        if ans.isdigit() and 1 <= int(ans) <= len(items)+1:
            return "all" if int(ans) == len(items)+1 else items[int(ans)-1][0]
        print("  ?")

def build_one(a, spec, spec_path, key):
    meta = spec["meta"]; vp = tv.voice_params(key)
    os.environ["VOICEVOX_STYLE"] = str(vp["id"])
    vname = (vp["name"] + ("" if vp["style"] in ("ノーマル","ふつう") else vp["style"])).replace("/","-").replace(" ","")
    print(f"\n===== voice {key}: {vp['name']}／{vp['style']} (id={vp['id']}) =====")
    OUT = spec_path.parent / "build" / (key if key in tv.NARRATORS else f"v{vp['id']}")
    VOX, SEC, PRE, NORM = OUT/"vox", OUT/"section", OUT/"preview", OUT/"norm"
    for d in (OUT, VOX, SEC, PRE, NORM): d.mkdir(parents=True, exist_ok=True)
    only = set(x for x in a.only.split(",") if x)
    if a.force:
        for f in list(SEC.glob("*.mp4")) + list(VOX.glob("*.wav")): f.unlink()
    readings = tv.load_readings(spec.get("readings") or None)
    theme = {k: THEME.get(k) for k in ("channel","series","colors","font_sans","font_mono")}

    for cut in spec["cuts"]:
        cid = cut["id"]; out = SEC/f"cut_{cid}.mp4"
        if out.exists() and not (only and cid in only) and not a.force: print(f"[have] {cid} {adur(out):.2f}s"); continue
        if only and cid not in only and out.exists(): continue
        text = cut.get("text"); tail = int(cut.get("tail_ms", 300 if text else 0))
        cut = dict(cut)
        if cut.get("left_html"): cut["left_html"] = cut["left_html"].replace("{{CLIP}}", str(spec_path.parent)).replace("{{SKILL}}", str(SKILL))
        if text:
            wav = VOX/f"{cid}.wav"
            if not wav.exists() or (only and cid in only and a.force): tv.tts(text, wav, key, readings)
            d = adur(wav); beatms = int(d*1000) + 100
            subs = sub_windows(text, int(d*1000), wav, a.align, readings)
            webm, beat = render(theme, meta, cut, OUT, beatms, tail, subs)
            bms = int(round(beat*1000));  bms = bms if cut.get("beat_sync") else min(bms, 150)
            cutargs = ["-t", f"{bms/1000 + d + 0.100 + tail/1000:.3f}"] if cut.get("static_end", True) else []
            sh([FFMPEG,"-y","-loglevel","error","-i",webm,"-i",wav,"-filter_complex",f"[1:a]adelay={bms}|{bms},apad[a]",
                "-map","0:v","-map","[a]","-r",FPS,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-ac","2","-ar","48000",
                "-shortest","-movflags","+faststart"] + cutargs + [out], check=True)
            print(f"[cut] {cid} voice {d:.1f}s beat={beat:.2f}s tail={tail}ms -> {out.name}")
        else:
            fixed = int(cut.get("fixed_ms", 2200))
            webm, beat = render(theme, meta, cut, OUT, fixed, tail, None)
            cutargs = ["-t", f"{beat + (fixed+tail)/1000:.3f}"] if cut.get("static_end", True) else []
            sh([FFMPEG,"-y","-loglevel","error","-i",webm,"-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-map","0:v","-map","1:a",
                "-r",FPS,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-ac","2","-ar","48000","-shortest","-movflags","+faststart"] + cutargs + [out], check=True)
            print(f"[cut] {cid} silent {fixed}ms -> {out.name}")

    # ---- 連結（PCM中間）→ ラウドネス → 出力 ----
    lst = []
    for i, c in enumerate(spec["cuts"]):
        src = SEC/f"cut_{c['id']}.mp4"; dst = NORM/f"{i:02d}_{c['id']}.mov"
        sh([FFMPEG,"-y","-loglevel","error","-i",src,"-af","aresample=48000,aformat=channel_layouts=stereo","-r",FPS,
            "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p","-c:a","pcm_s16le",dst], check=True)
        lst.append((c["id"], dst, adur(dst)))
    (OUT/"segs.txt").write_text("\n".join(f"file '{d.relative_to(OUT)}'" for _,d,_ in lst))
    full = OUT/"full.mov"
    sh([FFMPEG,"-y","-loglevel","error","-f","concat","-safe","0","-i",OUT/"segs.txt","-c","copy",full], check=True)
    final = OUT/f"{meta['id']}_{a.tag}_{vname}.mp4"
    if final.exists(): shutil.copy2(final, final.with_name(final.stem + "_pre.mp4"))
    sh([FFMPEG,"-y","-loglevel","error","-i",full,"-af",LOUD,"-map","0:v","-map","0:a","-c:v","copy","-c:a","aac","-ar","48000","-ac","2","-b:a","192k",final], check=True)
    for _ in range(3):
        I0 = lufs(final)
        if I0 is None or abs(EP_REF-I0) <= 0.3: break
        tmp = OUT/"_trim.mp4"
        sh([FFMPEG,"-y","-loglevel","error","-i",final,"-map","0:v","-map","0:a","-c:v","copy","-af",f"volume={EP_REF-I0:.2f}dB","-c:a","aac","-ar","48000","-ac","2","-b:a","192k",tmp], check=True)
        tmp.replace(final); print(f"[loud] trim {EP_REF-I0:+.1f}dB (I {I0:.1f} -> {EP_REF})")

    # ---- プレビュー・検査 ----
    t = 0.0; starts = {}
    for lbl, _, d in lst: starts[lbl] = (t, d); t += d
    for lbl, (s, d) in starts.items(): sh([FFMPEG,"-y","-loglevel","error","-ss",f"{s+d*0.55:.2f}","-i",final,"-frames:v","1",PRE/f"{lbl}.png"])
    ch = sh([FFPROBE,"-v","error","-select_streams","a:0","-show_entries","stream=codec_name,sample_rate,channels","-of","csv=p=0",final]).stdout.strip()
    drift = []
    for c in spec["cuts"]:
        p = SEC/f"cut_{c['id']}.mp4"
        v = sh([FFPROBE,"-v","error","-select_streams","v:0","-show_entries","stream=duration","-of","csv=p=0",p]).stdout.strip()
        au = sh([FFPROBE,"-v","error","-select_streams","a:0","-show_entries","stream=duration","-of","csv=p=0",p]).stdout.strip()
        try:
            if abs(float(v)-float(au)) > 0.06: drift.append(f"{c['id']} v={v} a={au}")
        except ValueError: drift.append(f"{c['id']} probe失敗")
    rc_lines = reading_check(spec, VOX, readings)
    I = lufs(final); T = adur(final); mx = meta.get("max_sec", THEME.get("max_sec_default", 130))
    ok = (50 <= T <= mx) and ch.startswith("aac,48000,2") and I is not None and abs(I-EP_REF) <= 0.3 and not drift
    rep = [str(final), f"voice: {tv.credit(key)}（{vp['style']} id={vp['id']}）",
           f"total {T:.1f}s ({T/60:.2f}min)  audio {ch}  I={I} LUFS  size {final.stat().st_size//1024}KB", "cuts:"] + \
          [f"  {lbl:8s} {s:6.2f}s +{d:5.2f}s" for lbl,(s,d) in starts.items()] + \
          ["A/V drift: " + (", ".join(drift) if drift else "none"), f"CHECK: {'PASS' if ok else 'WARN'}  (尺50–{mx}s / aac48k2ch / I={EP_REF}±0.3 / drift無し)",
           "reading (whisper 聞き戻し。要確認は原文と聞取を読んで誤読か判断。base モデルなので漢字がカナになるのは正常):"] + (rc_lines or ["  （whisper 未設定のため省略）"])
    (OUT/"report.txt").write_text("\n".join(rep)); print("\n".join(rep))

    # ---- レビュー用コピー（theme.review_copy_dir があれば）----
    rc = ENV.get("review_copy_dir") or THEME.get("review_copy_dir") or ""
    if rc and not a.no_copy:
        dst = pathlib.Path(rc).expanduser() / meta["id"]; dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, dst/final.name)
        h1 = hashlib.md5(final.read_bytes()).hexdigest(); h2 = hashlib.md5((dst/final.name).read_bytes()).hexdigest()
        print(f"[copy] {dst/final.name}\n  md5 {h1} / {h2} {'一致' if h1==h2 else '不一致!!'}")

def render(theme, meta, cut, OUT, beatms, tailms, subs):
    for w in OUT.glob("*.webm"): w.unlink()
    payload = {"theme": theme, "meta": meta, "cut": {k:v for k,v in cut.items() if k != "text"}, "beatms": beatms, "tailms": tailms, "fast": True, "subs": subs}
    q = "spec=" + urllib.parse.quote(json.dumps(payload, ensure_ascii=False), safe="")
    r = sh([NODE, CAP, FRAME, OUT, "1920", "1080", q])
    m = re.search(r"BEAT:([0-9.]+)", r.stdout); webms = sorted(OUT.glob("*.webm"))
    if not webms: raise RuntimeError(f"render failed {cut['id']}: {(r.stderr or r.stdout)[-600:]}")
    return webms[0], (float(m.group(1)) if m else 0.0)

if __name__ == "__main__":
    main()
