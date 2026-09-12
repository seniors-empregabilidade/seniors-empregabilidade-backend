from fastapi import APIRouter

# Import sub-routers for each feature
from app.accounts.router import router as accounts_router
from app.auth.router import router as auth_router
from app.api.v1 import professionals

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(auth_router)
api_router.include_router(professionals.router)
