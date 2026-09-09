# cli-clip

Claude Code などの **CLI ツールの使い方**を、1操作1本・1〜2分（最長5分）の解説動画にする Claude Code スキル。
構成は「タイトル → 説明スライド → デモ」固定。実機セッションを tmux で裏で回して実録を取り、清書した擬似ターミナル＋
VOICEVOX ナレーション（3声から選択）＋ whisper 同期字幕を自動生成して mp4 にする。**LLM 以外すべて無料・ローカル**。

| スキル | 役割 |
|---|---|
| `skills/cli-clip/` | 動画を1本作る手順とツール一式（自己完結） |
| `skills/cli-clip-setup/` | 実行環境を固定バージョンで整える（macOS arm64 / WSL Ubuntu x64） |

## はじめかた
```bash
bash skills/cli-clip-setup/scripts/setup.sh install   # 依存の導入（VOICEVOX / whisper.cpp / Playwright / ffmpeg / tmux）
bash skills/cli-clip-setup/scripts/setup.sh link      # ~/.claude/skills に登録（/cli-clip で呼べる）
python3 skills/cli-clip/scripts/build_clip.py clips/op01-esc/clip.json --voices kurono   # サンプルをビルド
```
このリポジトリ内で `claude` を起動すると `.claude/skills/` 経由で両スキルがそのまま使える。

## 構成
- `clips/<id>/clip.json` … 各回の正本（台本・画面ステップ・パネル文言）。例: `op01-esc`（Esc で止める）、`skill-overview`（本スキルの概要）
- `clips/<id>/capture/` … 実録（steps.txt / raw / transcript.md）
- `clips/<id>/build/<voice>/` … 中間物と完成 mp4（gitignore）
- `skills/cli-clip/docs/catalog-claude-code.md` … Claude Code 基本操作の題材一覧

## 環境
音声 VOICEVOX ENGINE 0.25.2 ／ 字幕同期 whisper.cpp（ggml-base）／ 録画 Playwright 1.61.1 + Chromium ／ 合成 ffmpeg ／ 実機操作 tmux。
導入先は `~/.local/opt/cli-clip/`。パスは `skills/cli-clip/config/env.json` に固定される。

---
<sub>Copyright (c) 2026 Tsuyoshi Hemmi — 現時点では社内利用（LICENSE.md）</sub>
