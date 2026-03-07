import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

from app.config import settings


logger = logging.getLogger(__name__)


class PixBankService:
    """Service for interacting with PixBank payment API."""

    def __init__(self):
        self.base_url = "https://api.pixbank.com.br/v1"
        self.api_key = settings.pixbank_api_key
        self.secret_key = settings.pixbank_secret_key
        self.headers = {
            "X-API-Key": self.api_key,
            "X-Secret-Key": self.secret_key,
            "Content-Type": "application/json"
        }

    async def create_pix_charge(
        self,
        amount: float,
        correlation_id: str,
        description: str,
        expires_in_minutes: int = 15,
        customer: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new Pix charge.

        Args:
            amount: Charge amount in BRL
            correlation_id: Unique ID for this charge
            description: Charge description
            expires_in_minutes: Time until QR code expires
            customer: Optional customer info

        Returns:
            Pix charge data with QR code
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "correlationId": correlation_id,
                    "amount": amount,
                    "description": description,
                    "expiresIn": expires_in_minutes * 60  # Convert to seconds
                }

                if customer:
                    payload["customer"] = customer

                response = await client.post(
                    f"{self.base_url}/charges",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Pix charge created: {correlation_id}, amount: R$ {amount}")
                return {
                    "txid": result.get("txid"),
                    "qr_code": result.get("qrCode"),
                    "qr_code_text": result.get("qrCodeText"),
                    "expires_at": datetime.utcnow() + timedelta(minutes=expires_in_minutes),
                    "amount": amount
                }

        except httpx.HTTPError as e:
            logger.error(f"Error creating Pix charge: {e}")
            raise

    async def get_charge_status(self, txid: str) -> Dict:
        """
        Get the status of a Pix charge.

        Args:
            txid: Transaction ID

        Returns:
            Charge status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/charges/{txid}",
                    headers=self.headers,
                    timeout=10.0
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting charge status: {e}")
            raise

    async def cancel_charge(self, txid: str) -> Dict:
        """
        Cancel a pending Pix charge.

        Args:
            txid: Transaction ID

        Returns:
            Cancellation result
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/charges/{txid}",
                    headers=self.headers,
                    timeout=10.0
                )

                response.raise_for_status()
                logger.info(f"Pix charge cancelled: {txid}")
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error cancelling charge: {e}")
            raise

    async def generate_qr_code_image(self, qr_code_text: str) -> str:
        """
        Generate QR code image URL from QR code text.

        Args:
            qr_code_text: QR code text/string

        Returns:
            URL to QR code image
        """
        # You could use a QR code generation service
        # For now, returning a placeholder
        return f"https://api.qrserver.com/v1/create-qr-code/?data={qr_code_text}"

    async def format_pix_message(
        self,
        amount: float,
        qr_code_text: str,
        expires_in_minutes: int
    ) -> str:
        """
        Format Pix payment message for WhatsApp.

        Args:
            amount: Amount to pay
            qr_code_text: QR code text for copy/paste
            expires_in_minutes: Time until expires

        Returns:
            Formatted message
        """
        message = f"""💰 *Pagamento via Pix*

Valor: *R$ {amount:.2f}*

📱 Copie e cole o código abaixo no app do seu banco:

```
{qr_code_text}
```

⏰ O pagamento expira em {expires_in_minutes} minutos.

Após o pagamento, você receberá a confirmação em até alguns segundos."""
        return message


# Singleton instance
pixbank_service = PixBankService()
