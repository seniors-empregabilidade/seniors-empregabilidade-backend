from fastapi import APIRouter

from app.accounts.router import router as accounts_router
from app.applications.router import router as applications_router
from app.auth.router import router as auth_router
from app.candidates.router import router as candidates_router
from app.companies.router import router as companies_router
from app.jobs.router import router as jobs_router
from app.password_reset.router import router as password_reset_router
from app.skills.router import router as skills_router

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(applications_router)
api_router.include_router(auth_router)
api_router.include_router(candidates_router)
api_router.include_router(companies_router)
api_router.include_router(jobs_router)
api_router.include_router(password_reset_router)
api_router.include_router(skills_router)
