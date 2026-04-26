from fastapi import FastAPI

from app.routes import execution_router

app = FastAPI(title="Cymatic Backend", version="0.1.0")
app.include_router(execution_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
