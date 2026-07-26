from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from tts_app.api.briefings import AUDIO_DIR
from tts_app.api.briefings import router as briefings_router

app = FastAPI(title="komcast TTS service")
app.add_middleware(
    CORSMiddleware,
    # TODO: Vite 개발 서버 기본 포트. 배포 시 실제 프론트 도메인으로 교체.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(briefings_router)
app.mount("/static/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
