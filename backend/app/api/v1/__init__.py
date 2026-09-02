from fastapi import APIRouter

from app.api.v1 import auth, comparisons, dashboard, images, inspections, system, users, vehicles

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(vehicles.router)
api_router.include_router(inspections.router)
api_router.include_router(images.router)
api_router.include_router(comparisons.router)
api_router.include_router(dashboard.router)

__all__ = ["api_router"]
