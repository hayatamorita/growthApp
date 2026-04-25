import os
import time
from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from psycopg.rows import dict_row
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get(
    "SECRET_KEY", "local-dev-secret-key"
)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_BYTES", 11 * 1024 * 1024))

DATABASE_URL = os.environ.get("DATABASE_URL")
db_initialized = False
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", 10 * 1024 * 1024))
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


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
                    image_data BYTEA,
                    image_mime_type TEXT,
                    image_filename TEXT,
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
                ALTER TABLE growth_records
                ADD COLUMN IF NOT EXISTS image_data BYTEA
                """
            )
            cur.execute(
                """
                ALTER TABLE growth_records
                ADD COLUMN IF NOT EXISTS image_mime_type TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE growth_records
                ADD COLUMN IF NOT EXISTS image_filename TEXT
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


def detect_image_mime_type(image_data):
    if image_data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(image_data) >= 12 and image_data[:4] == b"RIFF" and image_data[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_optional_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None, None

    image_data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if len(image_data) > MAX_IMAGE_BYTES:
        raise ValueError("画像サイズは10MB以下にしてください。")

    image_mime_type = detect_image_mime_type(image_data)
    if image_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("画像はJPEG、PNG、GIF、WebPのいずれかを選択してください。")

    image_filename = secure_filename(file_storage.filename) or None
    return image_data, image_mime_type, image_filename


def format_age(birthday):
    if not birthday:
        return "誕生日未設定"
    today = date.today()
    total_months = (today.year - birthday.year) * 12 + today.month - birthday.month
    if today.day < birthday.day:
        total_months -= 1
    if total_months < 0:
        return "誕生予定"
    years = total_months // 12
    months = total_months % 12
    if years == 0:
        return f"{months}ヶ月"
    return f"{years}歳 {months}ヶ月"


def format_month(record_date):
    return f"{record_date.year}年 {record_date.month}月"


def get_children():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, birthday FROM children ORDER BY id DESC")
            return cur.fetchall()


def get_child_or_none(child_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, birthday FROM children WHERE id = %s",
                (child_id,),
            )
            return cur.fetchone()


def get_active_child(child_id=None):
    if child_id:
        child = get_child_or_none(child_id)
        if child:
            return child
    children = get_children()
    return children[0] if children else None


def get_records(child_id, limit=None, images_only=False, ascending=False):
    order_direction = "ASC" if ascending else "DESC"
    image_clause = "AND image_data IS NOT NULL" if images_only else ""
    limit_clause = "LIMIT %s" if limit else ""
    params = [child_id]
    if limit:
        params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    child_id,
                    record_date,
                    height_cm,
                    weight_kg,
                    memo,
                    image_filename,
                    image_mime_type,
                    image_data IS NOT NULL AS has_image,
                    created_at
                FROM growth_records
                WHERE child_id = %s
                {image_clause}
                ORDER BY record_date {order_direction}, id {order_direction}
                {limit_clause}
                """,
                tuple(params),
            )
            return cur.fetchall()


def latest_value(records, key):
    for record in records:
        if record[key] is not None:
            return record[key]
    return None


def build_record_form_defaults(child_id):
    recent_records = get_records(child_id, limit=10)
    return {
        "record_date": date.today().isoformat(),
        "height_cm": latest_value(recent_records, "height_cm") or "",
        "weight_kg": latest_value(recent_records, "weight_kg") or "",
        "memo": "",
    }


def build_chart_points(records, key):
    values = [record for record in records if record[key] is not None]
    if not values:
        return {"points": "", "labels": [], "latest": None}

    values = values[-6:]
    numeric_values = [float(record[key]) for record in values]
    min_value = min(numeric_values)
    max_value = max(numeric_values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1

    points = []
    labels = []
    for index, record in enumerate(values):
        x_position = 12 + (76 * index / max(len(values) - 1, 1))
        y_position = 84 - ((float(record[key]) - min_value) / (max_value - min_value) * 68)
        points.append(f"{x_position:.2f},{y_position:.2f}")
        labels.append(record["record_date"].strftime("%m/%d"))

    return {
        "points": " ".join(points),
        "labels": labels,
        "latest": numeric_values[-1],
    }


def records_by_month(records):
    grouped_records = {}
    for record in records:
        month_label = format_month(record["record_date"])
        grouped_records.setdefault(month_label, []).append(record)
    return grouped_records.items()


def create_child_from_form():
    name = request.form.get("name", "").strip()
    birthday = request.form.get("birthday", "") or None

    if not name:
        flash("赤ちゃんの名前は必須です。", "error")
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO children (name, birthday) VALUES (%s, %s) RETURNING id",
                (name, birthday),
            )
            child = cur.fetchone()
        conn.commit()

    flash("赤ちゃんを追加しました。", "success")
    return child["id"]


def render_child_page(template_name, child, active_tab, **context):
    return render_template(
        template_name,
        child=child,
        children=get_children(),
        active_tab=active_tab,
        age_text=format_age(child["birthday"]) if child else None,
        **context,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        child_id = create_child_from_form()
        if child_id:
            return redirect(url_for("child_detail", child_id=child_id))

    child = get_active_child()
    if not child:
        return render_template("profile.html", child=None, children=[], active_tab="profile")
    return redirect(url_for("child_detail", child_id=child["id"]))


@app.route("/children/<int:child_id>")
def child_detail(child_id):
    child = get_active_child(child_id)
    if not child:
        flash("赤ちゃんが見つかりません。", "error")
        return redirect(url_for("index"))

    records = get_records(child["id"], limit=8)
    return render_child_page(
        "index.html",
        child,
        "home",
        records=records,
        latest_height=latest_value(records, "height_cm"),
        latest_weight=latest_value(records, "weight_kg"),
    )


@app.route("/children/<int:child_id>/chart")
def growth_chart(child_id):
    child = get_active_child(child_id)
    if not child:
        flash("赤ちゃんが見つかりません。", "error")
        return redirect(url_for("index"))

    records = get_records(child["id"], ascending=True)
    return render_child_page(
        "growth_chart.html",
        child,
        "chart",
        records=records,
        height_chart=build_chart_points(records, "height_cm"),
        weight_chart=build_chart_points(records, "weight_kg"),
    )


@app.route("/children/<int:child_id>/records/new", methods=["GET", "POST"])
def add_record(child_id):
    child = get_active_child(child_id)
    if not child:
        flash("赤ちゃんが見つかりません。", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        record_date = request.form.get("record_date", "")
        height_text = request.form.get("height_cm", "").strip()
        weight_text = request.form.get("weight_kg", "").strip()
        memo = request.form.get("memo", "").strip() or None
        image_file = request.files.get("image")

        try:
            if not record_date:
                raise ValueError("記録日は必須です。")
            height_cm = parse_optional_decimal(height_text, "身長")
            weight_kg = parse_optional_decimal(weight_text, "体重")
            image_data, image_mime_type, image_filename = read_optional_image(image_file)
        except ValueError as error:
            flash(str(error), "error")
            form_defaults = build_record_form_defaults(child["id"])
            form_defaults.update(request.form)
            return render_child_page(
                "add_record.html",
                child,
                "add",
                form=form_defaults,
            )

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO growth_records
                        (
                            child_id,
                            record_date,
                            height_cm,
                            weight_kg,
                            memo,
                            image_data,
                            image_mime_type,
                            image_filename
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        child["id"],
                        record_date,
                        height_cm,
                        weight_kg,
                        memo,
                        image_data,
                        image_mime_type,
                        image_filename,
                    ),
                )
            conn.commit()
        flash("成長記録を追加しました。", "success")
        return redirect(url_for("child_detail", child_id=child["id"]))

    return render_child_page(
        "add_record.html",
        child,
        "add",
        form=build_record_form_defaults(child["id"]),
    )


@app.route("/children/<int:child_id>/gallery")
def gallery(child_id):
    child = get_active_child(child_id)
    if not child:
        flash("赤ちゃんが見つかりません。", "error")
        return redirect(url_for("index"))

    image_records = get_records(child["id"], images_only=True)
    return render_child_page(
        "gallery.html",
        child,
        "gallery",
        grouped_records=records_by_month(image_records),
        image_count=len(image_records),
    )


@app.route("/children/<int:child_id>/profile", methods=["GET", "POST"])
def profile(child_id):
    child = get_active_child(child_id)
    if request.method == "POST":
        new_child_id = create_child_from_form()
        if new_child_id:
            return redirect(url_for("profile", child_id=new_child_id))

    return render_child_page("profile.html", child, "profile")


@app.route("/records/<int:record_id>/image")
def record_image(record_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT image_data, image_mime_type, image_filename
                FROM growth_records
                WHERE id = %s AND image_data IS NOT NULL
                """,
                (record_id,),
            )
            record = cur.fetchone()

    if not record:
        abort(404)

    response = Response(
        bytes(record["image_data"]),
        mimetype=record["image_mime_type"] or "application/octet-stream",
    )
    if record["image_filename"]:
        response.headers["Content-Disposition"] = f'inline; filename="{record["image_filename"]}"'
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


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

    flash("赤ちゃんを削除しました。", "success")
    return redirect(url_for("index"))


@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(error):
    flash("アップロードできる画像は10MB以下です。", "error")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    ensure_db_initialized()
    app.run(host="0.0.0.0", port=5000, debug=True)
