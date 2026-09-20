"""Link seeded users to real Cognito accounts.

The seed inserts `app_user` rows with a null `identity_subject`, and without
that column login finds nobody. This script creates the accounts and fills it.

Run with operator credentials, never from the instance role: the application
has no need for `cognito-idp:Admin*`.

    AWS_PROFILE=seniors-ages-sdk \
    DATABASE_URL=postgresql+psycopg://... \
    COGNITO_USER_POOL_ID=us-east-2_... \
    SENIORS_TEST_PASSWORD='...' \
    uv run python -m scripts.seed_identities
"""

import os

import boto3
from mypy_boto3_cognito_idp import CognitoIdentityProviderClient
from sqlalchemy import update

from app.db.models import AppUser
from app.db.session import get_session_factory
from scripts.seed import seed_id

TEST_USERS = [
    ("user-candidate", "candidate@example.invalid"),
    ("user-company", "representative@company.example.invalid"),
    ("user-administrator", "administrator@example.invalid"),
]


def ensure_account(
    cognito: CognitoIdentityProviderClient, pool_id: str, email: str, password: str
) -> str:
    try:
        # SUPPRESS sends no email, so this does not consume the pool's daily quota.
        created = cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
        )
        attributes = created["User"]["Attributes"]
    except cognito.exceptions.UsernameExistsException:
        attributes = cognito.admin_get_user(UserPoolId=pool_id, Username=email)[
            "UserAttributes"
        ]

    cognito.admin_set_user_password(
        UserPoolId=pool_id, Username=email, Password=password, Permanent=True
    )
    return str(next(a["Value"] for a in attributes if a["Name"] == "sub"))


def main() -> None:
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    password = os.environ["SENIORS_TEST_PASSWORD"]
    cognito = boto3.client(
        "cognito-idp", region_name=os.environ.get("COGNITO_REGION", "us-east-2")
    )

    with get_session_factory().begin() as session:
        for seed_name, email in TEST_USERS:
            subject = ensure_account(cognito, pool_id, email, password)
            session.execute(
                update(AppUser)
                .where(AppUser.id == seed_id(seed_name))
                .values(identity_subject=subject)
            )
            print(f"{email} -> {subject}")


if __name__ == "__main__":
    main()
