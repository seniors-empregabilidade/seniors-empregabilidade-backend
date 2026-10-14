from enum import StrEnum


class NotificationType(StrEnum):
    """Stable codes for the events that notify a user inside the platform.

    Add a member together with the operation that produces it (US-12, US-21,
    US-29, ...). The value is persisted in `notification.type` and returned
    to clients, so never rename an existing member.
    """

    APPLICATION_RECEIVED = "application_received"
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    COMPANY_REGISTRATION_REJECTED = "company_registration_rejected"
