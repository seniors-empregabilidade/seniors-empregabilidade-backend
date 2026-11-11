from fastapi import APIRouter

from app.account_management.router import router as account_management_router
from app.accounts.router import router as accounts_router
from app.applications.router import router as applications_router
from app.auth.router import router as auth_router
from app.candidates.router import router as candidates_router
from app.companies.router import router as companies_router
from app.contacts.router import router as contacts_router
from app.indicators.router import router as indicators_router
from app.jobs.admin_router import router as job_administration_router
from app.jobs.router import router as jobs_router
from app.notifications.router import router as notifications_router
from app.password_reset.router import router as password_reset_router
from app.skills.admin_router import router as skill_catalog_router
from app.skills.router import router as skills_router
from app.support.router import router as support_router
from app.trainings.admin_router import router as training_catalog_router
from app.trainings.router import router as trainings_router

api_router = APIRouter()
api_router.include_router(account_management_router)
api_router.include_router(accounts_router)
api_router.include_router(applications_router)
api_router.include_router(auth_router)
api_router.include_router(candidates_router)
api_router.include_router(companies_router)
api_router.include_router(contacts_router)
api_router.include_router(indicators_router)
api_router.include_router(job_administration_router)
api_router.include_router(jobs_router)
api_router.include_router(notifications_router)
api_router.include_router(password_reset_router)
api_router.include_router(skill_catalog_router)
api_router.include_router(skills_router)
api_router.include_router(support_router)
api_router.include_router(training_catalog_router)
api_router.include_router(trainings_router)
