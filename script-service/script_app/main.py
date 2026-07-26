from fastapi import FastAPI

from script_app.api.scripts import router as scripts_router

app = FastAPI()
app.include_router(scripts_router)


@app.get("/health")
def health():
    return {"status": "ok"}
