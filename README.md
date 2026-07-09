# news-digest

海外サイトから収集した最新のAI情報（メイン）・SaaS/ツール・IT全般の情報を、
**独立ドメイン数による照合レベル付き**で日本語に翻訳・要約し、
毎朝 8:00 JST に自動配信する GitHub Pages サイト。

PC の状態に関係なく **GitHub Actions** 上で完全自動実行される。

**公開URL**: https://liuxi4048-crypto.github.io/news-digest/

## 仕組み

1. GitHub Actions（[.github/workflows/daily-digest.yml](.github/workflows/daily-digest.yml)）が毎朝 8:00 JST（23:00 UTC）に起動
2. [scripts/generate_digest.py](scripts/generate_digest.py) が海外RSSフィード（TechCrunch AI / VentureBeat AI / The Verge AI / Ars Technica / MIT Tech Review / OpenAI・Anthropic・DeepMind 公式・Hacker News ほか、日本サイトは対象外）を取得
3. タイトルの類似度（共有トークン + 固有名詞トークン + 当日の希少度）で全フィード横断のトピッククラスタリングを行い、**照合ドメイン数が多い話題から優先採用**。各トピックには照合レベル（3ドメイン以上／2ドメイン／単一ソース）を明記する
4. `data/published_topics.json` の掲載履歴（直近60日）と突き合わせて重複を排除
5. 採用トピック（毎日10件以上、うちAI 6件以上を目標）を無料枠LLM（Groq / Llama 3.3 70B）で日本語に翻訳・要約
6. Markdown・HTML・履歴ファイルを生成し、Actions が自動で git commit & push

## 出力（毎日リセットせず無期限保存）

| パス | 内容 |
|---|---|
| `index.html` | 最新日のダイジェスト + 全アーカイブへのリンク |
| `digests/YYYY-MM-DD.md` | 正のMarkdown版（毎日追加） |
| `archive/YYYY-MM-DD.html` | HTML版アーカイブ（毎日追加） |
| `data/published_topics.json` | 掲載履歴（重複排除用） |

各トピックには照合に使った全ソースURLと照合レベルを記載し、
ページ末尾に当日巡回した全フィードの一覧（採用に至らなかったもの・取得失敗したものも含む）を掲載します。

## セットアップ

リポジトリの Settings → Secrets and variables → Actions に `GROQ_API_KEY`（[console.groq.com](https://console.groq.com) の無料枠キー）を登録する。
Actions の書き込み権限（Settings → Actions → General → Workflow permissions → Read and write）を有効にする。

## スマホ通知（ntfy.sh・無料）

毎朝ダイジェストが公開されると、スマホにプッシュ通知が届き、タップすると公開ページが開く。

1. スマホに [ntfy](https://ntfy.sh/) アプリをインストール（Android: Play ストア / iOS: App Store）
2. 推測されにくいトピック名を1つ決める（例: `news-digest-xn6w1h8bqky5`。ntfy.sh のトピックは知っている人なら誰でも購読できるため、ランダムな文字列を含めること）
3. アプリで「＋」→ Subscribe to topic → 決めたトピック名を入力
4. リポジトリの Settings → Secrets and variables → Actions に `NTFY_TOPIC` という名前でトピック名を登録

`NTFY_TOPIC` が未設定の間は通知ステップは自動的にスキップされる（ダイジェスト生成には影響しない）。
通知はダイジェストに変更があった日のみ送信される。

## ポリシー

- 情報源は海外サイトのみ
- 課金API（ニュースAPI・翻訳API等）は不使用。RSS + 無料枠LLMのみ
- HTML は push 前にサニタイズ済み（XSS対策: script/on*属性/javascript:URL/iframe等を除去）

## 免責事項

本サイトのニュース要約はAI（Llama 3.3, Meta）が自動生成したものです。
著作権は各メディア・原著作者に帰属します。情報提供目的のみ。
