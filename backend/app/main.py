from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(title="Railtrace")

app.include_router(api_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
