#!/usr/bin/env bash
# Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
# cli-clip 練習フォルダ生成：cc02 実機キャプチャで使った「散らかったダミー19ファイル」相当を隔離ディレクトリに作る。
# 使い方: make_practice_dir.sh <dir>   （既存なら中身を作り直す）
set -eu
D="$1"; rm -rf "$D"; mkdir -p "$D"; cd "$D"
touch "スクリーンショット 2026-07-01 10.15.30.png" "スクリーンショット 2026-07-03 18.02.11.png" IMG_5001.jpg IMG_5002.jpg logo_draft_v2.png
printf '%%PDF-1.4\n%% dummy\n' > "請求書_2026-06.pdf"; printf '%%PDF-1.4\n%% dummy\n' > "契約書_draft.pdf"
: > 売上集計_Q2.xlsx; : > 提案資料_v3.pptx; : > 議事録_0620.docx; : > export_users.csv
printf 'print("hello")\n' > script.py; printf '{"name":"demo","version":1}\n' > config.json
: > backup_0601.zip; : > demo.mp4; : > voice_memo_0703.m4a; : > README
printf 'メモ 7/3: 次回リリースは7月末目標。担当は未定。\n' > "会議メモ.txt"
cat > TODO.md <<'EOF'
# TODO

- [ ] 企画書のドラフトを書く
- [x] 定例MTGの議事録を共有
- [ ] 経費精算（6月分）
- [ ] チームの週次アンケートに回答
- [ ] 新しいツールの調査メモをまとめる
EOF
echo "practice dir ready: $D ($(ls | wc -l | tr -d ' ') files)"
