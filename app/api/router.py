from fastapi import APIRouter

from app.accounts.router import router as accounts_router
from app.auth.router import router as auth_router
from app.companies.router import router as companies_router

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(auth_router)
api_router.include_router(companies_router)
