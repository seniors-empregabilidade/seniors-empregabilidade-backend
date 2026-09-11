from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisteredIdentity:
    identity_subject: str
    confirmed: bool
