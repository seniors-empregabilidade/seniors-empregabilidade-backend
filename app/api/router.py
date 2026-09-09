from fastapi import APIRouter

# Import sub‑routers for each feature
from app.api.v1 import professionals

api_router = APIRouter()
# Include feature routers (they will use the global /api/v1 prefix set in main.py)
api_router.include_router(professionals.router)

