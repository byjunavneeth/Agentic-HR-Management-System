"""Read-only data access for the Database, Documents and Knowledge Graph pages.

* Database page   -> PostgreSQL, through the same read-only role the SQL agent uses
* Documents page  -> (:Document) nodes in Neo4j
* Graph page      -> Neo4j, always in READ mode

Nothing here can change data: Postgres runs in a read-only transaction with a timeout, table and
column names are checked against the real catalog before they are used, and Cypher runs through
run_read().
"""
import datetime as dt
import decimal

import psycopg
from psycopg import sql

from src import config
from src.graph.neo4j_client import run_read

HIDDEN_PROPS = {"embedding", "text"}     # never sent to the browser (huge or internal)
HIDDEN_LABELS = ("Chunk", "Concept")      # internal helper nodes, not shown in the graph
MAX_PAGE_SIZE = 200


def jsonable(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "<binary>"
    return v


# ------------------------------------------------------------------ PostgreSQL
def _conn():
    conn = psycopg.connect(config.pg_conninfo(readonly=True))
    conn.read_only = True
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 10000")
    return conn


def db_tables():
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT c.relname, c.relkind, obj_description(c.oid, 'pg_class')
                       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v')
                       ORDER BY (c.relkind = 'v'), c.relname""")
        tables = {r[0]: {"name": r[0], "kind": "view" if r[1] == "v" else "table", "comment": r[2],
                         "columns": [], "rows": None} for r in cur.fetchall()}
        cur.execute("""SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull,
                              col_description(c.oid, a.attnum)
                       FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                       JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v')
                         AND a.attnum > 0 AND NOT a.attisdropped
                       ORDER BY c.relname, a.attnum""")
        for t, col, typ, nullable, comment in cur.fetchall():
            if t in tables:
                tables[t]["columns"].append({"name": col, "type": typ, "nullable": bool(nullable),
                                             "comment": comment, "pk": False, "fk": None})
        cur.execute("""SELECT con.contype, rel.relname, a.attname, frel.relname, fa.attname
                       FROM pg_constraint con
                       JOIN pg_class rel ON rel.oid = con.conrelid
                       JOIN pg_namespace n ON n.oid = rel.relnamespace
                       JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
                       JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
                       LEFT JOIN pg_class frel ON frel.oid = con.confrelid
                       LEFT JOIN pg_attribute fa ON fa.attrelid = con.confrelid AND fa.attnum = con.confkey[k.ord]
                       WHERE n.nspname = 'public' AND con.contype IN ('p', 'f')""")
        for ctype, t, col, ref_t, ref_c in cur.fetchall():
            for c in tables.get(t, {}).get("columns", []):
                if c["name"] == col:
                    if ctype == "p":
                        c["pk"] = True
                    else:
                        c["fk"] = {"table": ref_t, "column": ref_c}
        for t in tables.values():
            try:
                with conn.transaction():          # savepoint: one failing table cannot break the rest
                    cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("public", t["name"])))
                    t["rows"] = cur.fetchone()[0]
            except Exception:
                t["rows"] = None
    return {"tables": list(tables.values())}


def db_table(name, page=1, size=25, sort=None, direction="asc", q=""):
    meta = {t["name"]: t for t in db_tables()["tables"]}
    if name not in meta:
        raise KeyError(name)
    cols = [c["name"] for c in meta[name]["columns"]]
    size = max(1, min(int(size), MAX_PAGE_SIZE))
    page = max(1, int(page))
    pks = [c["name"] for c in meta[name]["columns"] if c["pk"]]
    order_col = sort if sort in cols else (pks[0] if pks else (cols[0] if cols else None))
    order = sql.SQL("")
    if order_col:
        order = sql.SQL(" ORDER BY {} {} NULLS LAST").format(
            sql.Identifier(order_col), sql.SQL("DESC" if str(direction).lower() == "desc" else "ASC"))
    where, params = sql.SQL(""), []
    q = (q or "").strip()
    if q and cols:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where = sql.SQL(" WHERE ") + sql.SQL(" OR ").join(
            sql.SQL("{}::text ILIKE %s").format(sql.Identifier(c)) for c in cols)
        params = [like] * len(cols)
    table = sql.Identifier("public", name)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(table) + where, params)
        total = cur.fetchone()[0]
        cur.execute(sql.SQL("SELECT * FROM {}").format(table) + where + order +
                    sql.SQL(" LIMIT %s OFFSET %s"), params + [size, (page - 1) * size])
        rows = [[jsonable(v) for v in r] for r in cur.fetchall()]
    return {"name": name, "columns": cols, "rows": rows, "total": total, "page": page, "size": size,
            "sort": order_col, "dir": "desc" if str(direction).lower() == "desc" else "asc"}


# ------------------------------------------------------------------ documents
def docs_list():
    rows = run_read("""MATCH (d:Document)
                       OPTIONAL MATCH (d)-[:ABOUT]->(s)
                       RETURN d.doc_id AS id, d.type AS type, d.title AS title, d.path AS path,
                              size(coalesce(d.text, '')) AS chars,
                              elementId(s) AS about_id, labels(s)[0] AS about_label,
                              coalesce(s.name, s.title) AS about_name
                       ORDER BY d.type, d.doc_id""")
    return {"documents": rows}


def doc_get(doc_id):
    rows = run_read("""MATCH (d:Document {doc_id: $id})
                       OPTIONAL MATCH (d)-[:ABOUT]->(s)
                       OPTIONAL MATCH (d)-[:MENTIONS]->(m)
                       RETURN d.doc_id AS id, d.type AS type, d.title AS title, d.path AS path, d.text AS text,
                              elementId(s) AS about_id, labels(s)[0] AS about_label,
                              coalesce(s.name, s.title) AS about_name,
                              collect(DISTINCT CASE WHEN m IS NULL THEN NULL ELSE
                                  {id: elementId(m), label: labels(m)[0], name: coalesce(m.name, m.title)} END) AS mentions""",
                    id=doc_id)
    if not rows:
        raise KeyError(doc_id)
    r = rows[0]
    r["mentions"] = [m for m in r["mentions"] if m and m.get("name")][:40]
    return r


# ------------------------------------------------------------------ knowledge graph
def _node(node_id, label, props):
    props = props or {}
    name = props.get("name") or props.get("title") or props.get("doc_id") or props.get("text") or label
    clean = {}
    for k, v in props.items():
        if k in HIDDEN_PROPS:
            continue
        v = jsonable(v)
        if isinstance(v, str) and len(v) > 220:
            v = v[:220] + "..."
        if isinstance(v, list):
            v = [jsonable(x) for x in v][:20]
        clean[k] = v
    return {"id": node_id, "label": label, "name": str(name), "props": clean}


def graph_stats():
    labels = run_read("""MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $hidden)
                         RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC""", hidden=list(HIDDEN_LABELS))
    rels = run_read("MATCH (a)-[r]->(b) WHERE NOT any(l IN labels(a) + labels(b) WHERE l IN $hidden) "
                    "RETURN type(r) AS type, count(*) AS n ORDER BY n DESC", hidden=list(HIDDEN_LABELS))
    return {"labels": labels, "relationships": rels,
            "nodes": sum(x["n"] for x in labels), "edges": sum(x["n"] for x in rels)}


def graph_overview(labels, limit=160):
    limit = max(20, min(int(limit), 400))
    labels = [l for l in labels if l and l not in HIDDEN_LABELS][:12] or ["Department", "Project", "Client", "Skill"]
    per = max(8, limit // len(labels))
    rows = run_read("""UNWIND $labels AS l
                       CALL { WITH l MATCH (n) WHERE l IN labels(n) RETURN n LIMIT $per }
                       WITH collect(n) AS ns
                       UNWIND ns AS a
                       OPTIONAL MATCH (a)-[r]->(b) WHERE b IN ns
                       RETURN elementId(a) AS id, labels(a)[0] AS label, properties(a) AS props,
                              collect(CASE WHEN r IS NULL THEN NULL ELSE
                                  {id: elementId(r), source: elementId(a), target: elementId(b), type: type(r)} END) AS edges""",
                    labels=labels, per=per)
    nodes, edges = [], {}
    for r in rows:
        nodes.append(_node(r["id"], r["label"], r["props"]))
        for e in r["edges"]:
            if e:
                edges[e["id"]] = e
    return {"nodes": nodes, "edges": list(edges.values())}


def graph_search(q):
    q = (q or "").strip()
    if len(q) < 2:
        return {"results": []}
    rows = run_read("""MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $hidden)
                         AND toLower(coalesce(n.name, n.title, n.doc_id, '')) CONTAINS toLower($q)
                       RETURN elementId(n) AS id, labels(n)[0] AS label,
                              coalesce(n.name, n.title, n.doc_id) AS name LIMIT 15""",
                    hidden=list(HIDDEN_LABELS), q=q)
    return {"results": rows}


def graph_expand(node_id, limit=80):
    centre = run_read("MATCH (n) WHERE elementId(n) = $id RETURN elementId(n) AS id, labels(n)[0] AS label, "
                      "properties(n) AS props", id=node_id)
    if not centre:
        raise KeyError(node_id)
    rows = run_read("""MATCH (n) WHERE elementId(n) = $id
                       MATCH (n)-[r]-(m) WHERE NOT any(l IN labels(m) WHERE l IN $hidden)
                       RETURN elementId(m) AS id, labels(m)[0] AS label, properties(m) AS props,
                              elementId(r) AS rid, type(r) AS type,
                              elementId(startNode(r)) AS s, elementId(endNode(r)) AS t
                       LIMIT $limit""", id=node_id, hidden=list(HIDDEN_LABELS), limit=int(limit))
    nodes = {centre[0]["id"]: _node(centre[0]["id"], centre[0]["label"], centre[0]["props"])}
    edges = {}
    for r in rows:
        nodes[r["id"]] = _node(r["id"], r["label"], r["props"])
        edges[r["rid"]] = {"id": r["rid"], "source": r["s"], "target": r["t"], "type": r["type"]}
    return {"center": node_id, "nodes": list(nodes.values()), "edges": list(edges.values())}
