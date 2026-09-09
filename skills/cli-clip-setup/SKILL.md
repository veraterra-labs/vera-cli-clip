---
name: cli-clip-setup
description: cli-clip（CLIツールの使い方解説クリップ生成スキル）の実行環境を固定バージョンで整える。macOS(arm64) と WSL Ubuntu(x64) 対応。VOICEVOX ENGINE・whisper.cpp・Playwright+Chromium・ffmpeg・tmux を ~/.local/opt/cli-clip に導入し、config/env.json にパスを固定する。初回セットアップ・「cli-clip が動かない」「依存を確認して」の時に使う。
---

<!-- Copyright (c) 2026 Tsuyoshi Hemmi -->
# cli-clip-setup ─ 実行環境の固定セットアップ

cli-clip は **LLM（Claude Code 本体）以外すべて無料・ローカル**で動く。このスキルは、その環境を同じバージョンで揃える。

| 役割 | 固定するもの | 版 | 導入先 |
|---|---|---|---|
| 音声 | VOICEVOX ENGINE（CPU） | 0.25.2 | `~/.local/opt/cli-clip/voicevox/engine/run` |
| 字幕同期 | whisper.cpp ＋ ggml-base | mac: brew 最新／linux: ソースビルド | `~/.local/opt/cli-clip/whisper.cpp/` |
| 画面録画 | Playwright ＋ 同梱 Chromium | 1.61.1 | `skills/cli-clip/node_modules/` |
| 合成 | ffmpeg | brew／apt | PATH |
| 実機操作 | tmux ＋ claude | brew／apt | PATH |
| フォント | mac: ヒラギノ／linux: Noto Sans CJK | — | apt `fonts-noto-cjk` |

対応 OS: **macOS arm64** と **WSL Ubuntu x64**（Windows ネイティブは対象外。Windows では WSL 上で動かす）。

## 手順（AI向け）

1. まず現状確認（何も入れない）:
   ```bash
   bash skills/cli-clip-setup/scripts/setup.sh check
   ```
   `RESULT: READY` なら終了。`MISSING` なら 2 へ。
2. 導入（Ubuntu は apt に sudo が要る。ダウンロード合計 ≈ 2.5GB：VOICEVOX 1.7GB・Chromium・モデル 150MB）:
   ```bash
   bash skills/cli-clip-setup/scripts/setup.sh install
   ```
   最後に `config/env.json` を書き、`check` を再実行して READY を確認する。
3. どのプロジェクトからも `/cli-clip` で呼べるようにする（任意）:
   ```bash
   bash skills/cli-clip-setup/scripts/setup.sh link     # ~/.claude/skills/cli-clip{,-setup} にシンボリックリンク
   ```
4. レビュー用コピー先（iCloud 等）を使う場合は `skills/cli-clip/config/env.json` の `review_copy_dir` に絶対パスを書く。

## つまずきどころ
- **VOICEVOX が起動しない（linux）**: `engine/run` に実行権限があるか、`ldd engine/run` で不足ライブラリが無いか。WSL は x64 の CPU 版を使う。
- **Chromium が起動しない（linux）**: `npx playwright install --with-deps chromium` で共有ライブラリを入れる（setup が実行済み。失敗したら再実行）。
- **whisper-cli が無い（linux）**: `build-essential cmake` が入っているか。ビルドは数分かかる。
- **日本語が豆腐（linux）**: `fonts-noto-cjk` が入っているか。`fc-list | grep -i noto` で確認。
- **入れ子の claude が拒否される**: capture_session.sh が `env -u CLAUDECODE` で起動するので通常は出ない。出たら `claude --version` が通るか確認。
- **ポート 50021 が使用中**: 既存の VOICEVOX（アプリ版など）が動いていればそれを使う。`config/env.json` の `voicevox_host` で変更可。

## 再セットアップ・更新
- 版を上げるときは `setup.sh` 冒頭の `VV_VER` と `package.json` の playwright を変えて `install`。
- 依存を消して入れ直す: `rm -rf ~/.local/opt/cli-clip skills/cli-clip/node_modules` → `install`。
