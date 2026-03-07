from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import hmac
import hashlib
import logging

from app.config import settings
from app.tasks.message_tasks import process_whatsapp_message


logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_webhook_signature(request: Request) -> Dict[str, Any]:
    """Verify Uazapi webhook signature."""
    # Get raw body
    body = await request.body()

    # Get signature from headers
    signature = request.headers.get("X-Webhook-Signature", "")
    if not signature:
        logger.warning("Missing webhook signature")
        return {}

    # Verify signature (adjust based on Uazapi's actual signature method)
    expected_signature = hmac.new(
        settings.uazapi_webhook_verify_token.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    return await request.json()


@router.get("/")
async def webhook_verify(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
) -> JSONResponse:
    """
    Verify webhook with Uazapi.
    Uazapi will send a GET request to verify the webhook.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.uazapi_webhook_verify_token:
        logger.info("Webhook verified successfully")
        return JSONResponse(content={"challenge": hub_challenge}, status_code=200)

    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/")
async def webhook_message(
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Receive incoming WhatsApp message from Uazapi.
    """
    try:
        # Get webhook data
        data = await request.json()
        logger.info(f"Received webhook: {data}")

        # Validate webhook data
        if not data.get("event") or not data.get("message"):
            logger.warning("Invalid webhook data structure")
            raise HTTPException(status_code=400, detail="Invalid webhook data")

        # Extract message info
        message_data = data.get("message", {})
        phone = message_data.get("from", "")
        message_type = message_data.get("type", "text")
        message_id = message_data.get("id")

        # Handle different message types
        if message_type == "text":
            content = message_data.get("text", {}).get("body", "")
        elif message_type == "audio":
            audio_url = message_data.get("audio", {}).get("url", "")
            # Process audio asynchronously
            background_tasks.add_task(
                process_audio_message,
                phone=phone,
                audio_url=audio_url,
                message_id=message_id
            )
            return {"status": "processing_audio"}
        elif message_type == "image":
            content = "[Imagem recebida]"
        else:
            content = f"[{message_type} message received]"

        # Process message asynchronously with Celery
        background_tasks.add_task(
            process_whatsapp_message.delay,
            phone=phone,
            message=content,
            message_type=message_type,
            message_id=message_id
        )

        return {"status": "received", "message_id": message_id}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/status")
async def message_status(request: Request) -> Dict[str, str]:
    """
    Receive message status updates from Uazapi.
    """
    try:
        data = await request.json()
        logger.info(f"Message status update: {data}")

        message_id = data.get("message_id")
        status = data.get("status")  # sent, delivered, read, failed

        # Update message status in database
        # TODO: Implement status update logic

        return {"status": "updated"}

    except Exception as e:
        logger.error(f"Error processing status update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


async def process_audio_message(phone: str, audio_url: str, message_id: str):
    """
    Process incoming audio message.
    Downloads audio, transcribes it, and processes as text.
    """
    from app.services.audio_service import transcribe_audio

    try:
        logger.info(f"Processing audio message from {phone}")

        # Transcribe audio
        transcript = await transcribe_audio(audio_url)
        logger.info(f"Transcript: {transcript}")

        # Process as text message
        await process_whatsapp_message.delay(
            phone=phone,
            message=transcript,
            message_type="text",
            message_id=message_id
        )

    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        # Send error message to user
        # TODO: Implement error response
