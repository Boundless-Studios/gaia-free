"""
ElevenLabs Speech-to-Text Service
Handles audio transcription using ElevenLabs API
"""

import os
import logging
import asyncio
import base64
from typing import Optional, Dict, Any, AsyncGenerator, Callable
import aiohttp
import json

from elevenlabs import (
    ElevenLabs,
    RealtimeEvents,
    RealtimeAudioOptions,
    AudioFormat,
    CommitStrategy
)
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logger = logging.getLogger(__name__)


class ElevenLabsSTTService:
    """Service for handling speech-to-text using ElevenLabs API"""
    
    def __init__(self):
        self.api_key = os.environ.get('ELEVENLABS_API_KEY')
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def transcribe_audio(self, audio_data: bytes, audio_format: str = "webm") -> Dict[str, Any]:
        """
        Transcribe audio using ElevenLabs API
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (webm, mp3, wav, etc.)
            
        Returns:
            Dict containing transcription results
        """
        if not self.api_key:
            return {
                "error": "ElevenLabs API key not configured",
                "text": ""
            }
        
        try:
            # ElevenLabs STT endpoint
            url = f"{self.base_url}/speech-to-text"
            
            # Create form data for multipart upload
            form_data = aiohttp.FormData()
            # Map audio format to proper MIME type
            mime_types = {
                'webm': 'audio/webm',
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav',
                'ogg': 'audio/ogg',
                'm4a': 'audio/mp4',
                'flac': 'audio/flac'
            }
            content_type = mime_types.get(audio_format, f'audio/{audio_format}')
            
            form_data.add_field(
                'file',
                audio_data,
                filename=f'audio.{audio_format}',
                content_type=content_type
            )
            # Add model_id field (using their speech-to-text model)
            form_data.add_field('model_id', 'scribe_v1')
            # Force English language
            form_data.add_field('language_code', 'en')
            
            logger.info(f"Sending audio to ElevenLabs: format={audio_format}, size={len(audio_data)} bytes, language=en")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=form_data,
                    headers={"xi-api-key": self.api_key}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"ElevenLabs STT success: {result}")
                        return {
                            "text": result.get("text", ""),
                            "confidence": result.get("confidence", 1.0),
                            "language": result.get("language", "en"),
                            "segments": result.get("segments", [])
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"ElevenLabs STT error: {response.status} - {error_text}")
                        logger.error(f"Request headers: {response.request_info.headers}")
                        return {
                            "error": f"API error: {response.status} - {error_text}",
                            "text": ""
                        }
                        
        except Exception as e:
            logger.error(f"Error during ElevenLabs transcription: {e}")
            return {
                "error": str(e),
                "text": ""
            }
    
    async def transcribe_stream(self, audio_stream: asyncio.Queue) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transcribe audio stream in real-time
        
        Args:
            audio_stream: Queue containing audio chunks
            
        Yields:
            Transcription results as they become available
        """
        if not self.api_key:
            yield {
                "error": "ElevenLabs API key not configured",
                "text": ""
            }
            return
        
        # Collect audio chunks for batch processing
        audio_buffer = bytearray()
        chunk_size = 1024 * 16  # 16KB chunks
        
        stopped = False
        try:
            while not stopped:
                try:
                    # Get audio chunk with timeout
                    chunk = await asyncio.wait_for(audio_stream.get(), timeout=0.5)
                    
                    if chunk is None:  # End of stream
                        if audio_buffer:
                            # Process remaining audio
                            result = await self.transcribe_audio(bytes(audio_buffer))
                            yield result
                        break
                    
                    audio_buffer.extend(chunk)
                    
                    # Process when buffer reaches chunk size
                    if len(audio_buffer) >= chunk_size:
                        result = await self.transcribe_audio(bytes(audio_buffer))
                        yield result
                        audio_buffer.clear()
                        
                except asyncio.TimeoutError:
                    # Process buffer if we have data
                    if audio_buffer:
                        result = await self.transcribe_audio(bytes(audio_buffer))
                        yield result
                        audio_buffer.clear()
                        
        except Exception as e:
            logger.error(f"Error in stream transcription: {e}")
            yield {
                "error": str(e),
                "text": ""
            }

    async def stream_transcribe_realtime_v2(
        self,
        audio_queue: asyncio.Queue,
        on_message: Callable[[Dict[str, Any]], None],
        language: str = "en",
        sample_rate: int = 16000
    ):
        """
        Stream audio to ElevenLabs Scribe V2 Realtime API and receive transcriptions.

        Uses the official ElevenLabs Python SDK for proper connection management
        and type-safe configuration.

        Args:
            audio_queue: Queue containing audio chunks to stream
            on_message: Callback function called for each transcription message
            language: Language code (default: "en")
            sample_rate: Audio sample rate (default: 16000)
        """
        import uuid
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[{request_id}] stream_transcribe_realtime_v2 called")

        if not self.api_key:
            logger.error(f"[{request_id}] ElevenLabs API key not configured")
            await on_message({
                "error": "ElevenLabs API key not configured",
                "message_type": "error"
            })
            return

        # Create ElevenLabs client with API key
        client = ElevenLabs(api_key=self.api_key)

        # Use PCM_16000 format (matches our 16kHz audio from frontend)
        # The sample_rate parameter is passed separately to the API
        audio_format = AudioFormat.PCM_16000

        connection = None
        try:
            logger.info(f"[{request_id}] 🔌 Connecting to ElevenLabs Scribe V2 via SDK...")

            # Connect with typed options - VAD tuned for reliable commits
            # Explicit VAD parameters ensure committed_transcript events fire
            connection = await client.speech_to_text.realtime.connect(
                RealtimeAudioOptions(
                    model_id="scribe_v2_realtime",
                    language_code=language,
                    audio_format=audio_format,
                    sample_rate=sample_rate,
                    commit_strategy=CommitStrategy.VAD,
                    vad_silence_threshold_secs=1.0,  # 1 second of silence triggers commit
                    vad_threshold=0.5,  # Standard VAD sensitivity
                    min_speech_duration_ms=100,  # Minimum speech to consider
                    min_silence_duration_ms=300,  # Require 300ms sustained silence
                    include_timestamps=False,
                )
            )

            logger.info(f"[{request_id}] ✅ Connected to ElevenLabs Scribe V2")

            # Register event handlers
            def on_session_started(data):
                # Extract ElevenLabs session ID
                session_id = None
                if isinstance(data, dict):
                    session_id = data.get("session_id") or data.get("sessionId")
                elif hasattr(data, 'session_id'):
                    session_id = data.session_id
                elif hasattr(data, 'sessionId'):
                    session_id = data.sessionId

                logger.info(f"[{request_id}] 📤 ElevenLabs session started: {session_id}")
                logger.debug(f"[{request_id}] Session data: {data}")

            def on_partial_transcript(data):
                # Debug: Log full data object to see available fields (segment IDs, etc.)
                logger.debug(f"[{request_id}] 📝 Partial transcript data: {data}")
                if hasattr(data, '__dict__'):
                    logger.debug(f"[{request_id}] 📝 Partial attrs: {vars(data)}")
                elif isinstance(data, dict):
                    logger.debug(f"[{request_id}] 📝 Partial keys: {list(data.keys())}")

                # Handle both dict and SDK object types
                if isinstance(data, dict):
                    text = data.get("text", "")
                elif hasattr(data, 'text'):
                    text = data.text
                else:
                    text = str(data)
                # Forward to callback with standardized format
                asyncio.create_task(on_message({
                    "message_type": "partial_transcript",
                    "text": text
                }))

            def on_committed_transcript(data):
                # Debug: Log full data object to see available fields (segment IDs, etc.)
                logger.info(f"[{request_id}] ✅ Committed transcript data: {data}")
                if hasattr(data, '__dict__'):
                    logger.info(f"[{request_id}] ✅ Committed attrs: {vars(data)}")
                elif isinstance(data, dict):
                    logger.info(f"[{request_id}] ✅ Committed keys: {list(data.keys())}")

                # Handle both dict and SDK object types
                if isinstance(data, dict):
                    text = data.get("text", "")
                elif hasattr(data, 'text'):
                    text = data.text
                else:
                    text = str(data)
                # Forward to callback with standardized format
                # Use "committed_transcript" so websocket_handlers.py can strip cumulative prefix
                asyncio.create_task(on_message({
                    "message_type": "committed_transcript",
                    "text": text
                }))

            def on_error(error):
                logger.error(f"[{request_id}] ❌ Scribe V2 error: {error}")
                asyncio.create_task(on_message({
                    "message_type": "error",
                    "error": str(error)
                }))

            connection.on(RealtimeEvents.SESSION_STARTED, on_session_started)
            connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, on_partial_transcript)
            connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, on_committed_transcript)
            connection.on(RealtimeEvents.ERROR, on_error)

            # Stream audio from queue
            while True:
                chunk = await audio_queue.get()

                if chunk is None:  # Sentinel value to stop
                    logger.info(f"[{request_id}] 🛑 Audio stream ended, committing final transcript")
                    await connection.commit()
                    break

                # Send audio chunk (SDK handles base64 encoding)
                chunk_base64 = base64.b64encode(chunk).decode('utf-8')
                await connection.send({
                    "audio_base_64": chunk_base64,
                    "sample_rate": sample_rate
                })

        except ConnectionClosedOK as e:
            # Normal websocket closure (code 1000) - not an error
            logger.debug(f"[{request_id}] Scribe V2 connection closed normally: {e}")
        except ConnectionClosedError as e:
            # Abnormal websocket closure - log as warning
            logger.warning(f"[{request_id}] Scribe V2 connection closed unexpectedly: {e}")
            await on_message({
                "error": str(e),
                "message_type": "error"
            })
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Error in Scribe V2 streaming: {e}", exc_info=True)
            await on_message({
                "error": str(e),
                "message_type": "error"
            })
        finally:
            if connection:
                try:
                    await connection.close()
                    logger.info(f"[{request_id}] 🔌 Closed Scribe V2 connection")
                except Exception as e:
                    logger.warning(f"[{request_id}] Error closing connection: {e}")


# Singleton instance
_stt_service = None


def get_elevenlabs_stt_service() -> ElevenLabsSTTService:
    """Get or create the ElevenLabs STT service singleton"""
    global _stt_service
    if _stt_service is None:
        _stt_service = ElevenLabsSTTService()
    return _stt_service