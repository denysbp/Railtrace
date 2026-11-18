from fastapi import APIRouter
from app.api.routes.reports import reports_router

api_router = APIRouter(
    prefix="/v1"
)

api_router.include_router(reports_router)