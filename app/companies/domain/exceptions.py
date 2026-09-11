class InvalidCNPJError(ValueError):
    """A CNPJ cannot be represented as a valid domain value."""


class CompanySegmentBlockedError(ValueError):
    """The registry segment is not eligible for registration."""


class PersonalEmailDomainError(ValueError):
    """The supplied address belongs to a personal email provider."""


class InvalidCompanyDecisionError(ValueError):
    """A rejection must explain the decision; an approval must not include a reason."""
