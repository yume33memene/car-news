5) README（セットアップ手順）
前提

Discordアカウント・サーバーを持っていること

GitHubアカウントを持っていること

手順（ざっくり）

Discordで通知先チャンネルを作り、Webhook を作成して URL をコピーする。

新規 GitHub リポジトリを作成し、上記ファイル群をコミットする（toyota_news_discord.py, .github/workflows/run.yml, sent_ids.json を含む）。

GitHub リポジトリの Settings → Secrets に DISCORD_WEBHOOK を追加（Webhook URL）

Actions → Run workflow（workflow_dispatch）で手動実行して動作確認。

正常に投稿されれば、スケジュールで毎時実行されます。

注意点

著作権: 記事の全文を転載しない。見出し＋リンク＋短い要約で運用してください。見出しとリンクだけなら概ね問題になりにくいです。

スクレイピング規約: 利用するサイトの robots.txt や利用規約を遵守してください。

既読管理: sent_ids.json をコミットで管理しています。初回は空の [] を置いてください。
