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
  requirements.txt
  vercel.json
  db/
    schema.sql
    README.md
  app/
    __init__.py
    Dockerfile
    requirements.txt
    app.py
    api/
      __init__.py
      index.py
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
- サンプルUIに合わせた Home / Chart / Add / Gallery / Profile のタブ構成
- 写真つき成長記録の追加、アルバム表示

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

## 本番用DBの準備

Step 3 では、Vercel から接続する外部 PostgreSQL を用意します。第一候補は Neon です。Supabase を使う場合も、PostgreSQL の接続文字列を `DATABASE_URL` として扱えます。

### ローカルDBと本番DBの違い

ローカル:

- Docker Compose の `db` コンテナ
- 接続先は `db:5432`
- 学習・開発用

本番:

- Neon / Supabase などの外部PostgreSQL
- 接続先は外部DBのホスト
- Vercel から接続する

### Neon を使う場合

1. Neon にログインする
2. `New Project` を作成する
3. PostgreSQL の connection string を取得する
4. connection string を `DATABASE_URL` として扱う
5. 本番用の `DATABASE_URL` は Git に入れない

後続の Step 4 で、Vercel の Environment Variables に本番用 `DATABASE_URL` を登録します。

### schema.sql の適用

本番DBに必要なテーブル定義は `db/schema.sql` にあります。

ローカルに `psql` がある場合:

```sh
psql "$DATABASE_URL" -f db/schema.sql
```

Docker を使って `psql` を実行する場合:

```sh
docker run --rm -it \
  -v "$PWD/db:/db" \
  postgres:16 \
  psql "$DATABASE_URL" -f /db/schema.sql
```

実際の `DATABASE_URL`、DBパスワード、`FLASK_SECRET_KEY` は Git に含めないでください。`.env` に書く場合も、`.env` はローカル専用として管理します。

## Vercel デプロイ設定

Vercel では Docker Compose を使わず、リポジトリルートをVercelプロジェクトとしてデプロイします。

Vercel側の設定:

- Root Directory: 未設定、またはリポジトリルート
- Environment Variables:
  - `DATABASE_URL`: Neon / Supabase の本番PostgreSQL接続文字列
  - `FLASK_SECRET_KEY`: 本番用のランダムな秘密値

ルートの `vercel.json` では、すべてのリクエストを `app/api/index.py` に渡し、そこから `app/app.py` のFlaskアプリを読み込みます。

ルートの `requirements.txt` はVercel用です。`app/requirements.txt` はローカルDocker用として残しています。

```text
ブラウザ
  -> Vercel
  -> vercel.json
  -> app/api/index.py
  -> app/app.py
  -> Flask
  -> PostgreSQL
```

`compose.yml`、`app/Dockerfile`、ローカルPostgreSQLコンテナは、ローカル開発用です。Vercel本番環境では使いません。

## 開発メモ

- DB接続先は `DATABASE_URL` 環境変数から読みます。
- アプリ起動時に `init_db()` が `children` と `growth_records` テーブルを作成します。
- SQLは psycopg のプレースホルダを使って実行しています。
- `./app:/app` を volume mount しているため、ローカルのアプリコード変更がコンテナに反映されます。
- 写真は最小構成としてPostgreSQLの `BYTEA` カラムに保存します。
- 写真はJPEG、PNG、GIF、WebPに対応し、標準では10MBまでです。

## 次のステップ

- Step 4 で Vercel に GitHub リポジトリを接続する
- Step 4 で Vercel の Environment Variables に `DATABASE_URL` を登録する
- 必要に応じてDB確認用の Adminer や pgAdmin を追加する
