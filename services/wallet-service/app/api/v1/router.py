from fastapi import APIRouter

from app.api.v1.endpoints import health, wallet

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["Wallet"])

