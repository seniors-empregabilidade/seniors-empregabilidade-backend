import os
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


def test_pagination_keeps_the_total_unread_count(
    notifications_client: TestClient, scenario: NotificationsScenario
) -> None:
    response = notifications_client.get(
        LIST_PATH,
        params={"limit": 1, "offset": 1},
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        str(scenario.owner_middle_read_id)
    ]
    assert body["unread_count"] == 2


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
