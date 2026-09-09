---
name: cli-clip
description: Claude Code などCLIツールの「使い方」を1操作1本・1〜2分（最長5分）の解説動画にする。構成はタイトル→説明スライド→デモで固定。実機セッションを tmux で裏で回して実録を取り、清書した擬似ターミナル＋VOICEVOX ナレーション（3声から選択）＋whisper 同期字幕を自動生成して mp4 化する。操作とデモ題材が決まったら使う。環境は cli-clip-setup で固定（macOS / WSL Ubuntu）。
---

<!-- Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT -->
# cli-clip ─ CLI の使い方解説クリップの作り方（AI向け作業手順）

**対象**: Claude Code をはじめとする CLI ツールの「この操作は何をするか」を、**1操作＝1本＝基本1〜2分・最長5分**で見せる短尺動画。
**構成は固定**: `タイトル（番号＋操作名）→ 説明スライド（できることを一文＋補足）→ デモ（実録の清書）で完結`。エンディング・BGM・キャラ掛け合いは付けない。
**語り口は固定**: 講師スタイルの **ですます調**・断定を避ける・**開発用語を使わない**（§4.1〜4.2）。視聴者は開発者とは限らない。
**環境は固定**（`cli-clip-setup`）: 音声＝VOICEVOX、字幕同期＝whisper.cpp、録画＝Playwright/Chromium、合成＝ffmpeg、実機操作＝tmux。LLM 以外すべて無料・ローカル。

| 役割 | 誰が | 成果物 |
|---|---|---|
| 操作の選定・デモ題材・声の選択・OK出し | **人（会話で決める。選択肢ボタンにしない）** | 台本テキストの承認 |
| 実録・台本・画面清書・ビルド・検証 | **AI（本スキル）** | `clips/<id>/clip.json` → `clips/<id>/build/<voice>/<id>_<tag>_<話者>.mp4` |

## 0. ファイルマップ（スキルは自己完結。外部資産に依存しない。チャンネル名・シリーズ名は config/theme.json だけで差し替わる）

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
  templates/clip_frame.html     … 1920x1080 フレーム（擬似端末／説明スライド .slide／右パネル／フル字幕／タイトルカード）
  templates/clip.example.json   … 台本の雛形（構成・行タイプ・パネル・ですます調のセリフ例）
  templates/research.example.md … 題材メモの雛形（Phase 0 の調査結果＋あらすじ）
  config/theme.json             … チャンネル名・シリーズ名・配色・フォント・ラウドネス
  config/voices.json            … ナレーター候補（kurono=玄野武宏／no7=No.7アナウンス／metan=四国めたん）
  config/readings.tsv           … 読み辞書（TTS直前にのみ適用。字幕は原文のまま）
  config/terms.tsv              … 用語の平易化辞書（避ける語→言い換え。lint が警告）
  config/persona.md             … 想定視聴者（Claude Code 初心者・開発者とは限らない）。ブラインドレビューはこの目で見る
  config/review-checklist.md    … セルフレビューの観点（A: あらすじ／B: 台本）＋人の指摘の蓄積（C）
  config/env.json               … setup が生成（gitignore）。review_copy_dir もここ
  docs/catalog-claude-code.md   … Claude Code 基本操作の一覧と状態（題材の正本）
  docs/ideas-claude-code.md     … ネタ帳（初心者の質問リスト。まとめて調査して貯める）
clips/<id>/clip.json            … 各回の正本（作業リポジトリ側。例: clips/op01-esc/）
clips/<id>/research.md          … 題材メモ（調査＋あらすじ＋レビューの取り込み）
clips/<id>/capture/{steps.txt, raw/, transcript.md}
clips/<id>/build/<voice>/       … 中間物・完成mp4（gitignore）
```

## 1. 全体フロー（1本あたり半日〜1日）

```
Phase 0  操作・題材・声を決める（人と会話）→ AI が調査（§2.1）→ research.md に題材メモ＋あらすじ
         → あらすじのブラインドレビュー1回（§2.2）→ 取り込み → docs/catalog に行を追加/更新
Phase 1  実録（バックグラウンド）: make_practice_dir → steps.txt → capture_session.sh → raw/ → transcript.md
Phase 2  clip.json（台本＋画面清書＋パネル）→ --lint → 台本のブラインドレビュー1回（§4.5）→ 取り込み
         → 人のテキストレビュー（映像化前が最安）
Phase 3  build_clip.py（3声 or 1声）→ report.txt（誤読チェック含む）/ preview/*.png を AI が検証
Phase 4  人の動画レビュー → 指摘は「カットid＋内容」→ --only で該当カットだけ再ビルド → 指摘を checklist C に蓄積
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
6. 意味づけカット（d4）の要否（§4.3 の判断基準。基本は付けない）

### 2.1 題材の調査（AI。操作が決まったら、実録の前に）
目的は「どんな説明とデモが初心者に効くか」の当たりを付け、Phase 1・2 の精度を上げること。調べる先は固定:
1. **公式ドキュメント**と **changelog**（一次情報。バージョンと確認日を控える）
2. 初心者の質問・つまずき投稿（Zenn／X／Q&A）を **2〜3件まで**。要約して残す（引用しない）
3. `docs/ideas-claude-code.md`（ネタ帳）に該当操作の行があればそれを起点にする
- 成果物は `clips/<id>/research.md`（雛形 `templates/research.example.md`）: 公式の一言／つまずき／バージョン依存／デモ候補3つ／あらすじ。
- 調査は当たりを付けるためのもの。**実録と食い違ったら実録が正**（直すのは台本）。時間は目安 15〜30 分。深追いしない。
- ネタ出しは1本ずつでなく、カタログの操作ぶんをまとめて調べて `docs/ideas-claude-code.md` に貯めるほうが効率がよい。題材選びはそのリストの「困っている人が多い順」に拾う。

### 2.2 あらすじのブラインドレビュー（AI。実録の前に1回）
- research.md の「あらすじ」（1行 WIN／知らないとどう困るか／状況→操作→結果／持ち帰り／採用デモ）を審査する。
- レビュアーは**別のサブエージェント**。渡すのは `config/persona.md`・`config/review-checklist.md` の A と C・あらすじ本文だけ。台本を書く側の文脈や会話履歴は渡さない（ブラインド）。
- レビュアーはペルソナ（Claude Code 初心者・開発者とは限らない）になりきり、観点は**わかりやすさ・伝わりやすさ**。指摘は `[項目] 観点 → 指摘 → 直し方の案` で。
- レビューは **1回**。指摘を research.md §6 に記録して取り込み、必要なら人に一言報告してから Phase 1 へ。2回以上回さない（磨きすぎると尺と素直さを失う）。

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
{ "meta": { "id","series","no","op","version","capture_source", "voices":"all"(任意), "max_sec":130(任意), "terms_ok":[…](任意) },
  "readings": { "語":"よみ" },                      // この回だけの読み辞書（字幕は原文のまま）
  "cuts": [
    { "id":"t0","type":"card","kind":"title","fixed_ms":2200 },                       // 番号＋操作名だけ
    { "id":"x1","type":"demo","left_html":"<div class=\"slide\"><h2>…</h2><div class=\"lead\">…</div><ul class=\"pts\">…</ul><div class=\"ver\">…</div></div>",   // 説明スライド（§4.4）
      "cap":"…","prompt":"…","note":"…","badge":"14字以内","text":"…では、実際にやってみましょう。","S":[{"t":"beat","talk":true}] },
    { "id":"d1","type":"demo","cap":"…","prompt":"…","note":"…","badge":"…","text":"…","tail_ms":400,
      "S":[ {"t":"cmd","s":"claude"}, {"t":"user","s":"> …"}, {"t":"beat","talk":true,"dur":900}, {"t":"out","s":"⏺ …"}, {"t":"beat"} ] }
  ] }
```
- 行タイプ: `cmd`(＄) `user`(> 入力・タイピング演出) `out`(⏺) `sys`(薄字) `pm`(確認・黄) `menusel` `add/del`(diff) `warn` `code` `gap` `ret`(❯ 待機) `clear` `esc`／`key`(`"s":"Shift+Tab"`) `beat`。
  最初の `beat` までは即描画、以降はタイピング演出。`beat` の `dur` で声を止めずに画面ステップを挟み、最後は `dur` 無しの `beat` で音声尺まで待つ。
- 説明スライドは `left_html` に `.slide` 標準形（§4.4）。図解が要る回だけ `.flow/.fbox/.tbl/.codev/.mdpage/.b4a/.tip/.shot`（`{{CLIP}}`＝この clip のフォルダ、`{{SKILL}}`＝スキルフォルダの絶対パスに置換。画像は `<img class="shot" src="file://{{CLIP}}/…png">`）。
- **台本ルール**（詳細は §4.1〜4.4）: 1人語り・ですます調・二人称なし・断定を避ける・開発用語を使わない・状況→操作→結果・限界は正直に一言・数字や固有の主張を足さない・最後のカットは `tail_ms` 1000〜1200 でそのまま終わる。
- `python3 $S/build_clip.py clips/<id>/clip.json --lint` で構成（先頭=タイトル、2番目=説明スライド）・二人称・断定・文体（ですます調）・専門用語・バッジ14字・尺見込みを検査。二人称と断定はビルド停止、文体と用語は警告（直してから人に見せる）。
- **人のテキストレビュー**が Phase 2 の出口。

### 4.1 ナレーションのスタイル（講師スタイル・ですます調）
- 文体は **ですます調**。講師が受講者に話す口調（「〜します」「〜です」「〜してみましょう」）。だ・である調、体言止めの連続、「〜だ。」で切る書き方は使わない。
- **断定を避ける**。挙動はバージョンで変わるので「〜ことが多いです」「〜ようです」「〜はずです」。「必ず／絶対／決して」は lint で止まる。
- **二人称を使わない**（あなた・君）。呼びかけは「〜してみましょう」で代える。
- 1文は短く（目安 30〜40字）。読点を演出目的で足さない。TTS はセリフの句読点をそのまま読む。
- 順序は **状況 → 操作 → 結果**。意味づけは1文まで。限界や注意点は正直に一言。数字や固有の主張（「○倍速い」等）を足さない。比喩や励まし（「ブレーキと同じ」等）は入れない。
- 説明スライドの締めは「では、実際にやってみましょう。」で固定（デモへの橋渡し）。
- 例: ×「Escは、動き出したAIをその場で止めるキー。」 ○「Escキーは、動き出したAIをその場で止めるキーです。」

### 4.2 用語の平易化（説明スライド・ナレーション・右パネル共通）
視聴者は開発者とは限らない。**開発系の専門用語を使わず、日常の言葉に言い換える**。端末の行（S）は実録の原文ママなので対象外。

| 避ける | 言い換え |
|---|---|
| コンテキスト | 会話の蓄積／これまでのやりとり |
| プロンプトキャッシュ | （仕組み名を出さず）使用量がほぼかからない |
| subagent／サブエージェント | 別の作業／裏で動く別の担当 |
| トークン | 使用量／文字量 |
| プロンプト | 指示／頼み方 |
| セッション | 会話 |
| リポジトリ／ディレクトリ | プロジェクトのフォルダ／フォルダ |
| ターミナル／CLI | 黒い画面／コマンドで動かすツール（初出は「ターミナル（黒い画面）」でも可） |
| diff／コミット | 変更点／保存の区切り |
| パーミッション | 確認／許可 |

- 辞書は `config/terms.tsv`（追加はここ）。lint は `text／cap／prompt／note／badge／left_html` に含まれる語を警告する。
- 操作名そのもの（`/compact`・`/context` 等）は画面に出る語なので、初出で一言添えて使う（「/context は、これまでの会話の蓄積を見るコマンドです」）。その回に限って使ってよい語は `meta.terms_ok` に書く。

### 4.3 カット構成（基本形と意味づけカットの判断基準）
```
t0  タイトルカード（無声 2.2s）: 番号＋操作名だけ
x1  説明スライド（8〜12s）: できることを一文＋補足2つまで＋収録バージョン。締めは「では、実際にやってみましょう。」
d1  状況: 何を頼み、何が起きるか
d2  操作: キー／コマンド＋実録の反応（見せ場。原文ママ）
d3  結果: 何が残り、何が変わっていないか。**ここでそのまま終わる**のが基本形
（d4 意味づけ: デモで見せ切れなかったことを一言で補うときだけ）
```
- 基本形は **タイトル → 説明スライド → デモで完結**。d3 の結果画面で伝わっているなら d4 は付けない。
- d4 を付ける判断基準（どちらかに当てはまるときだけ）: ①結果画面だけでは「何が変わっていないか」「次に何をすればよいか」が伝わらない ②限界・注意点を正直に一言添える必要がある。
- d4 を付けても新しい画面は出さない（d3 と同じ画面のまま、1〜2文で終える）。
- 尺が2分を超えるなら、説明スライドを増やさず操作を分割する。

### 4.4 説明スライド（x1）の標準形
- 構成は **見出し（操作名＋一言）→ 一文（できること）→ 補足2つまで → 収録バージョン**。囲み・番号・矢印・アイコン・表は使わない（開発者向けの資料に見せない）。
- 文字は大きく少なく。一文は 30 字以内、補足は各 25 字以内。用語は §4.2 に従う。
- CSS は `.slide`（`.lead` `.pts` `.ver`、見出しの副題は `<span class="acc">`）。`.flow/.fbox/.tbl` は概要回や比較図にだけ使う。
- 右パネル: cap「この操作でできること」、prompt に一言、note はスライドの補足と同じ語で、badge 14字以内。雛形は `templates/clip.example.json` の x1。

### 4.5 台本のブラインドレビュー（AI。lint 通過後・人に見せる前に1回）
- 対象は `clips/<id>/clip.json` 全体（ナレーション・説明スライド・右パネル・S の行）と `capture/transcript.md`。
- レビュアーは §2.2 と同じく**別のサブエージェント**に、`config/persona.md`・`config/review-checklist.md` の B と C・clip.json・transcript.md だけを渡す。書いた側の文脈は渡さない。
- 観点は checklist B（説明スライドの量、ですます調、用語、d1 で頼んだ内容を言う、見せ場の対応、d3 で次の一手、S が原文ママ、尺、終わり方）。
- レビューは **1回**。指摘を取り込んで `--lint` を再実行し、それから人のテキストレビューに出す。人には「ブラインドレビューで直した点」を1〜3行添える。

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
- **誤読チェック**: `report.txt` 末尾の `reading:` に、各カットの音声を whisper で聞き戻した文と原文が並ぶ。`要確認`（類似度 0.55 未満）は原文と聞取を読み比べ、TTS の誤読なら `readings` に追加して `--only <id> --force` で作り直す。whisper は base モデルなので漢字がカナになる・助詞が落ちるのは正常。似た音の別語（例: 依頼→以来）は聞取側の誤りで、音声は正しいことが多い。
- `config/env.json` の `review_copy_dir` があれば完成 mp4 を `<dir>/<id>/` にコピーし md5 を照合する（`--no-copy` で抑止）。

## 6. Phase 4–5 ─ レビューと公開
- 指摘は「カットid＋内容」で受け、`--only` で当該カットだけ再ビルド（全体は毎回再結合される）。
- **指摘の蓄積**: 人の指摘のうち次回にも効くものは `config/review-checklist.md` の C に1行追記する（`- 日付 <id> <カット>: 要点 → 次回から見る観点`）。次回のブラインドレビューは A／B に加えて C を必ず見る。回を重ねるほどセルフレビューが人の目に近づく。
- 公開パッケージ `clips/<id>/publish.md`: タイトル候補・概要欄（**収録バージョン／VOICEVOX:<話者名>／免責**）・タグ。動画内にクレジットは出ないので概要欄が必須。
- 公開後 `docs/catalog-claude-code.md` の状態欄を更新。

## 7. 必ず守ること
1. 実録の清書＝捏造しない（UI 文言は原文ママ。パスの短縮は transcript.md に注記）。
2. TTS セリフは原文句読点のまま。誤読は `readings`（英字・スラッシュコマンドは辞書に必ず）。
3. 構成はタイトル→説明スライド→デモで完結（意味づけカットは §4.3 の基準に当てはまるときだけ）。エンディング・BGM・キャラなし。
4. 音声 aac/48kHz/2ch、最終 I=theme.loudness_lufs。カットは映像＋音声を同尺で1クリップ化し PCM で連結。
5. 静止末尾はノミナル尺でトリム（beat後に見せ場があるカットは `"static_end": false`）。
6. 右パネルのバッジ14字以内・字幕26字チャンク。
7. 依存は `cli-clip-setup` で固定。`python3 scripts/env.py` が READY でなければビルドしない。
8. ナレーションは講師スタイルのですます調・断定を避ける・開発用語を使わない（§4.1〜4.2）。
9. ブラインドレビューはあらすじ（§2.2）と台本（§4.5）で各1回。レビュアーには persona・checklist・対象物だけを渡す。人に見せる前に取り込む。
