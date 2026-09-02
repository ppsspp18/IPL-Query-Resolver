import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from benchmark import run_benchmark
from db import run_query
from queries import get_query_meta, run_query_by_id
import benchmark as benchmark_mod
from text2sql import (
    INTENT_META,
    MAX_QUESTION_LEN,
    ExecutionError,
    SQLGenerationError,
    Text2SQLError,
    ValidationError,
    process_question,
)

app = FastAPI(title="IPL Query Resolver")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# --------------------------------------------------------------------------- #
# Pydantic request models
# --------------------------------------------------------------------------- #
class RunRequest(BaseModel):
    query_id: int
    inputs: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LEN,
                          description="Natural-language question about IPL data")
    session_id: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        return v.strip()


# --------------------------------------------------------------------------- #
# Preset query endpoints (existing behaviour)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Text-to-SQL chat (REST) — returns the full lifecycle with generated SQL
# --------------------------------------------------------------------------- #
@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Run the Text-to-SQL pipeline and return the result plus lifecycle events.

    The response includes the generated SQL, its source (LLM or rule engine),
    and execution metadata, so every answer is transparent and auditable.
    """
    events: list[dict] = []
    try:
        result = await process_question(req.question, emit=events.append)
        return {"events": events, "result": result}
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except SQLGenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Text2SQLError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intents")
def api_intents():
    return {"intents": [{"id": k, **v} for k, v in INTENT_META.items()]}


# --------------------------------------------------------------------------- #
# Benchmark
# --------------------------------------------------------------------------- #
@app.get("/api/benchmark")
async def api_benchmark(engine: str = "rule"):
    """Run the 33-query accuracy benchmark and return the report.

    `engine`: rule (deterministic, offline, default) | auto | llm.
    """
    if engine not in ("auto", "rule", "llm"):
        raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}")
    benchmark_mod.ENGINE = engine
    report = await run_benchmark()
    return report


# --------------------------------------------------------------------------- #
# WebSocket streaming — live updates across the request lifecycle
# --------------------------------------------------------------------------- #
@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """Stream validation -> SQL generation -> execution -> result in real time.

    The client sends:      {"question": "..."}
    The server streams:    {"type": "validation" | "sql_generation" |
                                   "query_execution" | "result" | "error", ...}
    One connection answers any number of questions in sequence.
    """
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:
        # Called from the pipeline thread; push into the loop safely.
        asyncio.get_running_loop().call_soon_threadsafe(queue.put_nowait, event)

    async def sender():
        try:
            while True:
                event = await queue.get()
                if event.get("type") == "__close__":
                    break
                await ws.send_json(event)
        except Exception:  # noqa: BLE001 - client may disconnect mid-stream
            pass

    send_task = asyncio.create_task(sender())
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                req = ChatRequest.model_validate(data)
            except Exception as e:  # noqa: BLE001
                await queue.put({
                    "type": "error",
                    "stage": "validation",
                    "message": f"Invalid request: {e}",
                })
                continue

            try:
                await process_question(req.question, emit=emit)
            except ValidationError as e:
                await queue.put({"type": "error", "stage": "validation", "message": str(e)})
            except SQLGenerationError as e:
                await queue.put({"type": "error", "stage": "sql_generation", "message": str(e)})
            except ExecutionError as e:
                await queue.put({"type": "error", "stage": "query_execution", "message": str(e)})
            except Text2SQLError as e:
                await queue.put({"type": "error", "stage": "pipeline", "message": str(e)})
            except Exception as e:  # noqa: BLE001
                await queue.put({"type": "error", "stage": "pipeline", "message": f"Unexpected error: {e}"})
    except WebSocketDisconnect:
        pass
    finally:
        # Flush any pending events before tearing down the sender.
        await queue.put({"type": "__close__"})
        try:
            await asyncio.wait_for(asyncio.shield(send_task), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            send_task.cancel()


# --------------------------------------------------------------------------- #
# Static frontend
# --------------------------------------------------------------------------- #
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
