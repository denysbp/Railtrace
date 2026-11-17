from fastapi import FastAPI

app = FastAPI(title="Railtrace")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
