import os
import tempfile
from typing import Optional
from faster_whisper import WhisperModel
import logging

from app.config import settings
from app.services.uazapi_service import uazapi_service


logger = logging.getLogger(__name__)


class AudioService:
    """Service for processing audio messages."""

    def __init__(self):
        # Initialize Faster Whisper model
        # Use "tiny" or "base" for faster processing, "small" for better accuracy
        model_size = os.getenv("WHISPER_MODEL", "base")
        device = "cpu"  # or "cuda" if GPU is available

        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type="int8"  # Use "float16" for GPU
            )
            logger.info(f"Faster Whisper initialized with model: {model_size}")
        except Exception as e:
            logger.error(f"Error initializing Whisper model: {e}")
            self.model = None

    async def transcribe_audio(self, audio_url: str, language: str = "pt") -> str:
        """
        Transcribe audio message using Faster Whisper.

        Args:
            audio_url: URL of the audio file
            language: Language code (default: pt for Portuguese)

        Returns:
            Transcribed text
        """
        try:
            # Download audio from Uazapi
            logger.info(f"Downloading audio from: {audio_url}")
            audio_data = await uazapi_service.download_media(audio_url)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe using Faster Whisper
                if not self.model:
                    raise RuntimeError("Whisper model not initialized")

                segments, info = self.model.transcribe(
                    temp_path,
                    language=language,
                    beam_size=5
                )

                # Combine all segments
                transcript_parts = []
                for segment in segments:
                    transcript_parts.append(segment.text)

                transcript = " ".join(transcript_parts).strip()

                logger.info(f"Audio transcribed ({info.language} {info.language_probability:.2f}): {transcript[:50]}...")
                return transcript

            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

    async def transcribe_audio_with_fallback(
        self,
        audio_url: str,
        language: str = "pt"
    ) -> str:
        """
        Transcribe with fallback to different language detection.

        Args:
            audio_url: URL of the audio file
            language: Primary language code

        Returns:
            Transcribed text
        """
        try:
            return await self.transcribe_audio(audio_url, language)
        except Exception as e:
            logger.warning(f"Primary transcription failed: {e}")
            # Try without language specification
            try:
                return await self.transcribe_audio(audio_url, None)
            except Exception as e2:
                logger.error(f"Fallback transcription also failed: {e2}")
                raise


# Singleton instance
audio_service = AudioService()
