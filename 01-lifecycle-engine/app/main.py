from fastapi import FastAPI

from app.api import router

app = FastAPI(title="Lifecycle Engine")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
