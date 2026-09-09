from fastapi import APIRouter

from app.accounts.router import router as email_verification_router

api_router = APIRouter()
api_router.include_router(email_verification_router)
