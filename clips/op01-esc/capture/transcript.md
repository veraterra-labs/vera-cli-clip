<!-- Copyright (c) 2026 Tsuyoshi Hemmi / License: CC BY-NC-SA 4.0 -->
# cli-clip #01 Esc で止める ─ 実録メモ

- **v1 の端末表示の出典**: `scripts/cc02/capture/01-esc/transcript.md`（Claude Code v2.1.207・2026-07-12・tmux実操作）のテイク2を清書。
  raw は `scripts/cc02/capture/01-esc/raw/01_take2_*.txt`。本クリップで新規に撮り直していない（捏造なし・改変なし）。
- clip.json の S に載せた実表示（原文ママ）:
  - `⏺ フォルダの中身を確認しますね。` / `Listed 1 directory` / `⏺ 中身のあるファイルを軽く確認します。` / `Read 3 files`
  - Esc 後: `⎿  Interrupted · What should Claude do instead?` → 入力プロンプト `❯` に戻る
  - 言い直し: `画像ファイルだけ、「画像」フォルダにまとめて。ほかは触らないで`（この後は確認プロンプト→承認→画像5件のみ移動。クリップでは映さない）
- `✻ … (20s · thinking)` は raw の `· Nesting… (18s · ↓ 429 tokens)` 相当のスピナー行を cc02 と同じ簡略表記にしたもの（cc02 v5 で承認済みの表現）。
- 台本との整合: 「Escを一回→その場で止まる→次の指示を待つ」「ファイルは変わっていない」「読んだ内容は会話に残る」は実挙動どおり。

## 再収録するとき
`capture/steps.txt` を `skills/cli-clip/scripts/capture_session.sh` に渡す（練習フォルダは `make_practice_dir.sh` で生成）。
バージョンが変わったら `meta.version` と本ファイルを更新し、UI文言の差異があれば台本側を直す。

<sub>Copyright (c) 2026 Tsuyoshi Hemmi / License: CC BY-NC-SA 4.0</sub>
