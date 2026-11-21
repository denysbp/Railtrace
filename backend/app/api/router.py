from fastapi import APIRouter
from app.api.routes.assignments import assignments_router
from app.api.routes.depot import depot_router
from app.api.routes.duties import duties_router
from app.api.routes.lines import lines_router
from app.api.routes.reports import reports_router
from app.api.routes.stats import stats_router
from app.api.routes.trainsets import trainset_router
from app.api.routes.quarantine import quarantine_router

api_router = APIRouter(
    prefix="/v1"
)

api_router.include_router(reports_router)
api_router.include_router(depot_router)
api_router.include_router(lines_router)
api_router.include_router(duties_router)
api_router.include_router(trainset_router)
api_router.include_router(quarantine_router)
api_router.include_router(assignments_router)
api_router.include_router(stats_router)
