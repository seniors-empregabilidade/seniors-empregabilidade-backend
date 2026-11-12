"""Stable endpoint URL helper for profile photos.

``photo_url_for`` returns the path to the serving endpoint for a profile photo
(or ``None`` when no photo is stored).  It intentionally does NOT touch storage
or sign any URL, so it is safe to call during profile or list response assembly
even when storage is unavailable.  The serving endpoint itself is responsible
for signing via ``DocumentStorage.inline_url``.
"""

from uuid import UUID


def photo_url_for(
    owner_kind: str,
    owner_id: UUID,
    *,
    has_photo: bool,
) -> str | None:
    """Return the serving endpoint path for a profile photo, or ``None``.

    Args:
        owner_kind: Either ``"candidate"`` (maps to ``professionals``) or
            ``"company"`` (maps to ``companies``).
        owner_id: The UUID of the owner.
        has_photo: Whether a photo is currently stored (``True`` when
            ``photo_object_key is not None``).

    Returns:
        A stable API path string such as
        ``/api/v1/professionals/{owner_id}/photo``, or ``None`` when the owner
        has no photo.  This path never changes and never expires.
    """
    if not has_photo:
        return None
    if owner_kind == "candidate":
        return f"/api/v1/professionals/{owner_id}/photo"
    if owner_kind == "company":
        return f"/api/v1/companies/{owner_id}/photo"
    raise ValueError(f"Unknown owner_kind: {owner_kind!r}")
