# HR Assistant web interface

The Flask app is a small web UI for the main `src.pipeline` project. The browser talks to Flask; it does not connect directly to PostgreSQL, Neo4j or Groq.

## Run locally

From the repository root:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Windows: copy .env.example .env
python -m src.api.server
```

Open <http://127.0.0.1:5000>.

For a UI-only preview that uses saved mock responses and does not need databases or a Groq key, set `HR_MOCK=1` in `.env`. For real answers, configure PostgreSQL, Neo4j and Groq as described in the root README.

## Main files

- `server.py` — Flask routes and session handling (`POST /api/ask`, plus read-only database/document/graph endpoints).
- `static/index.html` — the single-page interface; no frontend build step is needed.
- `real_data.py` — read-only access to PostgreSQL and Neo4j for the data explorer pages.
- `local_db.py` — builds a local SQLite snapshot for the Database page.
- `guard.py` — basic question screening before the LLM pipeline is called.
- `mock_data.py` — saved sample responses for `HR_MOCK=1`.

## Useful environment variables

| Variable | Purpose |
|---|---|
| `HR_MOCK=1` | Use sample responses without live services. |
| `APP_PASSWORD` | Enables the simple sign-in screen when set. |
| `SECRET_KEY` | Flask session-signing key; configure a long random value when using sign-in. |
| `PORT` | Local port (default `5000`). |
| `HR_LOCAL_DB` | Optional path for the local SQLite snapshot. |

The server binds to `127.0.0.1` by default. This is a development/demo interface, not a production-ready HR system. Do not expose it publicly or connect it to real employee data without proper authentication, authorization, auditing, and security review.
