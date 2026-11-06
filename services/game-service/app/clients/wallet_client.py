from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
import httpx

from app.core.config import settings


class WalletClient:
    def __init__(self, base_url: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.base_url = base_url or settings.WALLET_SERVICE_URL
        self._client = client

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Internal-Service-Key": settings.INTERNAL_API_KEY,
        }

    async def hold_bet(
        self, user_id: int, amount: Decimal, reference_id: str, description: str = ""
    ) -> dict:
        """Gọi sang Wallet Service để tạm khóa số dư cược."""
        payload = {
            "user_id": user_id,
            "amount": str(amount),
            "reference_id": reference_id,
            "description": description or f"Khóa cược Tài Xỉu #{reference_id}",
        }
        url = f"{self.base_url}/hold"

        async with httpx.AsyncClient(timeout=10.0) if not self._client else self._client as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Không thể kết nối đến Wallet Service: {str(exc)}",
                )

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            error_detail = response.json().get("detail", "Số dư không đủ để đặt cược")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Wallet Service phản hồi lỗi: {response.text}",
            )

        return response.json()

    async def settle_bet(
        self,
        user_id: int,
        reference_id: str,
        result: str,
        hold_amount: Decimal,
        payout_amount: Decimal = Decimal("0.00"),
        description: str = "",
    ) -> dict:
        """Gọi sang Wallet Service để quyết toán tiền cược (WIN/LOSE/REFUND)."""
        payload = {
            "user_id": user_id,
            "reference_id": reference_id,
            "result": result,
            "hold_amount": str(hold_amount),
            "payout_amount": str(payout_amount),
            "description": description or f"Quyết toán cược #{reference_id}",
        }
        url = f"{self.base_url}/settle"

        async with httpx.AsyncClient(timeout=10.0) if not self._client else self._client as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Không thể kết nối đến Wallet Service khi quyết toán: {str(exc)}",
                )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Lỗi quyết toán ví: {response.text}",
            )

        return response.json()


wallet_client = WalletClient()

