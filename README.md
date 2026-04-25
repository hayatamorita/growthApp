# 成長記録アプリ

子供の基本情報と成長記録をローカル環境で管理する、Flask + PostgreSQL + Docker Compose の最小アプリです。

## 技術構成

- Python
- Flask
- PostgreSQL 16
- psycopg
- Docker
- Docker Compose
- Flask templates

## ディレクトリ構成

```text
growth-app/
  compose.yml
  .env.example
  .gitignore
  README.md
  app/
    Dockerfile
    requirements.txt
    app.py
    templates/
      base.html
      index.html
      child.html
      add_record.html
```

## 初回セットアップ

必要なもの:

- Docker
- Docker Compose

必要に応じてローカル用の `.env` を作成します。

```sh
cp .env.example .env
```

`.env` は Git に含めません。ローカル専用の値を入れてください。

## 起動方法

初回、または Dockerfile / requirements.txt を変更した後:

```sh
docker compose up --build
```

バックグラウンドで起動する場合:

```sh
docker compose up -d
```

## 停止方法

```sh
docker compose down
```

## DBデータを完全削除する方法

PostgreSQL の named volume も削除する場合:

```sh
docker compose down -v
```

## 画面URL

- トップページ: http://localhost:5002
- 子供詳細ページ: トップページの子供名リンクから移動
- 記録追加ページ: 子供詳細ページの「記録を追加」リンクから移動

## よく使うコマンド

```sh
# ビルドして起動
docker compose up --build

# バックグラウンド起動
docker compose up -d

# 停止
docker compose down

# DBデータも含めて削除
docker compose down -v

# appコンテナのログを見る
docker compose logs -f app

# appコンテナに入る
docker compose exec app sh

# psqlでDBを確認する
docker compose exec db psql -U growth_user -d growth_db
```

## できること

- 子供一覧の表示
- 子供の追加、削除
- 子供ごとの成長記録一覧表示
- 成長記録の追加、削除

## GitHub に含めないもの

- `.env` や `.env.local` などのローカル環境変数ファイル
- 本番DB接続URL、実運用パスワード、実運用の `FLASK_SECRET_KEY`
- Docker volume や PostgreSQL のDBデータ
- Python の `__pycache__/`、`.venv/`
- ログファイル、エディタ設定、ローカル生成物

## GitHub への初回push

GitHub で空のリポジトリを作成してから、以下を実行します。

```sh
git remote add origin <GitHubリポジトリURL>
git branch -M main
git push -u origin main
```

空リポジトリ作成時は、GitHub側で README / .gitignore / License を追加しないでください。

## 開発メモ

- DB接続先は `DATABASE_URL` 環境変数から読みます。
- アプリ起動時に `init_db()` が `children` と `growth_records` テーブルを作成します。
- SQLは psycopg のプレースホルダを使って実行しています。
- `./app:/app` を volume mount しているため、ローカルのアプリコード変更がコンテナに反映されます。

## 次のステップ

- GitHub リポジトリを作成して `origin` を設定する
- 必要に応じてDB確認用の Adminer や pgAdmin を追加する
- Step 3 で画面改善、入力編集、グラフ表示などを検討する
