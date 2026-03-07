from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from typing import Dict
import hmac
import hashlib
import logging

from app.config import settings
from app.tasks.payment_tasks import process_payment_confirmation


logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_pixbank_signature(request: Request) -> bool:
    """Verify PixBank webhook signature."""
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not signature:
        logger.warning("Missing PixBank signature")
        return False

    # Verify signature
    expected_signature = hmac.new(
        settings.pixbank_webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@router.post("/webhook")
async def pixbank_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Receive payment confirmation from PixBank.
    """
    try:
        # Verify signature
        if not await verify_pixbank_signature(request):
            logger.warning("Invalid PixBank signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Get webhook data
        data = await request.json()
        logger.info(f"Received PixBank webhook: {data}")

        # Validate required fields
        if not data.get("txid") or not data.get("status"):
            logger.warning("Invalid PixBank webhook data")
            raise HTTPException(status_code=400, detail="Invalid webhook data")

        txid = data.get("txid")
        status = data.get("status")  # confirmed, failed, pending
        amount = data.get("amount", 0)

        # Process payment asynchronously
        background_tasks.add_task(
            process_payment_confirmation.delay,
            txid=txid,
            status=status,
            amount=amount,
            raw_data=data
        )

        return {"status": "processing", "txid": txid}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing PixBank webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/health")
async def pixbank_health() -> Dict[str, str]:
    """Check PixBank API connectivity."""
    try:
        # TODO: Implement PixBank API health check
        return {"status": "healthy", "service": "pixbank"}
    except Exception as e:
        logger.error(f"PixBank health check failed: {e}")
        return {"status": "unhealthy", "service": "pixbank", "error": str(e)}
