# DBスキーマ管理

このディレクトリは、本番用 PostgreSQL に作成するスキーマを管理します。

## schema.sql

`schema.sql` は、成長記録アプリで使う `children` と `growth_records` テーブル、検索用の index を作成する PostgreSQL 用SQLです。

`CREATE TABLE IF NOT EXISTS` と `CREATE INDEX IF NOT EXISTS` を使っているため、既存のテーブルや index がある場合でもエラーになりにくい構成です。

## Neon でPostgreSQLを作る手順

1. Neon にログインする
2. `New Project` を作成する
3. PostgreSQL の connection string を取得する
4. connection string を `DATABASE_URL` として扱う
5. 本番用の `DATABASE_URL` は Git に入れない
6. 後続の Step 4 で Vercel の Environment Variables に登録する

## Supabase を使う場合

Supabase を使う場合も、PostgreSQL の接続文字列を `DATABASE_URL` として扱います。

- `Project Settings` / `Database` から接続情報を取得する
- Transaction pooler / direct connection の違いがある場合は、Vercel から使う接続文字列を確認する
- 最初はサービス公式の接続文字列を使う

## DATABASE_URL の扱い

- 実際の `DATABASE_URL` は表示しない
- `.env` に書く場合は Git に含めない
- README や `.env.example` にはサンプル値だけを書く
- 後続の Step 4 で Vercel の環境変数として登録する

## schema.sql の適用方法

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

## 注意事項

- 本番DBに直接接続する操作なので、実行前に接続先をよく確認する
- 本番DBの接続URL、パスワード、`SECRET_KEY` は Git に含めない
- DBダンプやログファイルを Git に含めない
- Vercel への登録は Step 4 で行う
