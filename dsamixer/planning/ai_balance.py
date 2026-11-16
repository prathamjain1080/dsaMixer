"""Preview and atomically apply a quota-aware redistribution of existing AI cards."""
import hashlib
import json
from datetime import timedelta

from ..core import config, db
from . import planner


def quotas(conn, cfg, dates):
    saved = db.get_setting(conn, "ai_balance_quotas", {})
    return {day: saved.get(day, sum(t["minutes"] for t in
            config.ai_template(cfg).get(planner.weekday_key(day), []))) for day in dates}


def preview(conn, day, overrides=None):
    start = planner.d(day)
    monday = start - timedelta(days=start.weekday())
    dates = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    cfg = config.load(conn)
    caps = quotas(conn, cfg, dates)
    for key, value in (overrides or {}).items():
        if key not in dates or type(value) is not int or not 0 <= value <= 1440:
            raise ValueError("Quotas must be whole minutes from 0 to 1440 for dates in this week.")
        caps[key] = value
    tickets = db.rows(conn.execute(
        "SELECT * FROM tickets WHERE date BETWEEN ? AND ? ORDER BY date,position,id", (dates[0], dates[-1])))
    days = db.rows(conn.execute("SELECT * FROM days WHERE date BETWEEN ? AND ?", (dates[0], dates[-1])))
    closed = {r["date"] for r in days if r["closed_at"]}
    eligible = [dt for dt in dates if dt >= planner.today() and dt >= cfg["start_date"] and dt not in closed]
    suppressed = db.get_setting(conn, "ai_balance_suppressed", {})
    planned = {r["date"] for r in days if r["planned_at"]}
    # Reserve not-yet-created recurring work, so an unopened day never looks artificially empty.
    reserved = dict.fromkeys(dates, 0)
    for dt in eligible:
        if dt in planned or planner.has_ai_plan(conn, dt):
            continue
        titles = {t["title"] for t in tickets if t["date"] == dt}
        for item in config.ai_template(cfg).get(planner.weekday_key(dt), []):
            if item["title"] not in titles and item["title"] not in suppressed.get(dt, []):
                reserved[dt] += item["minutes"]
    before = {dt: reserved[dt] + sum(t["est_minutes"] for t in tickets
              if t["date"] == dt and t["kind"] == "ai" and t["status"] != "skipped") for dt in dates}
    overloaded = {dt for dt in eligible if before[dt] > caps[dt]}
    movable = [t for t in tickets if t["date"] in overloaded and t["kind"] == "ai"
               and t["status"] == "todo" and not t["minutes_spent"] and not t["done_at"]
               and "class" not in t["title"].lower()]
    after = before.copy()
    for t in movable:
        after[t["date"]] -= t["est_minutes"]
    moves = []
    for t in sorted(movable, key=lambda t: (-t["est_minutes"], t["date"], t["position"], t["id"])):
        targets = [dt for dt in eligible if caps[dt] > 0]
        if not targets:
            targets = [t["date"]]
        # Minimize overflow first, then balance the fraction of each day's quota used.
        dest = min(targets, key=lambda dt: (
            max(0, after[dt] + t["est_minutes"] - caps[dt]) - max(0, after[dt] - caps[dt]),
            (after[dt] + t["est_minutes"]) / max(caps[dt], 1), dt != t["date"], dt))
        after[dest] += t["est_minutes"]
        if dest != t["date"]:
            moves.append({"id": t["id"], "title": t["title"], "minutes": t["est_minutes"],
                          "from": t["date"], "to": dest, "carried": t["carried"]})
    state = [tickets, days, cfg, caps, suppressed, reserved, planner.today()]
    token = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return {"start": dates[0], "end": dates[-1], "token": token, "quotas": caps, "moves": moves,
            "days": [{"date": dt, "quota": caps[dt], "before": before[dt], "after": after[dt],
                      "reserved": reserved[dt], "eligible": dt in eligible,
                      "over": max(0, after[dt] - caps[dt])} for dt in dates]}


def apply(conn, day, overrides, token):
    try:
        # Hold the board stable between validating the preview and committing all moves.
        if getattr(conn, "is_pg", False):
            conn.execute("LOCK TABLE tickets, days, settings, ai_week_plans IN SHARE ROW EXCLUSIVE MODE")
        else:
            conn.execute("BEGIN IMMEDIATE")
        result = preview(conn, day, overrides)
        if result["token"] != token:
            raise ValueError("The board changed. Preview the balance again before applying.")
        cfg = config.load(conn)
        suppressed = db.get_setting(conn, "ai_balance_suppressed", {})
        for move in result["moves"]:
            # No per-card commits: the entire preview applies or none of it does.
            sprint = planner.ensure_sprint(conn, cfg, move["to"])
            pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM tickets WHERE date=?", (move["to"],)).fetchone()[0]
            conn.execute("UPDATE tickets SET date=?,sprint_id=?,position=? WHERE id=?",
                         (move["to"], sprint, pos, move["id"]))
            titles = suppressed.setdefault(move["from"], [])
            if move["title"] not in titles:
                titles.append(move["title"])
        saved = db.get_setting(conn, "ai_balance_quotas", {})
        saved.update({r["date"]: r["quota"] for r in result["days"] if r["eligible"]})
        db.set_setting(conn, "ai_balance_quotas", saved)
        db.set_setting(conn, "ai_balance_suppressed", suppressed)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
