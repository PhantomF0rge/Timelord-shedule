from __future__ import annotations
import re
from http.cookies import SimpleCookie

from app import create_app

VISITOR_COOKIE = "visitor_id"
MAX_AGE = 60 * 60 * 24 * 180  # 180 дней

def _get_cookie_from_headers(headers, name: str):
    raw = headers.get("Set-Cookie")
    if not raw:
        return None
    c = SimpleCookie()
    c.load(raw)
    morsel = c.get(name)
    return morsel

def test_health_ok():
    app = create_app("dev")
    with app.test_client() as c:
        rv = c.get("/health")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"
        # Должны отдать visitor_id в JSON (созданный или существующий)
        assert "visitor_id" in data

def test_sets_visitor_id_cookie():
    app = create_app("dev")
    with app.test_client() as c:
        rv = c.get("/health")
        assert rv.status_code == 200

        cookie = _get_cookie_from_headers(rv.headers, VISITOR_COOKIE)
        assert cookie is not None, "должен быть установлен visitor_id"
        assert re.fullmatch(r"[0-9a-f]{32}", cookie.value), "ожидаем uuid4 hex"
        # Max-Age должен быть 180 дней
        assert cookie["max-age"] == str(MAX_AGE)

        # Повторный запрос с тем же cookie — не должен переустанавливать новый
        rv2 = c.get("/health", headers={"Cookie": f"{VISITOR_COOKIE}={cookie.value}"})
        # либо заголовка Set-Cookie нет, либо он с тем же value
        cookie2 = _get_cookie_from_headers(rv2.headers, VISITOR_COOKIE)
        if cookie2:
            assert cookie2.value == cookie.value
