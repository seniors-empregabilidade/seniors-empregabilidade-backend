from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.notifications.schemas.notification_list_response import (
    NotificationListResponse,
)
from app.notifications.schemas.notification_response import NotificationResponse
from app.notifications.services.list_my_notifications import list_my_notifications
from app.notifications.services.mark_all_notifications_as_read import (
    mark_all_notifications_as_read,
)
from app.notifications.services.mark_notification_as_read import (
    mark_notification_as_read,
)

# A real cursor is under 100 characters; the cap rejects junk before decoding.
MAX_CURSOR_LENGTH = 200

# Every account type receives notifications, so these routes require only an
# authenticated, active user and always scope the query to that user.
router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403)},
)


@router.get("/me", response_model=NotificationListResponse)
def read_my_notifications(
    response: Response,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    unread_only: Annotated[
        bool, Query(description="Return only unread notifications")
    ] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=MAX_CURSOR_LENGTH,
            description="`next_cursor` from the previous page; omit for the first.",
        ),
    ] = None,
) -> NotificationListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_my_notifications(
        session,
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
        cursor=cursor,
    )


@router.post("/me/read-all", status_code=204)
def read_all_my_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    mark_all_notifications_as_read(session, user_id=user.id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    responses={404: PROBLEM_RESPONSE},
)
def read_my_notification(
    notification_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotificationResponse:
    response.headers["Cache-Control"] = "no-store"
    return mark_notification_as_read(
        session, notification_id=notification_id, user_id=user.id
    )
