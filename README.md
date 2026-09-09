# cli-clip

Claude Code などの **CLI ツールの使い方**を、1操作1本・1〜2分（最長5分）の解説動画にする Claude Code スキル。
構成は「タイトル → 説明スライド → デモ」固定。実機セッションを tmux で裏で回して実録を取り、清書した擬似ターミナル＋
VOICEVOX ナレーション（3声から選択）＋ whisper 同期字幕を自動生成して mp4 にする。**LLM（Claude Code 本体）以外はすべて無料・ローカル**。

| スキル | 役割 |
|---|---|
| `skills/cli-clip/` | 動画を1本作る手順とツール一式（自己完結） |
| `skills/cli-clip-setup/` | 実行環境を固定バージョンで整える（macOS arm64 / WSL Ubuntu x64） |

---

## 1. 前提

| 項目 | macOS（Apple Silicon） | WSL Ubuntu（Windows） |
|---|---|---|
| OS | macOS 14 以降・arm64 | Windows 11 の WSL2 ＋ Ubuntu 22.04/24.04（x64） |
| パッケージ管理 | [Homebrew](https://brew.sh) | apt（`sudo` が使えること） |
| Claude Code | 導入済み（`claude --version` が通る） | 同左（WSL の Ubuntu 側に導入） |
| git / python3 | Homebrew で入る | `sudo apt install git python3` |
| ディスク | 約 4GB（VOICEVOX 2GB・Chromium・モデル） | 同左 |
| ネットワーク | GitHub / Hugging Face / npm に到達できること | 同左 |

Windows ネイティブ（PowerShell）は対象外。必ず WSL の Ubuntu 上で動かす。

## 2. インストール

```bash
# 1) 取得
git clone https://github.com/veraterra-labs/vera-cli-clip.git
cd vera-cli-clip

# 2) 現状確認（何も入れない）
bash skills/cli-clip-setup/scripts/setup.sh check

# 3) 導入（足りないものだけ入る。Ubuntu は apt に sudo のパスワードを聞かれる）
bash skills/cli-clip-setup/scripts/setup.sh install

# 4) どのフォルダからも /cli-clip で呼べるように登録（任意）
bash skills/cli-clip-setup/scripts/setup.sh link
```

`install` がやること（固定バージョン）:

| 役割 | 入るもの | 導入先 |
|---|---|---|
| 音声 | VOICEVOX ENGINE 0.25.2（CPU 版、約 1.7GB をダウンロード） | `~/.local/opt/cli-clip/voicevox/engine/` |
| 字幕同期 | whisper.cpp ＋ ggml-base モデル（mac は brew、Ubuntu はソースビルド。数分） | `~/.local/opt/cli-clip/whisper.cpp/` |
| 画面録画 | Playwright 1.61.1 ＋ 同梱 Chromium | `skills/cli-clip/node_modules/` |
| 合成 / 実機操作 | ffmpeg / tmux | brew・apt |
| フォント（Ubuntu） | fonts-noto-cjk | apt |
| node（Ubuntu） | NodeSource 22.x | apt |

最後に `skills/cli-clip/config/env.json` に各パスが書き出され、`check` が再実行される。
`RESULT: READY` と出れば完了。`MISSING` の行があれば、その項目だけ手で入れて `setup.sh env` を実行する。

導入先を変えたい場合は `CLI_CLIP_HOME=/path bash …/setup.sh install`。

## 3. 動作確認（サンプルを1本ビルド）

```bash
# VOICEVOX が未起動なら自動起動する。声を選ぶ番号入力が出る（1〜3 or 4=3声セット）
python3 skills/cli-clip/scripts/build_clip.py clips/op01-esc/clip.json
# 声を決め打ちする場合
python3 skills/cli-clip/scripts/build_clip.py clips/op01-esc/clip.json --voices kurono
```

出力: `clips/op01-esc/build/kurono/op01-esc_v1_玄野武宏.mp4`、各カットの `preview/*.png`、検査結果 `report.txt`（`CHECK: PASS` を確認）。
完成 mp4 を別の場所（iCloud 等）にもコピーしたいときは `skills/cli-clip/config/env.json` の `review_copy_dir` に絶対パスを書く。

## 4. 使い方（Claude Code から）

このリポジトリで `claude` を起動すると `.claude/skills/` 経由で両スキルが使える（`link` 済みならどこからでも）。

- `/cli-clip` … 新しい操作の動画を1本作る。操作・題材・声を会話で決め → 実録 → 台本 → ビルド → レビュー。
- `/cli-clip-setup` … 環境の確認・導入・更新。

手順の詳細は `skills/cli-clip/SKILL.md`、環境まわりは `skills/cli-clip-setup/SKILL.md`。

## 5. 構成

```
skills/cli-clip/
  SKILL.md                 手順（AI向け）
  scripts/                 build_clip.py / capture_session.sh / make_practice_dir.sh / raw2lines.py
                           tts_voicevox.py / align.py / voice_samples.py / cap_frame.mjs / env.py
  templates/               clip_frame.html（画面テンプレ）/ clip.example.json（台本の雛形）
  config/                  theme.json（チャンネル名・配色・フォント）/ voices.json（3声）/ readings.tsv（読み辞書）/ env.json（setup 生成）
  docs/catalog-claude-code.md   Claude Code 基本操作の題材一覧
skills/cli-clip-setup/
  SKILL.md / scripts/setup.sh   check | install | env | link
clips/<id>/
  clip.json                各回の正本（台本・画面ステップ・パネル文言）
  capture/                 実録（steps.txt / raw/ / transcript.md）
  build/<voice>/           中間物と完成 mp4（gitignore）
```

## 6. つまずいたら

- `setup.sh check` で `NG` の項目名を見る。`playwright` なら `cd skills/cli-clip && npm install && npx playwright install chromium`。
- Ubuntu で Chromium が起動しない: `npx playwright install --with-deps chromium`。
- Ubuntu で日本語が豆腐: `sudo apt install fonts-noto-cjk`。
- VOICEVOX が起動しない: `~/.local/opt/cli-clip/voicevox/engine/run --host 127.0.0.1 --port 50021` を直接実行してエラーを見る。ポート衝突なら `env.json` の `voicevox_host` を変更。
- 入れ子の `claude` が拒否される: `capture_session.sh` は `env -u CLAUDECODE` で起動する。`claude --version` が通るか確認。
- そのほかは `skills/cli-clip-setup/SKILL.md` の「つまずきどころ」。

## 7. クレジット・ライセンス

- 動画の概要欄に **「VOICEVOX:<話者名>」** を必ず表記する（玄野武宏／No.7／四国めたん。各キャラの利用規約は https://voicevox.hiroshiba.jp/ ）。
- 本リポジトリは現時点で社内利用（`LICENSE.md`）。外部ソフトウェア（VOICEVOX ENGINE・whisper.cpp・Playwright・ffmpeg）は各々のライセンスに従う。

---
<sub>Copyright (c) 2026 Tsuyoshi Hemmi</sub>
