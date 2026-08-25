from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import run_query
from queries import get_query_meta, run_query_by_id

app = FastAPI(title="IPL Query Resolver")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class RunRequest(BaseModel):
    query_id: int
    inputs: dict = {}


@app.get("/api/queries")
def api_queries():
    return {"queries": get_query_meta()}


@app.get("/api/options")
def api_options(source: str):
    source = source.strip().lower()
    if source == "teams":
        rows = run_query("SELECT team_name AS value FROM teams ORDER BY team_name")
    elif source == "players":
        rows = run_query("SELECT player_name AS value FROM players ORDER BY player_name")
    elif source == "venues":
        rows = run_query(
            "SELECT venue_name AS value FROM venues ORDER BY venue_name"
        )
    elif source == "umpires":
        rows = run_query("SELECT umpire_name AS value FROM umpires ORDER BY umpire_name")
    elif source == "seasons":
        rows = run_query(
            "SELECT DISTINCT season AS value FROM match_details ORDER BY season"
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown option source: {source}")
    return {"values": [r["value"] for r in rows]}


@app.post("/api/run")
def api_run(req: RunRequest):
    try:
        result = run_query_by_id(req.query_id, req.inputs or {})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"query_id": req.query_id, "result": result}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
