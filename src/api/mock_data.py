"""Saved sample outputs, used only when HR_MOCK=1 (front-end checks without databases or LLM).
The two answers are based on real pipeline outputs from the Review 1 demo run; the evidence rows shown with them are illustrative."""

_SAMPLES = {
    "is arya zachariah eligible for promotion under our appraisal policy?": {
        "question": "Is Arya Zachariah eligible for promotion under our appraisal policy?",
        "analysis": {"route": "sql+documents", "intent": "policy_check", "doc_classes": ["policy"]},
        "answer": ("Arya Zachariah is **not eligible** for promotion.\n"
                   "- The appraisal policy requires an average rating of 4.0 or higher and at least 18 months "
                   "in the current designation [Doc: policy].\n"
                   "- Arya's latest rating is 2.2, which is below the threshold [SQL]."),
        "sources_used": ["SQL", "Doc"], "confidence": "high", "follow_up_questions": [],
        "context": {"documents": [{"doc_id": "policy", "type": "policy",
                                   "text": "Promotion requires an average rating of at least 4.0 and a minimum of 18 months in the current designation."}]},
        "grounding": {"checked": 4, "unsupported": [], "grounded_pct": 100},
        "timings": {}, "total_seconds": 26.5, "llm_calls": 4,
    },
    "which projects are running into problems with an external vendor's api, and who leads them?": {
        "question": "Which projects are running into problems with an external vendor's API, and who leads them?",
        "analysis": {"route": "graph", "intent": "relationship", "doc_classes": []},
        "answer": ("Five projects report problems with a third-party API [Graph]:\n"
                   "- Nimbus Mobile App: Aadhya Ramakrishnan\n- Vega Dashboard: Henry Krish\n"
                   "- Vega Migration: Kashvi Lanka\n- Zenith Data Lake: Reyansh Gupta\n"
                   "- Zenith Migration: Januja Devi"),
        "sources_used": ["Graph"], "confidence": "high", "follow_up_questions": [],
        "context": {"graph": {"query": "", "error": None, "row_count": 5, "truncated": False,
                              "rows": [{"project": "Nimbus Mobile App", "lead": "Aadhya Ramakrishnan"},
                                       {"project": "Vega Dashboard", "lead": "Henry Krish"},
                                       {"project": "Vega Migration", "lead": "Kashvi Lanka"},
                                       {"project": "Zenith Data Lake", "lead": "Reyansh Gupta"},
                                       {"project": "Zenith Migration", "lead": "Januja Devi"}],
                              "related_facts": []}},
        "grounding": {"checked": 10, "unsupported": [], "grounded_pct": 100},
        "timings": {}, "total_seconds": 13.5, "llm_calls": 3,
    },
}


def mock_answer(question):
    r = _SAMPLES.get(" ".join(question.lower().split()))
    if r:
        return r
    return {"question": question, "analysis": {"route": "none", "intent": "mock"},
            "answer": ("Mock mode is on, so only the two saved sample questions can be answered "
                       "(the promotion question and the vendor-API question). "
                       "Start the server without HR_MOCK=1 to use the real system."),
            "sources_used": [], "confidence": "low", "follow_up_questions": [], "context": {},
            "grounding": None, "timings": {}, "total_seconds": 0, "llm_calls": 0}


# ======================================================================================
# Sample data for the Database, Documents and Knowledge Graph pages in mock mode.
# Invented for layout checks only; it is NOT the project's data.
# ======================================================================================
import datetime as _dt
import random as _random

_R = _random.Random(7)
_DEPTS = [(1, "Engineering", "Bengaluru"), (2, "Data Science", "Kochi"), (3, "Product", "Pune"),
          (4, "Human Resources", "Kochi"), (5, "Finance", "Chennai"), (6, "Sales", "Mumbai")]
_FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vihaan", "Anaya", "Arjun", "Sara", "Neel", "Tara",
          "Dev", "Riya", "Kiran", "Zoya", "Ishan", "Nisha", "Yash", "Pooja"]
_LAST = ["Nair", "Menon", "Iyer", "Pillai", "Sharma", "Reddy", "Das", "Varma", "Joshi", "Kurian"]
_DESIG = ["Software Engineer", "Senior Engineer", "Data Analyst", "Product Manager", "HR Executive", "Accountant",
          "Sales Associate", "Team Lead"]
_SKILLS = ["Python", "SQL", "Machine Learning", "React", "Leadership", "Communication", "Cloud", "Negotiation"]
_PROJ = ["Nimbus Mobile App", "Vega Dashboard", "Zenith Data Lake", "Orion Portal", "Atlas Migration", "Helix CRM"]
_EMP = []
for i in range(1, 41):
    f, l = _R.choice(_FIRST), _R.choice(_LAST)
    _EMP.append({"emp_id": 1000 + i, "first_name": f, "last_name": l,
                 "email": f"{f}.{l}@example.com".lower(), "designation": _R.choice(_DESIG),
                 "dept_id": _R.choice(_DEPTS)[0], "status": _R.choice(["Active"] * 8 + ["On leave", "Resigned"]),
                 "hire_date": (_dt.date(2019, 1, 1) + _dt.timedelta(days=_R.randint(0, 2400))).isoformat(),
                 "experience_years": round(_R.uniform(0.5, 14), 1), "monthly_salary": _R.randrange(32000, 210000, 500)})
_PROJECTS = [{"project_id": 200 + i, "name": n, "client": _R.choice(["Acme Corp", "Globex", "Initech", "Umbrella"]),
              "dept_id": _R.choice(_DEPTS)[0], "status": _R.choice(["Active", "Completed", "On hold"]),
              "start_date": (_dt.date(2024, 1, 1) + _dt.timedelta(days=_R.randint(0, 600))).isoformat()}
             for i, n in enumerate(_PROJ, 1)]

_TABLES = {
    "departments": ("Company departments with their office location",
                    [("dept_id", "integer", True, None), ("name", "text", False, None), ("location", "text", False, None)],
                    [[d[0], d[1], d[2]] for d in _DEPTS]),
    "employees": ("One row per employee, including designation and department",
                  [("emp_id", "integer", True, None), ("first_name", "text", False, None), ("last_name", "text", False, None),
                   ("email", "text", False, None), ("designation", "text", False, None),
                   ("dept_id", "integer", False, {"table": "departments", "column": "dept_id"}),
                   ("status", "text", False, None), ("hire_date", "date", False, None),
                   ("experience_years", "numeric(4,1)", False, None), ("monthly_salary", "integer", False, None)],
                  [[e[k] for k in ("emp_id", "first_name", "last_name", "email", "designation", "dept_id", "status",
                                   "hire_date", "experience_years", "monthly_salary")] for e in _EMP]),
    "projects": ("Client and internal projects",
                 [("project_id", "integer", True, None), ("name", "text", False, None), ("client", "text", False, None),
                  ("dept_id", "integer", False, {"table": "departments", "column": "dept_id"}),
                  ("status", "text", False, None), ("start_date", "date", False, None)],
                 [[p[k] for k in ("project_id", "name", "client", "dept_id", "status", "start_date")] for p in _PROJECTS]),
}


def mock_db_tables():
    out = []
    for name, (comment, cols, rows) in _TABLES.items():
        out.append({"name": name, "kind": "table", "comment": comment, "rows": len(rows),
                    "columns": [{"name": c[0], "type": c[1], "nullable": not c[2], "comment": None, "pk": c[2], "fk": c[3]}
                                for c in cols]})
    return {"tables": out, "snapshot": {"built_at": None, "source": "Sample data (mock mode)"}}


def mock_db_info():
    return {"exists": True, "built_at": None, "source": "Sample data (mock mode)"}


def mock_db_table(name, page=1, size=25, sort=None, direction="asc", q=""):
    if name not in _TABLES:
        raise KeyError(name)
    _, cols, rows = _TABLES[name]
    names = [c[0] for c in cols]
    q = (q or "").strip().lower()
    if q:
        rows = [r for r in rows if any(q in str(v).lower() for v in r)]
    key = sort if sort in names else names[0]
    idx = names.index(key)
    rows = sorted(rows, key=lambda r: (r[idx] is None, r[idx]), reverse=str(direction).lower() == "desc")
    size = max(1, min(int(size), 200)); page = max(1, int(page))
    return {"name": name, "columns": names, "rows": rows[(page - 1) * size: page * size], "total": len(rows),
            "page": page, "size": size, "sort": key, "dir": "desc" if str(direction).lower() == "desc" else "asc"}


_DOCS = []
for _e in _EMP[:14]:
    _DOCS.append({"id": f"review_{_e['emp_id']}", "type": "review", "title": f"Performance review: {_e['first_name']} {_e['last_name']}",
                  "path": f"reviews/review_{_e['emp_id']}.txt", "about_label": "Employee",
                  "about_name": f"{_e['first_name']} {_e['last_name']}", "about_id": f"e{_e['emp_id']}",
                  "text": (f"# Performance review: {_e['first_name']} {_e['last_name']}\n\nPeriod: 2025-H2\nRating: 4.1\n\n"
                           "## Summary\nDelivers reliable work and communicates clearly with the team. Mentors newer colleagues.\n\n"
                           "## Areas to improve\nTake on more cross-team planning.\n")})
for _p in _PROJECTS:
    _DOCS.append({"id": f"project_{_p['project_id']}", "type": "project", "title": f"Project report: {_p['name']}",
                  "path": f"projects/project_{_p['project_id']}.txt", "about_label": "Project", "about_name": _p["name"],
                  "about_id": f"p{_p['project_id']}",
                  "text": f"# Project report: {_p['name']}\n\nClient: {_p['client']}\nStatus: {_p['status']}\n\n## Risks\nIntegration delays with a third-party API.\n"})
for _i, _t in enumerate(["Leave policy", "Appraisal and promotion policy", "Code of conduct"], 1):
    _DOCS.append({"id": f"policy_{_i}", "type": "policy", "title": _t, "path": f"policies/policy_{_i}.txt",
                  "about_label": None, "about_name": None, "about_id": None,
                  "text": f"# {_t}\n\n## 1. Purpose\nThis policy applies to all employees.\n\n## 2. Rules\nSample text for layout checks.\n"})
for _i in range(1, 5):
    _DOCS.append({"id": f"resume_C{_i:03d}", "type": "resume", "title": f"Candidate {_i} resume", "path": f"resumes/resume_C{_i:03d}.txt",
                  "about_label": "Candidate", "about_name": f"Candidate {_i}", "about_id": f"c{_i}",
                  "text": f"CANDIDATE {_i}\nApplying for: Data Analyst\n\nSKILLS\n- Python\n- SQL\n\nACHIEVEMENTS\n- Won a state-level hackathon\n"})


def mock_docs_list():
    return {"documents": [{k: d[k] for k in ("id", "type", "title", "path", "about_id", "about_label", "about_name")}
                          | {"chars": len(d["text"])} for d in _DOCS]}


def mock_doc_get(doc_id):
    d = next((x for x in _DOCS if x["id"] == doc_id), None)
    if not d:
        raise KeyError(doc_id)
    return {**d, "mentions": [{"id": "s1", "label": "Skill", "name": "Python"}, {"id": "s2", "label": "Skill", "name": "SQL"}]}


# ---- graph
_G_NODES, _G_EDGES = {}, []


def _gn(i, label, name, **props):
    _G_NODES[i] = {"id": i, "label": label, "name": name, "props": {"name": name, **props}}


for _d in _DEPTS:
    _gn(f"d{_d[0]}", "Department", _d[1], location=_d[2])
for _s in _SKILLS:
    _gn("s_" + _s, "Skill", _s)
for _p in _PROJECTS:
    _gn(f"p{_p['project_id']}", "Project", _p["name"], status=_p["status"])
    _G_EDGES.append({"id": f"ed_p{_p['project_id']}", "source": f"p{_p['project_id']}", "target": f"d{_p['dept_id']}", "type": "OWNED_BY"})
for _e in _EMP:
    _gn(f"e{_e['emp_id']}", "Employee", f"{_e['first_name']} {_e['last_name']}", designation=_e["designation"], status=_e["status"])
    _G_EDGES.append({"id": f"ew{_e['emp_id']}", "source": f"e{_e['emp_id']}", "target": f"d{_e['dept_id']}", "type": "WORKS_IN"})
    for _k in _R.sample(_SKILLS, 2):
        _G_EDGES.append({"id": f"es{_e['emp_id']}{_k}", "source": f"e{_e['emp_id']}", "target": "s_" + _k, "type": "HAS_SKILL"})
    _G_EDGES.append({"id": f"ep{_e['emp_id']}", "source": f"e{_e['emp_id']}", "target": f"p{_R.choice(_PROJECTS)['project_id']}", "type": "WORKED_ON"})
for _c in range(1, 5):
    _gn(f"c{_c}", "Candidate", f"Candidate {_c}")
    _G_EDGES.append({"id": f"cs{_c}", "source": f"c{_c}", "target": "s_Python", "type": "HAS_SKILL"})


def mock_graph_stats():
    from collections import Counter
    lc = Counter(n["label"] for n in _G_NODES.values()); rc = Counter(e["type"] for e in _G_EDGES)
    return {"labels": [{"label": k, "n": v} for k, v in lc.most_common()],
            "relationships": [{"type": k, "n": v} for k, v in rc.most_common()],
            "nodes": len(_G_NODES), "edges": len(_G_EDGES)}


def mock_graph_overview(labels, limit=160):
    labels = labels or ["Department", "Project", "Skill"]
    per = max(8, int(limit) // len(labels)); ids = set(); nodes = []
    for lab in labels:
        for n in [x for x in _G_NODES.values() if x["label"] == lab][:per]:
            ids.add(n["id"]); nodes.append(n)
    return {"nodes": nodes, "edges": [e for e in _G_EDGES if e["source"] in ids and e["target"] in ids]}


def mock_graph_search(q):
    q = (q or "").lower().strip()
    return {"results": [{"id": n["id"], "label": n["label"], "name": n["name"]} for n in _G_NODES.values()
                        if len(q) >= 2 and q in n["name"].lower()][:15]}


def mock_graph_expand(node_id, limit=80):
    if node_id not in _G_NODES:
        raise KeyError(node_id)
    es = [e for e in _G_EDGES if node_id in (e["source"], e["target"])][:limit]
    ids = {node_id} | {e["source"] for e in es} | {e["target"] for e in es}
    return {"center": node_id, "nodes": [_G_NODES[i] for i in ids], "edges": es}
