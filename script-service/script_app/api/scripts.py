import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from script_app.dependencies import (
    create_script_generation_service,
    create_script_deletion_service,
    get_session,
)
from script_app.services import (
    ResourceInUseError,
    ResourceNotFoundError,
)
from script_app.schemas import (
    GenerateUserScriptsRequest,
    GenerateUserScriptsResponse,
)

router = APIRouter(prefix="/scripts", tags=["scripts"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateUserScriptsResponse)
async def generate_scripts(
    request: GenerateUserScriptsRequest,
    session: Session = Depends(get_session),
) -> GenerateUserScriptsResponse:
    logger.info(
        "script_generation_request_received start_at=%s end_at=%s user_ids=%s",
        request.start_at.isoformat(),
        request.end_at.isoformat(),
        [str(user_id) for user_id in request.user_ids],
    )
    service = create_script_generation_service(session)

    return await service.generate(
        user_ids=request.user_ids,
        period_start=request.start_at,
        period_end=request.end_at,
    )


@router.delete(
    "/{script_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_script(
    script_id: UUID,
    session: Session = Depends(get_session),
) -> Response:
    service = create_script_deletion_service(session)

    try:
        service.delete_script(script_id)
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="스크립트를 찾을 수 없습니다.",
        ) from error
    except ResourceInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="다른 데이터가 참조 중인 스크립트입니다.",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
