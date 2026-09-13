from app.companies.schemas.company_response import CompanyResponse


class CompanyRegistrationResponse(CompanyResponse):
    email_confirmation_required: bool
