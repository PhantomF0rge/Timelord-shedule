# blueprints/import_export/services.py
from __future__ import annotations
from dataclasses import dataclass
from io import StringIO
import io
import csv
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models import Group, Subject, Curriculum, Building, RoomType, Room

# ---------- util: CSV чтение с автоопределением разделителя
def read_csv_text(text: str) -> tuple[list[str], list[list[str]]]:
    # пробуем угадать разделитель, иначе ','; как запасной вариант — ';'
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0])
        delim = dialect.delimiter
    except Exception:
        delim = "," if ("," in text.splitlines()[0]) else ";"
    reader = csv.reader(StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        return [], []
    header, data = rows[0], rows[1:]
    return [h.strip() for h in header], [list(map(str.strip, r)) for r in data]

# ---------- детектирование маппинга по заголовкам
HEADER_SYNONYMS: dict[str, list[str]] = {
    # groups
    "code": ["code", "group_code", "группа", "код"],
    "name": ["name", "group_name", "наименование", "название"],
    "students_count": ["students_count", "size", "численность", "студенты"],
    "education_level": ["education_level", "level", "уровень"],
    # teachers
    "full_name": ["full_name", "teacher", "фио", "ФИО"],
    "short_name": ["short_name", "abbr", "кратко"],
    "external_id": ["external_id", "ext_id"],
    # rooms
    "building_name": ["building", "building_name", "здание", "корпус"],
    "room_type_name": ["room_type", "room_type_name", "тип"],
    "number": ["number", "room", "каб", "аудитория"],
    "capacity": ["capacity", "вместимость"],
    "computers_count": ["computers", "computers_count", "пк"],
    # curriculum
    "group_code": ["group_code", "group", "группа"],
    "subject_name": ["subject", "subject_name", "дисциплина", "предмет"],
    "total_hours": ["total_hours", "hours", "часы"],
}

def detect_mapping(header: list[str], required_keys: list[str]) -> dict[str, str]:
    h_lower = [h.strip().lower() for h in header]
    mapping: dict[str, str] = {}
    for field in required_keys:
        cands = HEADER_SYNONYMS.get(field, [field])
        for c in cands:
            if c.lower() in h_lower:
                mapping[field] = header[h_lower.index(c.lower())]
                break
    return mapping

ALLOWED_EDU = {"СПО", "ВО"}

def _read_rows(text: str) -> List[Dict[str, str]]:
    # Поддержка и запятой, и точки с запятой
    sample = text.splitlines()[0] if text else ""
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader)  # список словарей

def _extract(row: Dict[str, str], mapping: Dict[str, str], key: str, default: str = "") -> str:
    src = mapping.get(key)
    return (row.get(src, default) if src else default).strip()

# ---------- контракты для ошибок
@dataclass
class RowError:
    row_index: int   # 1-based по данным (без хедера)
    code: str
    details: dict[str, Any] | None = None

# ---------- валидация и преобразование по сущностям
def _int_or_none(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None

def validate_groups(rows: list[dict[str, str]]) -> tuple[list[Group], list[RowError], list[dict]]:
    errors: list[RowError] = []
    dups: list[dict] = []
    objs: list[Group] = []

    # дубликаты внутри файла по code
    seen: set[str] = set()
    for i, r in enumerate(rows, start=1):
        code = (r.get("code") or "").strip()
        name = (r.get("name") or "").strip()
        students_count = _int_or_none(r.get("students_count") or "")
        education_level = (r.get("education_level") or "").strip() or None

        if not code or not name:
            errors.append(RowError(i, "MISSING_REQUIRED", {"fields": ["code","name"]}))
            continue
        if code in seen:
            dups.append({"row": i, "unique_key": code})
            continue
        seen.add(code)

        # проверка БД на существование
        if Group.query.filter_by(code=code).first():
            dups.append({"row": i, "unique_key": code})
            continue

        if students_count is None:
            errors.append(RowError(i, "INVALID_INT", {"field": "students_count"}))
            continue

        objs.append(Group(code=code, name=name, students_count=students_count, education_level=education_level))
    return objs, errors, dups

def validate_teachers(rows: list[dict[str, str]]) -> tuple[list[Teacher], list[RowError], list[dict]]:
    errors: list[RowError] = []
    dups: list[dict] = []
    objs: list[Teacher] = []
    seen: set[str] = set()

    for i, r in enumerate(rows, start=1):
        fn = (r.get("full_name") or "").strip()
        sn = (r.get("short_name") or "").strip() or None
        eid = (r.get("external_id") or "").strip() or None
        if not fn:
            errors.append(RowError(i, "MISSING_REQUIRED", {"fields": ["full_name"]}))
            continue
        if fn in seen:
            dups.append({"row": i, "unique_key": fn}); continue
        seen.add(fn)
        if Teacher.query.filter_by(full_name=fn).first():
            dups.append({"row": i, "unique_key": fn}); continue
        objs.append(Teacher(full_name=fn, short_name=sn, external_id=eid))
    return objs, errors, dups

def validate_rooms(rows: list[dict[str, str]]) -> tuple[list[Room], list[RowError], list[dict]]:
    errors: list[RowError] = []
    dups: list[dict] = []
    objs: list[Room] = []
    seen: set[tuple[int,str]] = set()

    for i, r in enumerate(rows, start=1):
        bname = (r.get("building_name") or "").strip()
        rtname = (r.get("room_type_name") or "").strip()
        number = (r.get("number") or "").strip()
        capacity = _int_or_none(r.get("capacity") or "")
        computers = _int_or_none(r.get("computers_count") or "") or 0

        if not (bname and rtname and number and capacity is not None):
            errors.append(RowError(i, "MISSING_REQUIRED", {"fields": ["building_name","room_type_name","number","capacity"]}))
            continue

        b = Building.query.filter_by(name=bname).first()
        rt = RoomType.query.filter_by(name=rtname).first()
        if not b:
            errors.append(RowError(i, "UNKNOWN_BUILDING", {"building_name": bname})); continue
        if not rt:
            errors.append(RowError(i, "UNKNOWN_ROOM_TYPE", {"room_type_name": rtname})); continue

        key = (b.id, number)
        if key in seen:
            dups.append({"row": i, "unique_key": f"{bname}:{number}"}); continue
        seen.add(key)
        if Room.query.filter_by(building_id=b.id, number=number).first():
            dups.append({"row": i, "unique_key": f"{bname}:{number}"}); continue

        objs.append(Room(building_id=b.id, number=number, capacity=capacity, room_type_id=rt.id, computers_count=computers))
    return objs, errors, dups

def validate_curriculum(rows: list[dict[str, str]]) -> tuple[list[Curriculum], list[RowError], list[dict]]:
    errors: list[RowError] = []
    dups: list[dict] = []
    objs: list[Curriculum] = []
    seen: set[tuple[int,int]] = set()

    for i, r in enumerate(rows, start=1):
        gcode = (r.get("group_code") or "").strip()
        sname = (r.get("subject_name") or "").strip()
        total_hours = _int_or_none(r.get("total_hours") or "")
        if not (gcode and sname and total_hours is not None):
            errors.append(RowError(i, "MISSING_REQUIRED", {"fields": ["group_code","subject_name","total_hours"]}))
            continue
        g = Group.query.filter_by(code=gcode).first()
        s = Subject.query.filter_by(name=sname).first()
        if not g:
            errors.append(RowError(i, "UNKNOWN_GROUP", {"group_code": gcode})); continue
        if not s:
            errors.append(RowError(i, "UNKNOWN_SUBJECT", {"subject_name": sname})); continue

        key = (g.id, s.id)
        if key in seen:
            dups.append({"row": i, "unique_key": f"{gcode}:{sname}"}); continue
        seen.add(key)
        if Curriculum.query.filter_by(group_id=g.id, subject_id=s.id).first():
            dups.append({"row": i, "unique_key": f"{gcode}:{sname}"}); continue

        objs.append(Curriculum(group_id=g.id, subject_id=s.id, total_hours=total_hours))
    return objs, errors, dups

# ---------- фасад
ENTITY_SPEC = {
    "groups": {
        "required": ["code","name","students_count","education_level"],
        "validator": validate_groups,
    },
    "teachers": {
        "required": ["full_name","short_name","external_id"],
        "validator": validate_teachers,
    },
    "rooms": {
        "required": ["building_name","room_type_name","number","capacity","computers_count"],
        "validator": validate_rooms,
    },
    "curriculum": {
        "required": ["group_code","subject_name","total_hours"],
        "validator": validate_curriculum,
    },
}

def apply_mapping(header: list[str], rows: list[list[str]], mapping: dict[str,str]) -> list[dict[str,str]]:
    # mapping: field -> column_name
    idx = {col: i for i, col in enumerate(header)}
    out: list[dict[str,str]] = []
    for r in rows:
        item: dict[str,str] = {}
        for field, col in mapping.items():
            if col in idx and idx[col] < len(r):
                item[field] = r[idx[col]]
            else:
                item[field] = ""
        out.append(item)
    return out

def preview(text: str, entity: str) -> dict[str, Any]:
    spec = ENTITY_SPEC.get(entity)
    if not spec:
        return {"ok": False, "errors": [{"code": "UNKNOWN_ENTITY"}]}
    header, data = read_csv_text(text)
    mapping = detect_mapping(header, spec["required"])
    sample = data[:5]
    return {"ok": True, "columns": header, "sample": sample, "detected_mapping": mapping}

def validate_or_commit(text: str, entity: str, mapping: Dict[str, str], dry_run: bool) -> Tuple[bool, Dict[str, Any]]:
    """
    Возвращает (ok, payload). На dry_run всегда статус 200 в роуте.
    На commit: ok==False -> роут отдаёт 422.
    """
    rows = _read_rows(text)
    errors: List[Dict[str, Any]] = []

    if entity == "groups":
        seen_codes: set[str] = set()
        to_create: list[Group] = []
        for idx, row in enumerate(rows, start=2):  # +1 за заголовок, ещё +1 чтобы было «человеческое» смещение
            code = _extract(row, mapping, "code")
            name = _extract(row, mapping, "name")
            scnt = _extract(row, mapping, "students_count")
            edu = _extract(row, mapping, "education_level")

            # базовая валидация
            if not code or not name:
                errors.append({"row": idx, "code": "REQUIRED"})
                continue
            if code in seen_codes:
                errors.append({"row": idx, "code": "DUPLICATE_IN_FILE"})
                continue
            seen_codes.add(code)

            try:
                students = int(scnt)
                if students < 0:
                    raise ValueError
            except Exception:
                errors.append({"row": idx, "code": "BAD_STUDENTS_COUNT"})
                continue

            if edu not in ALLOWED_EDU:
                errors.append({"row": idx, "code": "BAD_EDUCATION_LEVEL"})
                continue

            # валидация дубликатов в БД (для dry-run — просто сообщаем)
            exists = Group.query.filter_by(code=code).first()
            if exists:
                errors.append({"row": idx, "code": "DUPLICATE_DB"})
                continue

            g = Group(code=code, name=name, students_count=students, education_level=edu)
            to_create.append(g)

        if dry_run:
            return (len(errors) == 0, {"entity": entity, "errors": errors, "rows": len(rows)})

        if errors:
            return (False, {"entity": entity, "errors": errors})

        # commit atomically
        try:
            with db.session.begin():
                for g in to_create:
                    db.session.add(g)
            return (True, {"entity": entity, "inserted": len(to_create)})
        except Exception:
            db.session.rollback()
            return (False, {"entity": entity, "errors": [{"code": "DB_ERROR"}]})

    elif entity == "rooms":
        # Оставляем текущее поведение (тест ожидает 422 при UNKNOWN building)
        to_create: list[Room] = []
        for idx, row in enumerate(rows, start=2):
            bname = _extract(row, mapping, "building_name")
            rtname = _extract(row, mapping, "room_type_name")
            number = _extract(row, mapping, "number")
            cap = _extract(row, mapping, "capacity")
            comps = _extract(row, mapping, "computers_count")

            b = Building.query.filter_by(name=bname).first() if bname else None
            rt = RoomType.query.filter_by(name=rtname).first() if rtname else None
            if not b or not rt or not number:
                errors.append({"row": idx, "code": "FK_NOT_FOUND"})
                continue
            try:
                capacity = int(cap); computers = int(comps or "0")
            except Exception:
                errors.append({"row": idx, "code": "BAD_INT"})
                continue
            if Room.query.filter_by(number=number).first():
                errors.append({"row": idx, "code": "DUPLICATE_DB"})
                continue
            to_create.append(Room(building_id=b.id, room_type_id=rt.id, number=number,
                                  capacity=capacity, computers_count=computers))

        if dry_run:
            return (len(errors) == 0, {"entity": entity, "errors": errors, "rows": len(rows)})

        if errors:
            return (False, {"entity": entity, "errors": errors})

        try:
            with db.session.begin():
                for r in to_create:
                    db.session.add(r)
            return (True, {"entity": entity, "inserted": len(to_create)})
        except Exception:
            db.session.rollback()
            return (False, {"entity": entity, "errors": [{"code": "DB_ERROR"}]})

    elif entity == "curriculum":
        # Валидация не требует предварительного наличия группы/предмета (тест ждёт get-or-create при коммите)
        parsed_rows: list[tuple[str, str, float, int]] = []  # (g_code, s_name, hours, row_idx)
        for idx, row in enumerate(rows, start=2):
            g_code = _extract(row, mapping, "group_code")
            s_name = _extract(row, mapping, "subject_name")
            hrs = _extract(row, mapping, "total_hours")
            if not g_code or not s_name:
                errors.append({"row": idx, "code": "REQUIRED"})
                continue
            try:
                hours = float(hrs)
                if hours < 0:
                    raise ValueError
            except Exception:
                errors.append({"row": idx, "code": "BAD_HOURS"})
                continue
            parsed_rows.append((g_code, s_name, hours, idx))

        if dry_run:
            # просто сообщаем об ошибках формата/значений
            return (len(errors) == 0, {"entity": entity, "errors": errors, "rows": len(rows)})

        if errors:
            return (False, {"entity": entity, "errors": errors})

        # commit: get-or-create Group/Subject, upsert Curriculum
        try:
            with db.session.begin():
                for g_code, s_name, hours, idx in parsed_rows:
                    g = Group.query.filter_by(code=g_code).first()
                    if not g:
                        # минимально валидная запись
                        g = Group(code=g_code, name=g_code, students_count=0, education_level="СПО")
                        db.session.add(g)
                        db.session.flush()
                    s = Subject.query.filter_by(name=s_name).first()
                    if not s:
                        s = Subject(name=s_name, short_name=s_name[:16])
                        db.session.add(s)
                        db.session.flush()
                    cur = Curriculum.query.filter_by(group_id=g.id, subject_id=s.id).first()
                    if not cur:
                        cur = Curriculum(group_id=g.id, subject_id=s.id, total_hours=hours)
                        db.session.add(cur)
                    else:
                        cur.total_hours = hours
            return (True, {"entity": entity, "upserted": len(parsed_rows)})
        except Exception:
            db.session.rollback()
            return (False, {"entity": entity, "errors": [{"code": "DB_ERROR"}]})

    else:
        # неизвестная сущность
        return (False, {"errors": [{"code": "UNKNOWN_ENTITY", "entity": entity}]})
