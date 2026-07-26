from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from script_app.dependencies import (
    create_script_generation_service,
    get_session,
)
from script_app.schemas import (
    GenerateUserScriptsRequest,
    GenerateUserScriptsResponse,
)

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/generate", response_model=GenerateUserScriptsResponse)
async def generate_scripts(
    request: GenerateUserScriptsRequest,
    session: Session = Depends(get_session),
) -> GenerateUserScriptsResponse:
    service = create_script_generation_service(session)

    return await service.generate(
        user_ids=request.user_ids,
        period_start=request.start_at,
        period_end=request.end_at,
    )
