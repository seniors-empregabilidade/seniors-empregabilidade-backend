import pytest
from pydantic import ValidationError

from app.companies.schemas.company_request import CompanyRegistrationRequest


@pytest.mark.parametrize(
    "url",
    [
        "https://linkedin.com.evil.invalid/company/test",
        "http://linkedin.com/company/test",
        "https://user@linkedin.com/company/test",
        "https://linkedin.com/in/test",
        "https://linkedin.com/company/",
        "https://linkedin.com:invalid/company/test",
    ],
)
def test_registration_rejects_invalid_linkedin_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        CompanyRegistrationRequest.model_validate(
            {
                "cnpj": "11222333000181",
                "display_name": "Synthetic Company",
                "address": {
                    "street": "Street",
                    "number": "1",
                    "neighborhood": "District",
                    "city": "City",
                    "state": "RS",
                    "zip_code": "90000000",
                },
                "corporate_email": "test@synthetic.invalid",
                "password": "SyntheticPass!2026",
                "terms_accepted": True,
                "terms_version": "v1",
                "linkedin_url": url,
            }
        )
