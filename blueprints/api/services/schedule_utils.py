from datetime import time

def _to_hhmm(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v[:5]
    try:
        return v.strftime("%H:%M")
    except Exception:
        return str(v)[:5]

def normalize_slot(slot) -> dict:
    """Берём start/end/order у объекта TimeSlot (с разными возможными именами полей)."""
    order_no = getattr(slot, "order_no", None) or getattr(slot, "order", None) or getattr(slot, "id", None)
    start = getattr(slot, "start_time", None) or getattr(slot, "start", None)
    end   = getattr(slot, "end_time", None) or getattr(slot, "end", None)
    return {
        "order_no": int(order_no) if isinstance(order_no, (int,)) or (isinstance(order_no, str) and order_no.isdigit()) else order_no,
        "start_time": _to_hhmm(start) or "00:00",
        "end_time": _to_hhmm(end) or "00:00",
    }

def insert_breaks(slots_ordered: list, lessons_payload: list) -> list:
    """
    Вставляет объекты-перерывы между занятиями на основе полной сетки slots_ordered.
    slots_ordered: список объектов TimeSlot (в порядке возрастания).
    lessons_payload: список уже нормализованных занятий с полем time_slot{order_no,...}
    """
    if not slots_ordered:
        return lessons_payload

    # карта слотов: ord -> (from,to)
    slots_map = {}
    for s in slots_ordered:
        ns = normalize_slot(s)
        ord_no = ns["order_no"]
        if ord_no is None:
            continue
        slots_map[int(ord_no)] = (ns["start_time"], ns["end_time"])

    occupied = { (l["time_slot"]["order_no"] if not l.get("is_break") else None) for l in lessons_payload }
    occupied = { int(o) for o in occupied if isinstance(o, (int,)) or (isinstance(o, str) and o and o.isdigit()) }

    if not slots_map:
        return lessons_payload

    min_ord, max_ord = min(slots_map.keys()), max(slots_map.keys())
    for ord_no in range(min_ord, max_ord + 1):
        if ord_no not in occupied:
            start, end = slots_map.get(ord_no, (None, None))
            lessons_payload.append({
                "is_break": True,
                "from": start or "—",
                "to": end or "—",
            })

    # сортируем: по времени начала/порядку
    def _key(x):
        if x.get("is_break"):
            return (x.get("from") or "00:00", 9999)
        ts = x.get("time_slot") or {}
        return (ts.get("start_time") or "00:00", ts.get("order_no") or 0)
    lessons_payload.sort(key=_key)
    return lessons_payload
