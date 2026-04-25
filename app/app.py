import os
import time
from decimal import Decimal, InvalidOperation

import psycopg
from flask import Flask, flash, redirect, render_template, request, url_for
from psycopg.rows import dict_row


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get(
    "SECRET_KEY", "local-dev-secret-key"
)

DATABASE_URL = os.environ.get("DATABASE_URL")
db_initialized = False


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が設定されていません。")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def wait_for_db(max_retries=30, delay_seconds=2):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return
        except psycopg.OperationalError as error:
            last_error = error
            print(f"DB接続待機中... ({attempt}/{max_retries})")
            time.sleep(delay_seconds)
    raise RuntimeError("DBに接続できませんでした。") from last_error


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS children (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    birthday DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS growth_records (
                    id SERIAL PRIMARY KEY,
                    child_id INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
                    record_date DATE NOT NULL,
                    height_cm NUMERIC,
                    weight_kg NUMERIC,
                    memo TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE children
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_growth_records_child_id
                ON growth_records (child_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_growth_records_record_date
                ON growth_records (record_date)
                """
            )
        conn.commit()


def ensure_db_initialized():
    global db_initialized
    if db_initialized:
        return
    wait_for_db()
    init_db()
    db_initialized = True


@app.before_request
def initialize_db_before_request():
    ensure_db_initialized()


def parse_optional_decimal(value, field_name):
    if value == "":
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field_name} は数値で入力してください。")
    if parsed < 0:
        raise ValueError(f"{field_name} は0以上で入力してください。")
    return parsed


def get_child_or_none(child_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, birthday FROM children WHERE id = %s",
                (child_id,),
            )
            return cur.fetchone()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        birthday = request.form.get("birthday", "") or None

        if not name:
            flash("子供の名前は必須です。", "error")
        else:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO children (name, birthday) VALUES (%s, %s)",
                        (name, birthday),
                    )
                conn.commit()
            flash("子供を追加しました。", "success")
            return redirect(url_for("index"))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, birthday FROM children ORDER BY id DESC")
            children = cur.fetchall()

    return render_template("index.html", children=children)


@app.route("/children/<int:child_id>")
def child_detail(child_id):
    child = get_child_or_none(child_id)
    if not child:
        flash("子供が見つかりません。", "error")
        return redirect(url_for("index"))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, child_id, record_date, height_cm, weight_kg, memo, created_at
                FROM growth_records
                WHERE child_id = %s
                ORDER BY record_date DESC, id DESC
                """,
                (child_id,),
            )
            records = cur.fetchall()

    return render_template("child.html", child=child, records=records)


@app.route("/children/<int:child_id>/records/new", methods=["GET", "POST"])
def add_record(child_id):
    child = get_child_or_none(child_id)
    if not child:
        flash("子供が見つかりません。", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        record_date = request.form.get("record_date", "")
        height_text = request.form.get("height_cm", "").strip()
        weight_text = request.form.get("weight_kg", "").strip()
        memo = request.form.get("memo", "").strip() or None

        try:
            if not record_date:
                raise ValueError("記録日は必須です。")
            height_cm = parse_optional_decimal(height_text, "身長")
            weight_kg = parse_optional_decimal(weight_text, "体重")
        except ValueError as error:
            flash(str(error), "error")
            return render_template("add_record.html", child=child, form=request.form)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO growth_records
                        (child_id, record_date, height_cm, weight_kg, memo)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (child_id, record_date, height_cm, weight_kg, memo),
                )
            conn.commit()
        flash("成長記録を追加しました。", "success")
        return redirect(url_for("child_detail", child_id=child_id))

    return render_template("add_record.html", child=child, form={})


@app.route("/records/<int:record_id>/delete", methods=["POST"])
def delete_record(record_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT child_id FROM growth_records WHERE id = %s",
                (record_id,),
            )
            record = cur.fetchone()
            if not record:
                flash("記録が見つかりません。", "error")
                return redirect(url_for("index"))
            child_id = record["child_id"]
            cur.execute("DELETE FROM growth_records WHERE id = %s", (record_id,))
        conn.commit()

    flash("成長記録を削除しました。", "success")
    return redirect(url_for("child_detail", child_id=child_id))


@app.route("/children/<int:child_id>/delete", methods=["POST"])
def delete_child(child_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM children WHERE id = %s", (child_id,))
        conn.commit()

    flash("子供を削除しました。", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    ensure_db_initialized()
    app.run(host="0.0.0.0", port=5000, debug=True)
