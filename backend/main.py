from fastapi import FastAPI

from app.routes.mcp import router as mcp_router
from app.routes.voice import router as voice_router

app = FastAPI(title="Cymatic Backend", version="0.1.0")
app.include_router(mcp_router)
app.include_router(voice_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
