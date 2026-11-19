from fastapi import (
    Depends,
    APIRouter,
    status,
    HTTPException
)
from sqlalchemy.orm import Session
from app.schemas.assignment import AssignmentResponse, AssignmentUpdate
from app.services.assignments import (
    AssignmentNotFoundError,
    AssignmentOverlapError,
    InvalidIntervalError,
    update_assignment,
)
from app.db.session import get_db

assignments_router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)

@assignments_router.patch(
    "/{assignment_id}",
    response_model=AssignmentResponse
)
def patch_assignment(
    assignment_id: int,
    body: AssignmentUpdate,
    db: Session = Depends(get_db)
):
    try:
        return update_assignment(db, assignment_id, body.started_at, body.ended_at)
    except AssignmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    except InvalidIntervalError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ended_at must be after started_at"
        )
    except AssignmentOverlapError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment overlaps an existing one"
        )
