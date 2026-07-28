from fastapi import FastAPI

from script_app.api.scripts import router as scripts_router
from script_app.api.sections import router as sections_router

app = FastAPI()
app.include_router(scripts_router)
app.include_router(sections_router)


@app.get("/health")
def health():
    return {"status": "ok"}
