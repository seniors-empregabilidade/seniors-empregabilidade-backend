from app.core.errors import ProblemException


class InvalidCpfError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_cpf",
            detail="The CPF is invalid.",
            errors={"cpf": ["The CPF is invalid."]},
        )


class MinimumAgeNotMetError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="minimum_age_not_met",
            detail="The professional must be at least 45 years old.",
            errors={"birth_date": ["The minimum age is 45."]},
        )


class TermsAcceptanceRequiredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="terms_acceptance_required",
            detail="The current terms must be accepted.",
            errors={"terms_version_accepted": ["The terms version is required."]},
        )


class CpfAlreadyRegisteredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="cpf_already_registered",
            detail="The CPF is already registered.",
            errors={"cpf": ["The CPF is already registered."]},
        )


class EmailAlreadyRegisteredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="email_already_registered",
            detail="The email is already registered.",
            errors={"email": ["The email is already registered."]},
        )


class ProfileNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="profile_not_found",
            detail="The professional profile was not found.",
        )


class ExperienceNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="experience_not_found",
            detail="The experience was not found.",
        )


class InvalidExperiencePeriodError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_experience_period",
            detail="The end date cannot be before the start date.",
            errors={"end_date": ["The end date cannot be before the start date."]},
        )


class EducationNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="education_not_found",
            detail="The education was not found.",
        )


class InvalidEducationPeriodError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_education_period",
            detail="The end date cannot be before the start date.",
            errors={"end_date": ["The end date cannot be before the start date."]},
        )


class SkillNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="skill_not_found",
            detail="The skill was not found.",
        )


class SkillAlreadyAddedError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="skill_already_added",
            detail="The skill is already in the profile.",
            errors={"skill_id": ["The skill is already in the profile."]},
        )


class CertificationNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="certification_not_found",
            detail="The certification was not found.",
        )


class InvalidCertificationPeriodError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_certification_period",
            detail="The expiration date cannot be before the issue date.",
            errors={
                "expiration_date": [
                    "The expiration date cannot be before the issue date."
                ]
            },
        )


class CertificationDocumentNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="certification_document_not_found",
            detail="The certification has no document.",
        )


class UnsupportedDocumentTypeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="unsupported_document_type",
            detail="The document must be a PDF, PNG, or JPEG file.",
            errors={"file": ["The document must be a PDF, PNG, or JPEG file."]},
        )


class DocumentTooLargeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="document_too_large",
            detail="The document must be at most 5 MB.",
            errors={"file": ["The document must be at most 5 MB."]},
        )
