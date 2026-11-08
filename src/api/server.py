"""
Web front end for the HR Intelligence Assistant.

A small Flask server that serves one web page (api/static/index.html) and exposes the
pipeline through a JSON endpoint.  The page never talks to the databases or the LLM
itself; it only calls  POST /api/ask  and shows what src.pipeline.answer() returns.

Run from the project root (the folder that contains src/ and .env):

    pip install flask
    python -m src.api.server          ->  http://127.0.0.1:5000   (if this folder is src/api)
    python -m api.server              ->  http://127.0.0.1:5000   (if this folder is next to src/)

Optional settings (environment variables or .env):
    APP_PASSWORD   if set, users must sign in with this password first
    SECRET_KEY     session signing key (set a fixed value in real use)
    HR_MOCK=1      answer from two saved sample outputs, without databases or LLM
    PORT           port to listen on (default 5000)
"""
import hmac
import importlib
import json
import os
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
# project root = the folder that contains src/ (works for api/ next to src/ and for src/api/)
ROOT = next((p for p in [HERE, *HERE.parents] if (p / "src" / "pipeline.py").exists()), HERE.parent)
sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, request, send_from_directory, session  # noqa: E402

try:                                    # reuse the project's .env loading when it is there
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.json.sort_keys = False
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(24)
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
MOCK = os.getenv("HR_MOCK", "") == "1"
MAX_QUESTION_CHARS = 500

# The pipeline keeps a global LLM call counter, so questions are answered one at a time.
_lock = threading.Lock()
_pipeline = None

EXAMPLES = [
    {"q": "How many active employees does each department have?", "tag": "Database"},
    {"q": "Which projects are running into problems with an external vendor's API, and who leads them?", "tag": "Graph"},
    {"q": "How many days of paternity leave do employees get, and is it paid?", "tag": "Documents"},
    {"q": "Is Arya Zachariah eligible for promotion under our appraisal policy?", "tag": "Database + Documents"},
    {"q": "Who mentors people in the Data Science team, and how are their mentees performing?", "tag": "Graph"},
]


def load_pipeline():
    """Import the pipeline on first use, so the page itself opens even if a service is down."""
    global _pipeline
    if _pipeline is None:
        from src import llm, pipeline
        _pipeline = (pipeline, llm)
    return _pipeline


def _mock():
    try:
        from .mock_data import mock_answer          # python -m src.api.server
    except ImportError:
        from mock_data import mock_answer           # python src/api/server.py
    return mock_answer


def authorised():
    return (not APP_PASSWORD) or session.get("ok") is True


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/status")
def status():
    return jsonify({"mock": MOCK, "login_required": bool(APP_PASSWORD), "signed_in": authorised()})


@app.post("/api/login")
def login():
    pw = (request.get_json(silent=True) or {}).get("password", "")
    if APP_PASSWORD and hmac.compare_digest(str(pw), APP_PASSWORD):
        session["ok"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Wrong password."}), 401


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


def _module(name):
    try:
        return importlib.import_module("." + name, __package__) if __package__ else importlib.import_module(name)
    except ImportError:
        return importlib.import_module(name)


def _respond(fn):
    """Run one data call and turn every failure into a clear JSON message."""
    if not authorised():
        return jsonify({"error": "Please sign in first.", "kind": "auth"}), 401
    try:
        return app.response_class(json.dumps(fn(), default=str), mimetype="application/json")
    except KeyError:
        return jsonify({"error": "Not found.", "kind": "missing"}), 404
    except Exception as e:
        if type(e).__name__ == "NoSnapshot":
            return jsonify({"error": str(e), "kind": "nosnapshot"}), 409
        return jsonify({"error": f"{type(e).__name__}: {str(e)[:240]}", "kind": "failure"}), 500


def _call(fn_name, *args):
    """Documents and Knowledge Graph pages: Neo4j in real mode, saved samples in mock mode."""
    return _respond(lambda: getattr(_module("mock_data" if MOCK else "real_data"), ("mock_" if MOCK else "") + fn_name)(*args))


def _local(fn_name, *args):
    """Database page: ALWAYS the local SQLite copy (never the online server), samples in mock mode."""
    return _respond(lambda: getattr(_module("mock_data" if MOCK else "local_db"), ("mock_" if MOCK else "") + fn_name)(*args))


@app.get("/api/db/info")
def api_db_info():
    return _local("db_info")


@app.post("/api/db/snapshot")
def api_db_snapshot():
    """The one step that contacts the online PostgreSQL (read-only role): refresh the local copy."""
    return _respond(lambda: _module("mock_data").mock_db_info() if MOCK else _module("local_db").build())


@app.get("/api/db/tables")
def api_db_tables():
    return _local("db_tables")


@app.get("/api/db/table/<name>")
def api_db_table(name):
    a = request.args
    try:
        page, size = int(a.get("page", 1)), int(a.get("size", 25))
    except ValueError:
        return jsonify({"error": "Bad page number.", "kind": "input"}), 400
    return _local("db_table", name, page, size, a.get("sort"), a.get("dir", "asc"), a.get("q", ""))


@app.get("/api/docs")
def api_docs():
    return _call("docs_list")


@app.get("/api/docs/<doc_id>")
def api_doc(doc_id):
    return _call("doc_get", doc_id)


@app.get("/api/graph/stats")
def api_graph_stats():
    return _call("graph_stats")


@app.get("/api/graph/overview")
def api_graph_overview():
    labels = [x for x in request.args.get("labels", "").split(",") if x]
    try:
        limit = int(request.args.get("limit", 160))
    except ValueError:
        limit = 160
    return _call("graph_overview", labels, limit)


@app.get("/api/graph/search")
def api_graph_search():
    return _call("graph_search", request.args.get("q", ""))


@app.get("/api/graph/expand")
def api_graph_expand():
    return _call("graph_expand", request.args.get("id", ""))


@app.post("/api/ask")
def ask():
    if not authorised():
        return jsonify({"error": "Please sign in first.", "kind": "auth"}), 401
    question = ((request.get_json(silent=True) or {}).get("question") or "").strip()
    if not question:
        return jsonify({"error": "Please type a question.", "kind": "input"}), 400
    if len(question) > MAX_QUESTION_CHARS:
        return jsonify({"error": f"Please keep the question under {MAX_QUESTION_CHARS} characters.",
                        "kind": "input"}), 400

    blocked = _module("guard").check(question)
    if blocked:                         # unauthorised or off-topic: custom reply, no pipeline or LLM call
        return jsonify(blocked)

    if MOCK:
        mock_answer = _mock()
        return jsonify(mock_answer(question))

    try:
        pipeline, llm = load_pipeline()
    except Exception as e:              # missing package, wrong .env, database not reachable ...
        return jsonify({"error": f"The assistant could not start: {type(e).__name__}: {str(e)[:200]}",
                        "kind": "startup"}), 503
    try:
        with _lock:
            result = pipeline.answer(question, verbose=False)
    except llm.DailyLimitReached as e:
        return jsonify({"error": f"The language-model daily limit has been reached. {str(e)[:200]}",
                        "kind": "limit"}), 429
    except Exception as e:
        return jsonify({"error": f"Something went wrong while answering: {type(e).__name__}: {str(e)[:200]}",
                        "kind": "failure"}), 500
    # default=str turns dates and decimals from the database into text
    return app.response_class(json.dumps(result, default=str), mimetype="application/json")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"HR Intelligence Assistant -> http://127.0.0.1:{port}" + ("   [MOCK MODE]" if MOCK else ""))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
