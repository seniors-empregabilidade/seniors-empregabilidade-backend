import os
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Notification
from app.db.session import get_session_factory
from tests.notifications.conftest import (
    OTHER_TOKEN,
    OWNER_TOKEN,
    NotificationsScenario,
    authorization,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

LIST_PATH = "/api/v1/notifications/me"
READ_ALL_PATH = "/api/v1/notifications/me/read-all"


def read_path(notification_id: object) -> str:
    return f"/api/v1/notifications/{notification_id}/read"


def is_read(notification_id: UUID) -> bool:
    with get_session_factory()() as session:
        notification = session.get(Notification, notification_id)
        assert notification is not None
        return notification.read


def test_owner_lists_only_their_notifications_newest_first(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        str(scenario.owner_newest_unread_id),
        str(scenario.owner_middle_read_id),
        str(scenario.owner_oldest_unread_id),
    ]
    assert body["unread_count"] == 2
    newest = body["items"][0]
    assert newest["type"] == "company_registration_rejected"
    assert newest["message"] == "Newest"
    assert newest["read"] is False
    assert newest["details"] == {"reference_id": "synthetic"}
    assert set(newest) == {"id", "type", "message", "details", "read", "created_at"}


def test_unread_only_filter_hides_read_notifications(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.get(
        LIST_PATH,
        params={"unread_only": "true"},
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        str(scenario.owner_newest_unread_id),
        str(scenario.owner_oldest_unread_id),
    ]
    assert body["unread_count"] == 2


def list_page(
    client: TestClient, cursor: str | None = None, **params: str | int
) -> dict[str, Any]:
    query: dict[str, str | int] = {"limit": 1, **params}
    if cursor is not None:
        query["cursor"] = cursor
    response = client.get(LIST_PATH, params=query, headers=authorization(OWNER_TOKEN))
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def page_ids(body: dict[str, Any]) -> list[str]:
    return [item["id"] for item in body["items"]]


def test_cursor_walks_every_page_and_keeps_the_total_unread_count(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    first = list_page(notifications_client)
    second = list_page(notifications_client, first["next_cursor"])
    third = list_page(notifications_client, second["next_cursor"])

    assert page_ids(first) == [str(scenario.owner_newest_unread_id)]
    assert page_ids(second) == [str(scenario.owner_middle_read_id)]
    assert page_ids(third) == [str(scenario.owner_oldest_unread_id)]
    assert third["next_cursor"] is None
    assert [page["unread_count"] for page in (first, second, third)] == [2, 2, 2]


def test_single_page_has_no_next_cursor(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    body = list_page(notifications_client, limit=20)

    assert len(body["items"]) == 3
    assert body["next_cursor"] is None


def test_marking_as_read_between_unread_pages_skips_nothing(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    first = list_page(notifications_client, unread_only="true")
    notifications_client.post(
        read_path(scenario.owner_newest_unread_id),
        headers=authorization(OWNER_TOKEN),
    )
    second = list_page(notifications_client, first["next_cursor"], unread_only="true")

    # With an offset, the read item would leave the set and shift the oldest
    # unread notification out of reach.
    assert page_ids(first) == [str(scenario.owner_newest_unread_id)]
    assert page_ids(second) == [str(scenario.owner_oldest_unread_id)]
    assert second["next_cursor"] is None


def test_new_notification_between_pages_is_not_repeated(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    first = list_page(notifications_client)
    with get_session_factory().begin() as session:
        session.add(
            Notification(
                user_id=scenario.owner_id,
                type="company_registration_rejected",
                message="Arrived between pages",
            )
        )
    second = list_page(notifications_client, first["next_cursor"])

    assert page_ids(first) == [str(scenario.owner_newest_unread_id)]
    assert page_ids(second) == [str(scenario.owner_middle_read_id)]


def walk_every_page(client: TestClient, limit: int) -> list[str]:
    ids: list[str] = []
    cursor: str | None = None
    while True:
        body = list_page(client, cursor, limit=limit)
        ids.extend(page_ids(body))
        cursor = body["next_cursor"]
        if cursor is None:
            return ids


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_notifications_sharing_a_timestamp_are_neither_skipped_nor_repeated(
    notifications_client: TestClient, scenario: NotificationsScenario, limit: int
) -> None:
    # Rows created in one transaction share `now()`, so only `id` orders them
    # and page boundaries fall inside the tie.
    with get_session_factory().begin() as session:
        tied = [
            Notification(
                user_id=scenario.owner_id,
                type="company_registration_rejected",
                message=f"Tied {position}",
            )
            for position in range(4)
        ]
        session.add_all(tied)
        session.flush()
        tied_ids = [notification.id for notification in tied]
        assert len({notification.created_at for notification in tied}) == 1

    walked = walk_every_page(notifications_client, limit)

    assert walked == [
        *(str(tied_id) for tied_id in sorted(tied_ids, reverse=True)),
        str(scenario.owner_newest_unread_id),
        str(scenario.owner_middle_read_id),
        str(scenario.owner_oldest_unread_id),
    ]


def test_owner_marks_a_notification_as_read(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.post(
        read_path(scenario.owner_newest_unread_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["id"] == str(scenario.owner_newest_unread_id)
    assert body["read"] is True
    assert is_read(scenario.owner_newest_unread_id)
    assert not is_read(scenario.owner_oldest_unread_id)


def test_marking_an_already_read_notification_is_idempotent(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.post(
        read_path(scenario.owner_middle_read_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["read"] is True


def test_another_users_notification_is_not_found_and_left_unread(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.post(
        read_path(scenario.other_unread_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "notification_not_found"
    assert not is_read(scenario.other_unread_id)


def test_nonexistent_notification_is_not_found(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.post(
        read_path(uuid4()), headers=authorization(OWNER_TOKEN)
    )

    assert response.status_code == 404
    assert response.json()["code"] == "notification_not_found"


def test_read_all_marks_only_the_owners_notifications(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.post(
        READ_ALL_PATH, headers=authorization(OWNER_TOKEN)
    )

    assert response.status_code == 204
    assert response.content == b""
    assert is_read(scenario.owner_newest_unread_id)
    assert is_read(scenario.owner_oldest_unread_id)
    assert not is_read(scenario.other_unread_id)

    listing = notifications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))
    assert listing.json()["unread_count"] == 0


def test_company_account_lists_its_own_notifications(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.get(LIST_PATH, headers=authorization(OTHER_TOKEN))

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(scenario.other_unread_id)]
    assert body["unread_count"] == 1


def test_unknown_token_is_rejected(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.get(
        LIST_PATH, headers=authorization("unknown-token")
    )

    assert response.status_code == 401
