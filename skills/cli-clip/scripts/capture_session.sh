#!/usr/bin/env bash
# Copyright (c) 2026 Tsuyoshi Hemmi / License: CC BY-NC-SA 4.0
# cli-clip 実機キャプチャ（macOS / WSL Ubuntu 共通・tmux）：tmux 上で本物の Claude Code を起動し、steps ファイルどおりに操作して
# 画面（pane）を raw/NN_label.txt にスナップショット保存する。＝バックグラウンドで「実録」を取る。
#
# 使い方: capture_session.sh <workdir(練習フォルダ)> <steps.txt> <rawdir> [session名]
# steps.txt（1行1命令。# はコメント）:
#   type <text>              文字列を入力（Enterは送らない）
#   enter                    Enter
#   key <tmuxキー名>          Escape / Tab / BTab(Shift+Tab) / Down / Up / C-c など
#   wait <sec>               秒待つ（小数可）
#   waitfor <regex> [sec]    pane に regex が現れるまで待つ（既定 90s）。現れなければ WARN を記録して続行
#   snap <label>             pane を rawdir/NN_label.txt に保存（-J で折返し結合・スクロールバック200行込み）
#   trust                    新規フォルダの信頼確認（"Is this a project you created or one you trust?"）が出ていれば
#                            「Yes, I trust this folder」を選んで Enter（既定選択は "No, exit" なので Enter だけだと終了する）。
#                            出ていなければ何もしない。その後 ❯ の入力プロンプトを待つ
#   say <comment>            session.log に記録するだけ
# 終了時に /exit を送ってセッションを閉じる。実行ログ＝ rawdir/session.log（各命令の時刻）。
#
# 注意:
#  - 練習フォルダは隔離（make_practice_dir.sh で生成）。実ファイル・リポジトリでは絶対に走らせない。
#  - 新規フォルダの初回起動は信頼確認ダイアログが出る → steps 冒頭に `trust` を書く（サンプル steps 参照）。
#  - Claude Code 内から起動すると CLAUDECODE 環境変数で入れ子起動が拒否されるため env -u で外す。
#  - 起動オプションは環境変数 CLAUDE_ARGS で渡す（例: CLAUDE_ARGS="--permission-mode default" ＝確認プロンプトを見せる回）。
#    入れ子起動はユーザー設定（auto mode 等）を継承するので、見せたい挙動に合わせて明示する。
set -u
WORK="$1"; STEPS="$2"; RAW="$3"; S="${4:-ccop}"
mkdir -p "$RAW"; LOG="$RAW/session.log"; N=0
ts(){ date +%H:%M:%S.%N | cut -c1-12; }
log(){ echo "$(ts) $*" | tee -a "$LOG"; }
pane(){ tmux capture-pane -t "$S" -p -J -S -200 2>/dev/null; }

tmux kill-session -t "$S" 2>/dev/null
tmux new-session -d -s "$S" -x 180 -y 45 -c "$WORK" "env -u CLAUDECODE claude ${CLAUDE_ARGS:-}"
log "start session=$S work=$WORK"

while IFS= read -r line || [ -n "$line" ]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  cmd="${line%% *}"; arg="${line#* }"; [ "$cmd" = "$line" ] && arg=""
  case "$cmd" in
    type)    tmux send-keys -t "$S" -l -- "$arg"; sleep 0.4; log "type: $arg" ;;
    enter)   tmux send-keys -t "$S" Enter; log "enter" ;;
    key)     tmux send-keys -t "$S" "$arg"; log "key: $arg" ;;
    wait)    sleep "$arg"; log "wait $arg" ;;
    waitfor) re="${arg% *}"; to="${arg##* }"; [ "$re" = "$to" ] && to=90
             t0=$(date +%s); ok=0
             while [ $(( $(date +%s) - t0 )) -lt "$to" ]; do
               if pane | grep -Eq -- "$re"; then ok=1; break; fi; sleep 0.5; done
             [ $ok = 1 ] && log "waitfor ok: $re" || log "WARN waitfor timeout(${to}s): $re" ;;
    snap)    N=$((N+1)); f="$RAW/$(printf '%02d' $N)_${arg}.txt"; pane > "$f"; log "snap -> $(basename "$f")" ;;
    trust)   t0=$(date +%s); st="none"
             while [ $(( $(date +%s) - t0 )) -lt 40 ]; do
               if pane | grep -q "trust this folder"; then st="dialog"; break; fi
               if pane | grep -Eq "^\s*❯(\s*$|\s+Try )"; then st="prompt"; break; fi; sleep 0.5; done
             if [ "$st" = "dialog" ]; then
               tmux send-keys -t "$S" Down; sleep 0.3; tmux send-keys -t "$S" Enter; log "trust: dialog -> Yes"
               t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 40 ]; do pane | grep -Eq "^\s*❯(\s*$|\s+Try )" && break; sleep 0.5; done
             else log "trust: $st (no dialog)"; fi ;;
    say)     log "say: $arg" ;;
    *)       log "WARN unknown: $line" ;;
  esac
done < "$STEPS"

sleep 0.5; tmux send-keys -t "$S" -l -- "/exit"; sleep 0.3; tmux send-keys -t "$S" Enter; sleep 2
tmux kill-session -t "$S" 2>/dev/null
log "end (snaps=$N)"
