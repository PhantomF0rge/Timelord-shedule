# scripts/dump_client_routes.py
# Usage:
#   python scripts/dump_client_routes.py [out_file]
# or:
#   python -m scripts.dump_client_routes [out_file]
from __future__ import annotations

import sys
import json
from pathlib import Path

# --- ensure project root on sys.path ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- get Flask app ---
try:
    # предпочтительно: брать уже созданный app из wsgi.py в корне
    from wsgi import app  # type: ignore
except Exception:
    # фолбэк: собрать приложение из фабрики
    from app import create_app  # type: ignore
    app = create_app("dev")

API_PREFIX = "/api/"

def _is_client_rule(rule) -> bool:
    """Считать клиентскими: без /api/*, без static и без blueprints, имя которых включает 'api'."""
    if rule.rule.startswith(API_PREFIX):
        return False
    if rule.endpoint == "static" or rule.endpoint.endswith(".static"):
        return False
    bp = rule.endpoint.split(".")[0] if "." in rule.endpoint else ""
    if "api" in bp.lower():
        return False
    return True

def _collect():
    rows = []
    with app.app_context():
        for rule in app.url_map.iter_rules():
            if not _is_client_rule(rule):
                continue
            methods = sorted(m for m in (rule.methods or []) if m in {"GET", "POST", "PUT", "PATCH", "DELETE"})
            rows.append({
                "url": rule.rule,
                "endpoint": rule.endpoint,
                "methods": methods,
            })
    rows.sort(key=lambda r: (r["url"], r["endpoint"]))
    return rows

def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("client_routes.txt")
    rows = _collect()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".json":
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        lines = [f"{','.join(r['methods']):<18} {r['url']:<45} {r['endpoint']}" for r in rows]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(rows)} client routes to {out}")

if __name__ == "__main__":
    main()
