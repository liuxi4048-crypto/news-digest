# news-digest

海外サイトから収集した最新のAI情報（メイン）・SaaS/ツール・IT全般の情報を、
**3つ以上の独立ドメインで照合**したうえで日本語に翻訳・要約し、
毎朝 8:00 JST に自動配信する GitHub Pages サイト。

PC の状態に関係なく **GitHub Actions** 上で完全自動実行される。

**公開URL**: https://liuxi4048-crypto.github.io/news-digest/

## 仕組み

1. GitHub Actions（[.github/workflows/daily-digest.yml](.github/workflows/daily-digest.yml)）が毎朝 8:00 JST（23:00 UTC）に起動
2. [scripts/generate_digest.py](scripts/generate_digest.py) が海外RSSフィード（TechCrunch AI / VentureBeat AI / The Verge AI / Ars Technica / MIT Tech Review / OpenAI・Anthropic・DeepMind 公式・Hacker News ほか、日本サイトは対象外）を取得
3. タイトルの類似度で記事を話題（トピック）単位にクラスタリングし、**独立した3ドメイン以上**が報じている話題だけを採用（追加の課金APIは使わず、RSS収集そのものをクロスチェックの手段にしている）
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

各トピックには照合に使った全ソースURL（3件以上）を記載し、
ページ末尾に当日巡回した全フィードの一覧（採用に至らなかったもの・取得失敗したものも含む）を掲載します。

## セットアップ

リポジトリの Settings → Secrets and variables → Actions に `GROQ_API_KEY`（[console.groq.com](https://console.groq.com) の無料枠キー）を登録する。
Actions の書き込み権限（Settings → Actions → General → Workflow permissions → Read and write）を有効にする。

## ポリシー

- 情報源は海外サイトのみ
- 課金API（ニュースAPI・翻訳API等）は不使用。RSS + 無料枠LLMのみ
- HTML は push 前にサニタイズ済み（XSS対策: script/on*属性/javascript:URL/iframe等を除去）

## 免責事項

本サイトのニュース要約はAI（Llama 3.3, Meta）が自動生成したものです。
著作権は各メディア・原著作者に帰属します。情報提供目的のみ。
