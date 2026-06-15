# news-digest

毎朝9:00 JST に AI・IT・PC/スマホツールの最新情報を自動収集・要約して配信する GitHub Pages サイト。

**公開URL**: https://liuxi4048-crypto.github.io/news-digest/

## 仕組み

1. Claude Code `/schedule` がクラウドで毎日9:00 JST に実行
2. WebSearch で AI・IT・スマホツールのニュースを収集
3. Claude が3〜5行の日本語要約を生成
4. GitHub REST API で `index.html` を更新・デプロイ
5. 前日分は `archive/YYYY-MM-DD.html` に保存

## セキュリティ

- GitHub PAT は Fine-grained（Contents:Write のみ・90日ローテーション）
- HTML は push 前にサニタイズ済み（XSS対策）
- CSP ヘッダで `script-src 'none'` を設定

## 免責事項

本サイトのニュース要約は AI（Claude, Anthropic Inc.）が自動生成したものです。
著作権は各メディア・原著作者に帰属します。情報提供目的のみ。
