#!/usr/bin/env bash
# Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
# cli-clip-setup: cli-clip の実行環境を固定バージョンで整える（macOS arm64 / WSL Ubuntu x64）。
#   ./setup.sh check     … 依存の有無を表で出す（何も入れない）
#   ./setup.sh install   … 足りないものを入れる（VOICEVOX ENGINE / whisper.cpp+model / Playwright+Chromium / ffmpeg / tmux / フォント）
#   ./setup.sh link      … ~/.claude/skills に cli-clip と cli-clip-setup のシンボリックリンクを置く（どのプロジェクトからも /cli-clip で呼べる）
#   ./setup.sh env       … 解決したパスを skills/cli-clip/config/env.json に書く（install の最後に自動実行）
# 固定バージョン: VOICEVOX ENGINE 0.25.2 / whisper.cpp（ggml-base）/ Playwright 1.61.1 / Chromium はその同梱版
# 導入先: $CLI_CLIP_HOME（既定 ~/.local/opt/cli-clip）。sudo が要るのは apt（Ubuntu）だけ。
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../../cli-clip" && pwd)"
HOME_DIR="${CLI_CLIP_HOME:-$HOME/.local/opt/cli-clip}"
VV_VER="0.25.2"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) OS=macos; VV_ASSET="voicevox_engine-macos-arm64-${VV_VER}.7z.001";;
  Linux-x86_64) OS=linux; VV_ASSET="voicevox_engine-linux-cpu-x64-${VV_VER}.7z.001";;
  Linux-aarch64) OS=linux; VV_ASSET="voicevox_engine-linux-cpu-arm64-${VV_VER}.7z.001";;
  *) echo "unsupported: $(uname -s)-$(uname -m)（対応: macOS arm64 / Linux(WSL Ubuntu) x64・arm64）"; exit 1;;
esac
CMD="${1:-check}"
say(){ printf '\033[1;36m[setup]\033[0m %s\n' "$*"; }
has(){ command -v "$1" >/dev/null 2>&1; }

pkg_install(){  # 引数: mac用パッケージ名 apt用パッケージ名
  if [ "$OS" = macos ]; then has brew || { echo "Homebrew が必要: https://brew.sh"; exit 1; }; brew list "$1" >/dev/null 2>&1 || brew install "$1"
  else sudo apt-get install -y "$2"; fi
}

do_check(){ python3 "$SKILL/scripts/env.py"; }

do_install(){
  say "OS=$OS  導入先=$HOME_DIR"; mkdir -p "$HOME_DIR"
  [ "$OS" = linux ] && sudo apt-get update -y
  # --- 基本ツール
  has ffmpeg || pkg_install ffmpeg ffmpeg
  has tmux   || pkg_install tmux tmux
  has git    || pkg_install git git
  has python3|| pkg_install python3 python3
  if [ "$OS" = linux ]; then
    sudo apt-get install -y build-essential cmake curl p7zip-full fonts-noto-cjk
    has node || { say "node を導入（NodeSource 22.x）"; curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs; }
  else
    has 7zz  || pkg_install sevenzip sevenzip
    has node || pkg_install node nodejs
    has cmake|| pkg_install cmake cmake
  fi
  # --- Playwright（スキル直下に固定版）＋ Chromium
  say "Playwright"
  ( cd "$SKILL" && npm install --no-audit --no-fund >/dev/null && npx playwright install chromium $( [ "$OS" = linux ] && echo --with-deps ) )
  # --- whisper.cpp（mac は brew、linux はソースビルド）＋ ggml-base モデル
  say "whisper.cpp"
  if [ "$OS" = macos ]; then
    has whisper-cli || pkg_install whisper-cpp whisper-cpp
    WHISPER_CLI="$(command -v whisper-cli)"
  else
    if [ ! -x "$HOME_DIR/whisper.cpp/build/bin/whisper-cli" ]; then
      [ -d "$HOME_DIR/whisper.cpp" ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp "$HOME_DIR/whisper.cpp"
      ( cd "$HOME_DIR/whisper.cpp" && cmake -B build -DCMAKE_BUILD_TYPE=Release >/dev/null && cmake --build build -j --config Release >/dev/null )
    fi
    WHISPER_CLI="$HOME_DIR/whisper.cpp/build/bin/whisper-cli"
  fi
  MODEL_DIR="$HOME_DIR/whisper.cpp/models"; mkdir -p "$MODEL_DIR"
  [ -f "$MODEL_DIR/ggml-base.bin" ] || curl -L -o "$MODEL_DIR/ggml-base.bin" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
  # --- VOICEVOX ENGINE（固定版・CPU）
  say "VOICEVOX ENGINE $VV_VER"
  if [ ! -x "$HOME_DIR/voicevox/engine/run" ]; then
    mkdir -p "$HOME_DIR/voicevox"; cd "$HOME_DIR/voicevox"
    [ -f "$VV_ASSET" ] || curl -L -o "$VV_ASSET" "https://github.com/VOICEVOX/voicevox_engine/releases/download/${VV_VER}/${VV_ASSET}"
    if has 7zz; then 7zz x -y "$VV_ASSET" >/dev/null; else 7z x -y "$VV_ASSET" >/dev/null; fi
    d="$(ls -d */ | grep -v engine | head -1)"; [ -n "$d" ] && mv "${d%/}" engine
    chmod +x engine/run; rm -f "$VV_ASSET"; cd - >/dev/null
  fi
  do_env
  do_check
}

do_env(){
  WHISPER_CLI="${WHISPER_CLI:-$(command -v whisper-cli || echo "$HOME_DIR/whisper.cpp/build/bin/whisper-cli")}"
  REVIEW_DIR="$(python3 -c "import json;print(json.load(open('$SKILL/config/env.json')).get('review_copy_dir',''))" 2>/dev/null || true)"
  MODEL="$HOME_DIR/whisper.cpp/models/ggml-base.bin"; [ -f "$MODEL" ] || [ ! -f "$HOME/.cache/whisper-cpp/ggml-base.bin" ] || MODEL="$HOME/.cache/whisper-cpp/ggml-base.bin"
  cat > "$SKILL/config/env.json" <<EOF
{
  "_note": "cli-clip-setup が生成。手で直してよい（review_copy_dir は完成mp4のコピー先。空なら何もしない）",
  "os": "$OS",
  "ffmpeg": "$(command -v ffmpeg || true)",
  "ffprobe": "$(command -v ffprobe || true)",
  "node": "$(command -v node || true)",
  "whisper_cli": "$WHISPER_CLI",
  "whisper_model": "$MODEL",
  "voicevox_run": "$HOME_DIR/voicevox/engine/run",
  "voicevox_host": "http://127.0.0.1:50021",
  "review_copy_dir": "$REVIEW_DIR"
}
EOF
  say "wrote $SKILL/config/env.json"
}

do_link(){
  mkdir -p "$HOME/.claude/skills"
  for s in cli-clip cli-clip-setup; do
    ln -sfn "$(cd "$HERE/../../$s" && pwd)" "$HOME/.claude/skills/$s"; say "linked ~/.claude/skills/$s"
  done
}

case "$CMD" in
  check) do_check;;
  install) do_install;;
  env) do_env; do_check;;
  link) do_link;;
  *) echo "usage: setup.sh check|install|env|link"; exit 1;;
esac
