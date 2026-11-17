from fastapi import FastAPI
from app.api.routes.reports import reports_router

app = FastAPI(title="Railtrace")

app.include_router(reports_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
