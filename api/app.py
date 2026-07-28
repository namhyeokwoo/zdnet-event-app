"""ZD 이벤트 캘린더 — 클라우드 쓰기 경로 API (Render + Neon Postgres).

K:\\claude\\hub_api.py 의 /events, /tags 라우트를 여기로 이전한 것.
경로/JSON 형태는 동일 — www/js/api.js는 base URL만 바꾸면 됨.
Tailscale 바인딩과 달리 공인망에 노출되므로 CORS를 origin 화이트리스트로 제한하고
PUT/DELETE를 Access-Control-Allow-Methods에 포함(원본의 누락 버그 수정), rate limit 추가.
"""
import os
import re
import time

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import events_store

TOKEN = os.environ.get("HUB_API_TOKEN", "")
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}

app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])


@app.before_request
def _auth():
    if request.method == "OPTIONS":
        return  # CORS preflight has no Authorization header
    if not TOKEN or request.headers.get("Authorization") != f"Bearer {TOKEN}":
        return jsonify(ok=False, error="unauthorized"), 401


@app.after_request
def _cors(resp):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    return jsonify(ok=True, data={"time": time.time()})


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _validate_event_payload(body: dict, *, require_title_and_date: bool) -> str | None:
    if require_title_and_date:
        if not body.get("title"):
            return "title은 필수입니다"
        if not body.get("start_at"):
            return "start_at은 필수입니다"
    if "start_at" in body and body["start_at"] is not None and not _DATE_RE.match(body["start_at"]):
        return "start_at은 YYYY-MM-DD 형식이어야 합니다"
    if body.get("end_at") and not _DATE_RE.match(body["end_at"]):
        return "end_at은 YYYY-MM-DD 형식이어야 합니다"
    if body.get("time") and not _TIME_RE.match(body["time"]):
        return "time은 HH:MM 형식이어야 합니다"
    return None


# ── 개인 일정 CRUD ────────────────────────────────────────────────────

@app.route("/events/manual", methods=["GET", "OPTIONS"])
def list_manual_events():
    return jsonify(ok=True, data=events_store.list_manual_events())


@app.route("/events/manual", methods=["POST", "OPTIONS"])
def create_manual_event():
    body = request.get_json(silent=True) or {}
    err = _validate_event_payload(body, require_title_and_date=True)
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True, data=events_store.create_manual_event(body)), 201


@app.route("/events/manual/<int:event_id>", methods=["PUT", "OPTIONS"])
def update_manual_event(event_id):
    body = request.get_json(silent=True) or {}
    err = _validate_event_payload(body, require_title_and_date=False)
    if err:
        return jsonify(ok=False, error=err), 400
    updated = events_store.update_manual_event(event_id, body)
    if updated is None:
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True, data=updated)


@app.route("/events/manual/<int:event_id>", methods=["DELETE", "OPTIONS"])
def delete_manual_event(event_id):
    if not events_store.delete_manual_event(event_id):
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True)


# ── 자동 추출 이벤트 검수 상태 ──────────────────────────────────────────

@app.route("/events/review", methods=["GET", "OPTIONS"])
def list_review_status():
    return jsonify(ok=True, data=events_store.list_review_status())


@app.route("/events/review/<event_id>", methods=["POST", "OPTIONS"])
def set_review_status(event_id):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in ("pending", "confirmed", "rejected"):
        return jsonify(ok=False, error="status는 pending/confirmed/rejected 중 하나여야 합니다"), 400
    overrides = body.get("overrides")
    if overrides is not None:
        err = _validate_event_payload(overrides, require_title_and_date=False)
        if err:
            return jsonify(ok=False, error=err), 400
    try:
        result = events_store.set_review_status(event_id, status, overrides)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, data=result)


# ── 태그 ────────────────────────────────────────────────────────────────

@app.route("/tags", methods=["GET", "OPTIONS"])
def list_tags():
    return jsonify(ok=True, data=events_store.list_tags())


@app.route("/tags", methods=["POST", "OPTIONS"])
def create_tag():
    name = (request.get_json(silent=True) or {}).get("name", "").strip()
    if not name:
        return jsonify(ok=False, error="name은 필수입니다"), 400
    return jsonify(ok=True, data=events_store.create_tag(name)), 201


@app.route("/tags/<int:tag_id>", methods=["DELETE", "OPTIONS"])
def delete_tag(tag_id):
    if not events_store.delete_tag(tag_id):
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True)


@app.route("/events/<event_id>/tags", methods=["GET", "OPTIONS"])
def get_event_tags(event_id):
    return jsonify(ok=True, data=events_store.get_event_tags(event_id))


@app.route("/events/<event_id>/tags", methods=["POST", "OPTIONS"])
def add_event_tag(event_id):
    body = request.get_json(silent=True) or {}
    tag_id = body.get("tag_id")
    if tag_id is None and body.get("name"):
        tag_id = events_store.create_tag(body["name"].strip())["id"]
    if tag_id is None:
        return jsonify(ok=False, error="tag_id 또는 name이 필요합니다"), 400
    events_store.add_event_tag(event_id, tag_id)
    return jsonify(ok=True, data=events_store.get_event_tags(event_id))


@app.route("/events/<event_id>/tags/<int:tag_id>", methods=["DELETE", "OPTIONS"])
def remove_event_tag(event_id, tag_id):
    events_store.remove_event_tag(event_id, tag_id)
    return jsonify(ok=True, data=events_store.get_event_tags(event_id))


if __name__ == "__main__":
    if not TOKEN:
        print("[오류] HUB_API_TOKEN 이 설정되지 않았습니다.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8788)), debug=False)
