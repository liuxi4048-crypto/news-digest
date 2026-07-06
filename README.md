# news-digest

海外サイトから収集した最新のAI情報（メイン）・SaaS/ツール・IT全般の情報を、
**3つ以上の独立ソースで照合**したうえで日本語に翻訳・要約し、
毎朝 8:00 JST に自動配信する GitHub Pages サイト。

**公開URL**: https://liuxi4048-crypto.github.io/news-digest/

## 仕組み

1. Claude Code のクラウドルーチンが毎朝 8:00 JST に [prompts/daily_digest.md](prompts/daily_digest.md) を実行
2. 海外サイトのRSSフィード（TechCrunch AI / VentureBeat AI / The Verge AI / Ars Technica / MIT Tech Review / OpenAI・Anthropic・DeepMind 公式 ほか）を直接取得
3. 話題単位にクラスタリングし、`data/published_topics.json` の掲載履歴（直近60日）と照合して重複を排除
4. 各トピックを WebSearch で追加照合し、**独立した3ドメイン以上**で確認できたものだけ採用
5. Claude が自然な日本語で翻訳・要約（毎日10件以上、うちAI 6件以上）
6. GitHub に push して自動デプロイ

## 出力（毎日リセットせず無期限保存）

| パス | 内容 |
|---|---|
| `index.html` | 最新日のダイジェスト + 全アーカイブへのリンク |
| `digests/YYYY-MM-DD.md` | 正のMarkdown版（毎日追加） |
| `archive/YYYY-MM-DD.html` | HTML版アーカイブ（毎日追加） |
| `data/published_topics.json` | 掲載履歴（重複排除用） |

各トピックには照合に使った全ソースURL（3件以上）を記載し、
ページ末尾に当日巡回した全サイトの一覧（採用に至らなかったものも含む）を掲載します。

## ポリシー

- 情報源は海外サイトのみ（日本語訳はClaudeが実施）
- 課金API（ニュースAPI・翻訳API等）は不使用。RSS + WebSearch のみ
- GitHub PAT は Fine-grained（Contents:Write のみ）
- HTML は push 前にサニタイズ済み（XSS対策）、CSP で `script-src 'none'`

## 免責事項

本サイトのニュース要約は AI（Claude, Anthropic Inc.）が自動生成したものです。
著作権は各メディア・原著作者に帰属します。情報提供目的のみ。
