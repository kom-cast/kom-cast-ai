from fastapi import FastAPI, Depends

from sqlalchemy.orm import Session
from script_app.schemas import (
    GenerateScriptsRequest,
    GenerateScriptsResponse,
)
from script_app.dependencies import (
    create_script_service,
    get_session,
)

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/scripts/generate",
    response_model=GenerateScriptsResponse,
)
async def generate_scripts(
    request: GenerateScriptsRequest,
    session: Session = Depends(get_session)
) -> GenerateScriptsResponse:

    try:
        service = create_script_service(session)

        scripts = await service.generate_scripts(
            stock_ids=request.stock_ids,
            start_at=request.start_at,
            end_at=request.end_at,
        )

        generated_stock_ids = [
            stock_id
            for stock_id, script in scripts.items()
            if script
        ]

        skipped_stock_ids = [
            stock_id
            for stock_id, script in scripts.items()
            if not script
        ]

        return GenerateScriptsResponse(
            status="completed",
            generated_stock_ids=generated_stock_ids,
            skipped_stock_ids=skipped_stock_ids,
        )

    finally:
        session.close()
