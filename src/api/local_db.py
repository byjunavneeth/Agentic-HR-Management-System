"""Local copy of the SQL tables for the Database page.

The Database page never talks to the online PostgreSQL server.  It reads a SQLite file stored on
this computer (data/local_snapshot.sqlite).  The file is created once from PostgreSQL, using the
read-only role, when you press "Create local copy" on the page or run:

    python -m src.api.local_db

and can be refreshed the same way whenever the online data changes.
"""
import datetime as dt
import json
import os
import sqlite3
import sys
import threading
from pathlib import Path

MAX_PAGE_SIZE = 200
MAX_ROWS_PER_TABLE = 100_000
_build_lock = threading.Lock()


def _root():
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "src" / "pipeline.py").exists():
            return p
    return here


def path():
    return Path(os.getenv("HR_LOCAL_DB") or (_root() / "data" / "local_snapshot.sqlite"))


class NoSnapshot(Exception):
    pass


def _open():
    p = path()
    if not p.exists():
        raise NoSnapshot("There is no local copy of the database yet.")
    return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)


def _qi(name):
    return '"' + str(name).replace('"', '""') + '"'


def info():
    p = path()
    if not p.exists():
        return {"exists": False, "path": str(p)}
    conn = _open()
    try:
        meta = dict(conn.execute("SELECT key, value FROM _info").fetchall())
    finally:
        conn.close()
    return {"exists": True, "path": str(p), "built_at": meta.get("built_at"), "source": meta.get("source"),
            "size_kb": round(p.stat().st_size / 1024)}


# ------------------------------------------------------------------ build (the only online step)
def build():
    """Copy every table and view from PostgreSQL (read-only role) into the local SQLite file."""
    try:
        from . import real_data
    except ImportError:
        import real_data
    from psycopg import sql

    meta = real_data.db_tables()["tables"]
    dst = path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".building")
    with _build_lock:
        if tmp.exists():
            tmp.unlink()
        conn = sqlite3.connect(tmp)
        try:
            conn.execute("CREATE TABLE _meta (name TEXT PRIMARY KEY, json TEXT NOT NULL)")
            conn.execute("CREATE TABLE _info (key TEXT PRIMARY KEY, value TEXT)")
            with real_data._conn() as pg, pg.cursor() as cur:
                for t in meta:
                    cols = [c["name"] for c in t["columns"]]
                    if not cols:
                        continue
                    conn.execute("CREATE TABLE %s (%s)" % (_qi(t["name"]), ", ".join(_qi(c) for c in cols)))
                    insert = "INSERT INTO %s VALUES (%s)" % (_qi(t["name"]), ",".join("?" * len(cols)))
                    cur.execute(sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier("public", t["name"])),
                                [MAX_ROWS_PER_TABLE])
                    batch = []
                    for r in cur.fetchall():
                        row = []
                        for v in r:
                            v = real_data.jsonable(v)
                            row.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
                        batch.append(row)
                        if len(batch) >= 2000:
                            conn.executemany(insert, batch)
                            batch = []
                    if batch:
                        conn.executemany(insert, batch)
                    n = conn.execute("SELECT count(*) FROM %s" % _qi(t["name"])).fetchone()[0]
                    conn.execute("INSERT INTO _meta VALUES (?, ?)", (t["name"], json.dumps({**t, "rows": n})))
            conn.execute("INSERT INTO _info VALUES ('built_at', ?)", (dt.datetime.now().isoformat(timespec="seconds"),))
            conn.execute("INSERT INTO _info VALUES ('source', 'PostgreSQL (read-only role)')")
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp, dst)
    return info()


# ------------------------------------------------------------------ reads (local file only)
def _meta(conn):
    return {name: json.loads(js) for name, js in conn.execute("SELECT name, json FROM _meta ORDER BY rowid")}


def db_info():
    return info()


def db_tables():
    conn = _open()
    try:
        tables = list(_meta(conn).values())
        tables.sort(key=lambda t: (t["kind"] == "view", t["name"]))
        inf = dict(conn.execute("SELECT key, value FROM _info").fetchall())
    finally:
        conn.close()
    return {"tables": tables, "snapshot": {"built_at": inf.get("built_at"), "source": inf.get("source")}}


def db_table(name, page=1, size=25, sort=None, direction="asc", q=""):
    conn = _open()
    try:
        meta = _meta(conn)
        if name not in meta:
            raise KeyError(name)
        cols = [c["name"] for c in meta[name]["columns"]]
        size = max(1, min(int(size), MAX_PAGE_SIZE))
        page = max(1, int(page))
        pks = [c["name"] for c in meta[name]["columns"] if c["pk"]]
        order_col = sort if sort in cols else (pks[0] if pks else (cols[0] if cols else None))
        desc = str(direction).lower() == "desc"
        order = ""
        if order_col:
            order = " ORDER BY (%s IS NULL), %s %s" % (_qi(order_col), _qi(order_col), "DESC" if desc else "ASC")
        where, params = "", []
        q = (q or "").strip()
        if q and cols:
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where = " WHERE " + " OR ".join("CAST(%s AS TEXT) LIKE ? ESCAPE '\\'" % _qi(c) for c in cols)
            params = [like] * len(cols)
        t = _qi(name)
        total = conn.execute("SELECT count(*) FROM " + t + where, params).fetchone()[0]
        rows = [list(r) for r in conn.execute("SELECT * FROM " + t + where + order + " LIMIT ? OFFSET ?",
                                              params + [size, (page - 1) * size])]
    finally:
        conn.close()
    return {"name": name, "columns": cols, "rows": rows, "total": total, "page": page, "size": size,
            "sort": order_col, "dir": "desc" if desc else "asc"}


if __name__ == "__main__":
    sys.path.insert(0, str(_root()))
    print("Copying tables from PostgreSQL (read-only role) into the local file ...")
    print(build())
