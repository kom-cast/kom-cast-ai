from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from script_app.dependencies import (
    create_script_deletion_service,
    get_session,
)
from script_app.services import (
    ResourceInUseError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/sections", tags=["sections"])


@router.delete(
    "/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_section(
    section_id: UUID,
    session: Session = Depends(get_session),
) -> Response:
    service = create_script_deletion_service(session)

    try:
        service.delete_section(section_id)
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="섹션을 찾을 수 없습니다.",
        ) from error
    except ResourceInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="스크립트에서 사용 중인 섹션입니다.",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
