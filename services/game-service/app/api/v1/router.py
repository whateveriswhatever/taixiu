from fastapi import APIRouter

from app.api.v1.endpoints import game, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(game.router, prefix="/game", tags=["Game Engine"])

