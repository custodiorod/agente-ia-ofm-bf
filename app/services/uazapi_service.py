import httpx
from typing import Dict, Optional, List
import logging

from app.config import settings


logger = logging.getLogger(__name__)


class UazapiService:
    """Service for interacting with Uazapi WhatsApp API."""

    def __init__(self):
        self.base_url = f"https://api.uazapi.com/instance/{settings.uazapi_instance_id}"
        self.api_token = settings.uazapi_api_token
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def send_text_message(
        self,
        phone: str,
        message: str,
        message_id: Optional[str] = None
    ) -> Dict:
        """
        Send a text message via WhatsApp.

        Args:
            phone: Recipient phone number (with country code, no +)
            message: Message content
            message_id: Optional message ID to reply to

        Returns:
            API response
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "number": phone,
                    "text": message
                }

                # If replying to a message
                if message_id:
                    payload["messageId"] = message_id

                response = await client.post(
                    f"{self.base_url}/sendText",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Message sent to {phone}: {result.get('key', {}).get('id')}")
                return result

        except httpx.HTTPError as e:
            logger.error(f"Error sending message to {phone}: {e}")
            raise

    async def send_audio_message(
        self,
        phone: str,
        audio_url: str,
        message_id: Optional[str] = None
    ) -> Dict:
        """
        Send an audio message via WhatsApp.

        Args:
            phone: Recipient phone number
            audio_url: URL of the audio file
            message_id: Optional message ID to reply to

        Returns:
            API response
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "number": phone,
                    "audio": audio_url
                }

                if message_id:
                    payload["messageId"] = message_id

                response = await client.post(
                    f"{self.base_url}/sendAudio",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Audio sent to {phone}: {result.get('key', {}).get('id')}")
                return result

        except httpx.HTTPError as e:
            logger.error(f"Error sending audio to {phone}: {e}")
            raise

    async def send_media_message(
        self,
        phone: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Dict:
        """
        Send a media message (image, video, document) via WhatsApp.

        Args:
            phone: Recipient phone number
            media_url: URL of the media file
            media_type: Type of media (image, video, document)
            caption: Optional caption
            message_id: Optional message ID to reply to

        Returns:
            API response
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "number": phone,
                    media_type: media_url
                }

                if caption:
                    payload["caption"] = caption

                if message_id:
                    payload["messageId"] = message_id

                endpoint = f"send{media_type.capitalize()}"
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Media sent to {phone}: {result.get('key', {}).get('id')}")
                return result

        except httpx.HTTPError as e:
            logger.error(f"Error sending media to {phone}: {e}")
            raise

    async def get_message_status(self, message_id: str) -> Dict:
        """
        Get the status of a sent message.

        Args:
            message_id: Message ID

        Returns:
            Message status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/checkStatus/{message_id}",
                    headers=self.headers,
                    timeout=10.0
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error checking message status: {e}")
            raise

    async def download_media(self, media_url: str) -> bytes:
        """
        Download media file from Uazapi.

        Args:
            media_url: URL of the media

        Returns:
            Media content as bytes
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url,
                    headers=self.headers,
                    timeout=60.0
                )

                response.raise_for_status()
                return response.content

        except httpx.HTTPError as e:
            logger.error(f"Error downloading media: {e}")
            raise

    async def check_instance_status(self) -> Dict:
        """
        Check if the WhatsApp instance is connected and ready.

        Returns:
            Instance status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/status",
                    headers=self.headers,
                    timeout=10.0
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error checking instance status: {e}")
            raise


# Singleton instance
uazapi_service = UazapiService()
