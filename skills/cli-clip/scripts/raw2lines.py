#!/usr/bin/env python3
# Copyright (c) 2026 Tsuyoshi Hemmi / License: CC BY-NC-SA 4.0
"""raw pane スナップショット → clip.json の画面ステップ S の下書き（清書の叩き台）。cli-clip 版。

使い方: python3 raw2lines.py <raw/NN_label.txt> [--from "<regex>"]
  Claude Code の起動ボックス・ステータス行・Tip 行を落とし、残った行を行タイプ推定つきの JSON 配列で出す。
  --from を渡すとその行から下だけ（例: --from "❯ このフォルダ"）。
  出力は捏造しない前提の“抽出”であり、最終的な S は人（Vera）が transcript.md と突き合わせて確定する。
"""
import sys, re, json, argparse

BOX = re.compile(r"^[╭╰│╮╯─]|^\s*[│]")
NOISE = re.compile(r"^\s*(⎿\s+Tip:|Tips for|Run /init|What's new|/release-notes|▎|⚠ \d+ MCP|⏸ |.* in /.*ctx:|─{20,}|Welcome back|▐|▝|Fable|Claude Max)")

def guess(l):
    s = l.rstrip()
    if re.match(r"^\s*❯\s+\d+\.", s) or re.match(r"^\s*❯ (Restore|Yes|No)", s): return "menusel"
    if re.match(r"^\s*❯\s*$", s): return "ret"
    if s.startswith("❯ ") or s.startswith("> "): return "user"
    if s.lstrip().startswith("⏺"): return "out"
    if s.lstrip().startswith("⎿"): return "sys"
    if re.search(r"Do you want|proceed\?|Esc to cancel|Enter to continue", s): return "pm"
    if re.match(r"^\s*\d+\s*[-−]", s) or re.match(r"^\s*-\s", s): return "del"
    if re.match(r"^\s*\d+\s*\+", s): return "add"
    if s.lstrip().startswith("⚠"): return "warn"
    if s.lstrip().startswith("✻") or s.lstrip().startswith("·"): return "sys"
    if s.startswith("  "): return "sys"
    return "out"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("--from", dest="frm", default="")
    a = ap.parse_args()
    lines = open(a.raw, encoding="utf-8").read().splitlines()
    if a.frm:
        for i, l in enumerate(lines):
            if re.search(a.frm, l): lines = lines[i:]; break
    out = []; blank = 0
    for l in lines:
        if BOX.match(l) or NOISE.search(l): continue
        if not l.strip():
            blank += 1
            if blank == 1 and out: out.append({"t":"gap"})
            continue
        blank = 0
        t = guess(l); s = l.rstrip()
        if t == "user": s = "> " + re.sub(r"^\s*[❯>]\s*", "", s)
        if t == "ret": out.append({"t":"ret"}); continue
        out.append({"t":t, "s":s})
    while out and out[-1].get("t") == "gap": out.pop()
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
