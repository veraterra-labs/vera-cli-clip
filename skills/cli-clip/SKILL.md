---
name: cli-clip
description: Claude Code などCLIツールの「使い方」を1操作1本・1〜2分（最長5分）の解説動画にする。構成はタイトル→説明スライド→デモで固定。実機セッションを tmux で裏で回して実録を取り、清書した擬似ターミナル＋VOICEVOX ナレーション（3声から選択）＋whisper 同期字幕を自動生成して mp4 化する。操作とデモ題材が決まったら使う。環境は cli-clip-setup で固定（macOS / WSL Ubuntu）。
---

<!-- Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT -->
# cli-clip ─ CLI の使い方解説クリップの作り方（AI向け作業手順）

**対象**: Claude Code をはじめとする CLI ツールの「この操作は何をするか」を、**1操作＝1本＝基本1〜2分・最長5分**で見せる短尺動画。
**構成は固定**: `タイトル（番号＋操作名）→ 説明スライド（何が起きるか3点）→ デモ（実録の清書）`。エンディング・BGM・キャラ掛け合いは付けない。
**環境は固定**（`cli-clip-setup`）: 音声＝VOICEVOX、字幕同期＝whisper.cpp、録画＝Playwright/Chromium、合成＝ffmpeg、実機操作＝tmux。LLM 以外すべて無料・ローカル。

| 役割 | 誰が | 成果物 |
|---|---|---|
| 操作の選定・デモ題材・声の選択・OK出し | **人（会話で決める。選択肢ボタンにしない）** | 台本テキストの承認 |
| 実録・台本・画面清書・ビルド・検証 | **AI（本スキル）** | `clips/<id>/clip.json` → `clips/<id>/build/<voice>/<id>_<tag>_<話者>.mp4` |

## 0. ファイルマップ（スキルは自己完結。kirin-ai-lab 等の外部資産に依存しない）

```
skills/cli-clip/
  SKILL.md                      … 本書
  scripts/build_clip.py         … clip.json → TTS → whisper同期 → 録画 → mux → 連結 → ラウドネス → preview/report →（設定時）レビュー用コピー
  scripts/capture_session.sh    … tmux で本物の CLI を操作し pane を raw/NN_*.txt に保存（実録。macOS/WSL 共通）
  scripts/make_practice_dir.sh  … 隔離した練習フォルダ（散らかったダミー19ファイル・TODO.md・会議メモ.txt）
  scripts/raw2lines.py          … raw → 画面ステップ S の下書き（抽出のみ。確定は人）
  scripts/tts_voicevox.py       … VOICEVOX（config/voices.json の3声・読み辞書・クレジット）
  scripts/align.py              … whisper.cpp で字幕チャンクを実発話にスナップ（文字起こしではなく時刻合わせ）
  scripts/voice_samples.py      … 声の聞き比べサンプル
  scripts/cap_frame.mjs         … Playwright 録画（node_modules はスキル直下）
  scripts/env.py                … 依存パスの解決（config/env.json > 既定パス > PATH）
  templates/clip_frame.html     … 1920x1080 フレーム（擬似端末／説明スライド／右パネル／フル字幕／タイトルカード）
  templates/clip.example.json   … 台本の雛形（構成・行タイプ・パネルの書き方）
  config/theme.json             … チャンネル名・シリーズ名・配色・フォント・ラウドネス
  config/voices.json            … ナレーター候補（kurono=玄野武宏／no7=No.7アナウンス／metan=四国めたん）
  config/readings.tsv           … 読み辞書（TTS直前にのみ適用。字幕は原文のまま）
  config/env.json               … setup が生成（gitignore）。review_copy_dir もここ
  docs/catalog-claude-code.md   … Claude Code 基本操作の一覧と状態（題材の正本）
clips/<id>/clip.json            … 各回の正本（作業リポジトリ側。例: clips/op01-esc/）
clips/<id>/capture/{steps.txt, raw/, transcript.md}
clips/<id>/build/<voice>/       … 中間物・完成mp4（gitignore）
```

## 1. 全体フロー（1本あたり半日〜1日）

```
Phase 0  操作・題材・声を決める（人と会話）→ docs/catalog に行を追加/更新
Phase 1  実録（バックグラウンド）: make_practice_dir → steps.txt → capture_session.sh → raw/ → transcript.md
Phase 2  clip.json（台本＋画面清書＋パネル）→ --lint → 人のテキストレビュー（映像化前が最安）
Phase 3  build_clip.py（3声 or 1声）→ report.txt / preview/*.png を AI が検証
Phase 4  人の動画レビュー → 指摘は「カットid＋内容」→ --only で該当カットだけ再ビルド
Phase 5  公開パッケージ（タイトル・概要欄・収録バージョン・VOICEVOX クレジット）→ catalog の状態更新
```

## 2. Phase 0 ─ 会話で決めること
1. 操作（1本1操作。混ぜない。2分を超えるなら操作を割る）
2. デモ題材（練習フォルダで何を頼むか。実データ・実リポジトリは映さない）
3. 見せ場（実録で必ず取る画面状態。例 `Interrupted · What should Claude do instead?`）
4. **声**: 人から指定があればそれを `--voices` に渡す。**指定が無ければ、この場で選択肢を出して聞く**
   （kurono＝玄野武宏／no7＝No.7アナウンス／metan＝四国めたん／all＝3声セット）。`meta.voices` に書けば以後は聞かない。
   build_clip.py 自体も `--voices` 未指定なら同じ選択を端末に出す（非対話実行では終了する）
5. 尺の目安（1〜2分。最長5分。長くなる回は説明スライドを増やさずデモを段階分け）

## 3. Phase 1 ─ 実録（捏造しない）
```bash
S=skills/cli-clip/scripts
P=/tmp/cli-clip-practice/<id>                      # 隔離された練習フォルダ
bash $S/make_practice_dir.sh "$P"
CLAUDE_ARGS="--permission-mode default" bash $S/capture_session.sh "$P" clips/<id>/capture/steps.txt clips/<id>/capture/raw
```
- steps.txt 文法（スクリプト冒頭）: `trust / type / enter / key / wait / waitfor <regex> / snap <label> / say`。**見せ場の直前・直後で必ず `snap`**。
- 新規フォルダ初回は信頼確認が出る → steps 冒頭に `trust`（既定選択が "No, exit" なので Enter だけは不可）。
- 入れ子の claude はユーザー設定（auto mode 等）を継承する。確認プロンプトを見せる回は `CLAUDE_ARGS="--permission-mode default"`。
- 実行後 `raw/` を読んで `transcript.md`（原文ママ抜粋＋台本との整合メモ）。**挙動が想定と違えば直すのは台本**。`claude --version` を `meta.version` に。
- 下書き変換: `python3 $S/raw2lines.py clips/<id>/capture/raw/02_running.txt --from "❯ …"`。最終 S は人が transcript と突き合わせて確定（行の追加・改変は不可。省略は可）。

## 4. Phase 2 ─ clip.json（正本）
`templates/clip.example.json` を雛形に。構造:
```jsonc
{ "meta": { "id","series","no","op","version","capture_source", "voices":"all"(任意), "max_sec":130(任意) },
  "readings": { "語":"よみ" },                      // この回だけの読み辞書（字幕は原文のまま）
  "cuts": [
    { "id":"t0","type":"card","kind":"title","fixed_ms":2200 },                       // 番号＋操作名だけ
    { "id":"x1","type":"demo","left_html":"<h2>…</h2><div class=\"flow\">…</div>",    // 説明スライド（3点＋収録バージョン）
      "cap":"…","prompt":"…","note":"…","badge":"14字以内","text":"…では、実際にやってみよう。","S":[{"t":"beat","talk":true}] },
    { "id":"d1","type":"demo","cap":"…","prompt":"…","note":"…","badge":"…","text":"…","tail_ms":400,
      "S":[ {"t":"cmd","s":"claude"}, {"t":"user","s":"> …"}, {"t":"beat","talk":true,"dur":900}, {"t":"out","s":"⏺ …"}, {"t":"beat"} ] }
  ] }
```
- 行タイプ: `cmd`(＄) `user`(> 入力・タイピング演出) `out`(⏺) `sys`(薄字) `pm`(確認・黄) `menusel` `add/del`(diff) `warn` `code` `gap` `ret`(❯ 待機) `clear` `esc`／`key`(`"s":"Shift+Tab"`) `beat`。
  最初の `beat` までは即描画、以降はタイピング演出。`beat` の `dur` で声を止めずに画面ステップを挟み、最後は `dur` 無しの `beat` で音声尺まで待つ。
- 説明スライドや図は `left_html`（`.flow/.fbox/.tbl/.codev/.mdpage/.b4a/.tip/.shot` のCSS。`{{CLIP}}`＝この clip のフォルダ、`{{SKILL}}`＝スキルフォルダの絶対パスに置換。画像は `<img class="shot" src="file://{{CLIP}}/…png">`）。
- **台本ルール**: 1人語り・二人称なし・断定なし（「〜ことが多い」）・読点を演出目的で足さない・状況→操作→結果→意味づけ・限界は正直に一言・数字や固有の主張を足さない・最後のカットは `tail_ms` 1000〜1200 でそのまま終わる。
- `python3 $S/build_clip.py clips/<id>/clip.json --lint` で構成（先頭=タイトル、2番目=説明スライド）・二人称・断定・バッジ14字・尺見込みを検査。
- **人のテキストレビュー**が Phase 2 の出口。

## 5. Phase 3 ─ ビルドと検証
```bash
python3 $S/build_clip.py clips/<id>/clip.json                   # --voices 未指定 → 声の選択を出す（meta.voices があればそれ）
python3 $S/build_clip.py clips/<id>/clip.json --voices all      # 3声セット
python3 $S/build_clip.py clips/<id>/clip.json --voices kurono   # 1声
python3 $S/build_clip.py clips/<id>/clip.json --only d2         # 指摘カットだけ（全声）
python3 $S/build_clip.py clips/<id>/clip.json --force --tag v2  # 全カット作り直し
```
- セリフを変えたカットは `--only <id> --force`（TTS キャッシュ vox/<id>.wav は内容変更を検知しない）。
- 字幕は既定 whisper 同期。失敗カットは自動で文字数比例（ログ `[align]`）。ずれるなら `--align prop` で比較かセリフを短文に割る。
- **AI の検証（人に見せる前）**: `report.txt` が PASS（尺／aac 48k 2ch／I=±0.3／A/V drift 無し）、`preview/*.png` 全カット目視（字幕収まり・バッジ14字・実表示が原文ママ・キー可視化・説明スライドの折返し）、台本と画面の整合、収録バージョン表示。
- `config/env.json` の `review_copy_dir` があれば完成 mp4 を `<dir>/<id>/` にコピーし md5 を照合する（`--no-copy` で抑止）。

## 6. Phase 4–5 ─ レビューと公開
- 指摘は「カットid＋内容」で受け、`--only` で当該カットだけ再ビルド（全体は毎回再結合される）。
- 公開パッケージ `clips/<id>/publish.md`: タイトル候補・概要欄（**収録バージョン／VOICEVOX:<話者名>／免責**）・タグ。動画内にクレジットは出ないので概要欄が必須。
- 公開後 `docs/catalog-claude-code.md` の状態欄を更新。

## 7. 必ず守ること
1. 実録の清書＝捏造しない（UI 文言は原文ママ。パスの短縮は transcript.md に注記）。
2. TTS セリフは原文句読点のまま。誤読は `readings`（英字・スラッシュコマンドは辞書に必ず）。
3. 構成はタイトル→説明スライド→デモ。エンディング・BGM・キャラなし。
4. 音声 aac/48kHz/2ch、最終 I=theme.loudness_lufs。カットは映像＋音声を同尺で1クリップ化し PCM で連結。
5. 静止末尾はノミナル尺でトリム（beat後に見せ場があるカットは `"static_end": false`）。
6. 右パネルのバッジ14字以内・字幕26字チャンク。
7. 依存は `cli-clip-setup` で固定。`python3 scripts/env.py` が READY でなければビルドしない。
