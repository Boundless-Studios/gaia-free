"""WebSocket handlers for real-time audio transcription"""

import asyncio
import json
import logging
import time
import base64
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
import numpy as np

from .services.elevenlabs_stt import get_elevenlabs_stt_service
from .services.connection_pool import get_connection_pool
from .scribe_message_processor import ScribeMessageProcessor
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def _accept_websocket_with_subprotocol(websocket: WebSocket) -> None:
    """Accept the websocket, preserving negotiated subprotocol when available.

    This is required for subprotocol-based auth (token passed via Sec-WebSocket-Protocol).
    The browser will close the connection with 1006 if the server doesn't echo
    back the accepted subprotocol.
    """
    subprotocol = None
    scope = getattr(websocket, "scope", None)
    if isinstance(scope, dict):
        # Check 'subprotocols' (plural) - the list of protocols offered by client
        # This is available BEFORE accept(), unlike 'subprotocol' (singular)
        subprotocols = scope.get("subprotocols", [])
        if subprotocols:
            # Accept the first offered subprotocol (which contains our auth token)
            subprotocol = subprotocols[0]
            logger.debug(f"🔐 Accepting WebSocket with subprotocol: {subprotocol[:20]}...")

    try:
        if subprotocol is not None:
            await websocket.accept(subprotocol=subprotocol)
            return
    except TypeError:
        # Fallback for stubs that don't support keyword arguments
        pass

    await websocket.accept()

# Global voice activity tracking (session_id -> last_voice_timestamp)
voice_activity_tracker = {}

def get_voice_activity_status(session_id: str) -> bool:
    """Check if voice was detected in the last VOICE_ACTIVITY_DURATION_MS milliseconds."""
    import time
    if session_id not in voice_activity_tracker:
        return False
    
    last_voice_time = voice_activity_tracker[session_id]
    current_time = time.time() * 1000  # Convert to milliseconds
    time_since_voice = current_time - last_voice_time
    is_active = time_since_voice < settings.voice_activity_duration_ms
    
    return is_active


async def handle_simple_transcription_websocket(websocket: WebSocket, user_info: Optional[Dict[str, Any]] = None):
    """
    Handle simple audio transcription (complete audio at once)

    Args:
        websocket: FastAPI WebSocket connection
    """
    await _accept_websocket_with_subprotocol(websocket)
    
    stt_service = get_elevenlabs_stt_service()
    audio_chunks = []
    
    try:
        while True:
            try:
                # Receive message
                message = await websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    break
                
                data = None
                if "bytes" in message:
                    data = message["bytes"]
                elif "text" in message:
                    text_data = message["text"]
                    json_data = json.loads(text_data)
                    
                    # Handle control messages
                    if json_data.get("type") == "transcribe":
                        # Transcribe accumulated audio
                        if audio_chunks:
                            combined_audio = b''.join(audio_chunks)
                            logger.info(f"Transcribing {len(combined_audio)} bytes")
                            
                            result = await stt_service.transcribe_audio(
                                combined_audio,
                                audio_format=json_data.get("format", "webm")
                            )
                            
                            await websocket.send_json({
                                "event": "transcription_segment",
                                "data": {
                                    "text": result.get("text", ""),
                                    "error": result.get("error"),
                                    "confidence": result.get("confidence", 1.0),
                                    "timestamp": time.time()
                                }
                            })
                            
                            # Clear chunks
                            audio_chunks.clear()
                    elif json_data.get("type") == "clear":
                        audio_chunks.clear()
                        logger.info("Cleared audio chunks")
                    
                    # Handle base64 audio
                    if "audio" in json_data:
                        data = base64.b64decode(json_data["audio"])
                
                if data:
                    audio_chunks.append(data)
                    logger.debug(f"Added chunk, total chunks: {len(audio_chunks)}")
                    
            except WebSocketDisconnect:
                logger.info("Simple transcription WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"Error in simple transcription: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                    "timestamp": time.time()
                })

    finally:
        logger.info("Simple transcription WebSocket handler completed")


async def handle_scribe_v2_realtime_websocket(websocket: WebSocket, user_info: Optional[Dict[str, Any]] = None):
    """
    Handle real-time transcription using ElevenLabs Scribe V2 Realtime API.
    Falls back to Scribe V1 (batch API) if V2 fails (e.g., insufficient funds).

    This handler proxies audio from the frontend to ElevenLabs Scribe V2 WebSocket,
    providing real-time streaming transcription with built-in VAD.

    Args:
        websocket: FastAPI WebSocket connection from frontend
        user_info: Optional user authentication info
    """
    await _accept_websocket_with_subprotocol(websocket)
    logger.info("🔌 Scribe V2 WebSocket connection accepted")

    # Connection pool for rate limiting
    request_id = f"scribe_{id(websocket)}_{time.time()}"
    connection_pool = get_connection_pool(max_connections=20)
    slot_acquired = False

    # Callback for pool status updates
    async def notify_queue_status(event_type: str, data: dict):
        """Send queue status updates to the client"""
        try:
            await websocket.send_json({
                "event": event_type,
                "data": data
            })
        except Exception as e:
            logger.warning(f"Failed to send queue status: {e}")

    stt_service = get_elevenlabs_stt_service()
    audio_queue = asyncio.Queue()
    scribe_task = None
    use_v1_fallback = False
    v2_error = None
    first_client_audio_received = False
    ready_sent_at = None

    # Error callback for V1 fallback on billing errors
    async def handle_billing_error(error: str):
        nonlocal use_v1_fallback, v2_error
        v2_error = error
        use_v1_fallback = True
        logger.info("📝 Will fall back to Scribe V1 (batch API)")

    # Create message processor with timer-based commit handling
    processor = ScribeMessageProcessor(
        send_callback=websocket.send_json,
        on_error=handle_billing_error,
        timer_delay_secs=2.0
    )

    # TODO Move into scribe_message_processor
    # Callback for handling messages from ElevenLabs V2
    async def on_scribe_message(message: Dict[str, Any]):
        """Forward transcription messages from ElevenLabs to frontend"""
        try:
            await processor.process_message(message)
        except Exception as e:
            logger.error(f"❌ Error forwarding Scribe message: {e}")

    try:
        # Acquire connection pool slot
        logger.info(f"🔄 Requesting connection slot for {request_id}")
        slot_acquired = await connection_pool.acquire(request_id, notify_queue_status)

        if not slot_acquired:
            logger.info(f"❌ Connection cancelled while queued: {request_id}")
            return

        logger.debug(f"✅ Connection slot acquired for {request_id}")

        # Notify frontend that we're ready to receive audio
        await websocket.send_json({
            "event": "ready",
            "data": {
                "message": "Ready for audio",
                "timestamp": time.time()
            }
        })
        ready_sent_at = time.time()

        # Start the Scribe V2 streaming task
        scribe_task = asyncio.create_task(
            stt_service.stream_transcribe_realtime_v2(
                audio_queue=audio_queue,
                on_message=on_scribe_message
            )
        )

        logger.info("✅ Scribe V2 streaming task started")

        # Collect audio chunks in case we need V1 fallback
        audio_chunks = []

        # Forward audio from frontend to ElevenLabs
        while True:
            try:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    logger.debug("🔌 Frontend WebSocket disconnected")
                    break

                # Handle binary audio data
                if "bytes" in message:
                    audio_data = message["bytes"]
                    # Always collect for potential V1 fallback
                    audio_chunks.append(audio_data)
                    await audio_queue.put(audio_data)
                    logger.debug(f"📤 Forwarded {len(audio_data)} bytes to Scribe V2")

                    if not first_client_audio_received:
                        first_client_audio_received = True
                        delta_ms = 0
                        if ready_sent_at:
                            delta_ms = int((time.time() - ready_sent_at) * 1000)
                        logger.info(f"⏱️ First audio chunk received from client ({len(audio_data)} bytes) {delta_ms}ms after ready")

                    # Check if V2 failed and we need to switch to V1
                    if use_v1_fallback:
                        logger.info("🔄 Switching to V1 fallback mode")
                        # Cancel V2 task
                        if scribe_task:
                            scribe_task.cancel()
                        # Run V1 fallback loop
                        await _run_v1_fallback_loop(websocket, stt_service, audio_chunks)
                        return

                # Handle control messages
                elif "text" in message:
                    try:
                        json_data = json.loads(message["text"])

                        if json_data.get("type") == "stop":
                            logger.info("🛑 Stop command received")
                            break

                        elif json_data.get("type") == "ping":
                            await websocket.send_json({"event": "pong", "data": {}})

                    except json.JSONDecodeError:
                        logger.warning("⚠️ Received non-JSON text message")

            except WebSocketDisconnect:
                logger.info("🔌 WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"❌ Error in WebSocket loop: {e}")
                await websocket.send_json({
                    "event": "error",
                    "data": {
                        "message": str(e),
                        "timestamp": time.time()
                    }
                })

    except Exception as e:
        error_str = str(e)
        logger.error(f"❌ Error in Scribe V2 handler: {e}")

        # Check if this is a V2 connection failure that should trigger fallback
        if "insufficient_funds" in error_str.lower() or "billing" in error_str.lower():
            logger.info("📝 V2 failed, falling back to V1 batch API")
            try:
                await websocket.send_json({
                    "event": "info",
                    "data": {
                        "message": "Using batch transcription mode",
                        "timestamp": time.time()
                    }
                })
                await _run_v1_fallback_loop(websocket, stt_service, [])
                return
            except Exception as fallback_error:
                logger.error(f"❌ V1 fallback also failed: {fallback_error}")

        try:
            await websocket.send_json({
                "event": "error",
                "data": {
                    "message": f"Transcription error: {error_str}",
                    "timestamp": time.time()
                }
            })
        except:
            pass

    finally:
        # Flush any pending transcription before closing
        try:
            await processor.cleanup()
        except Exception as e:
            logger.warning(f"Failed to cleanup processor: {e}")

        # Release connection pool slot
        if slot_acquired:
            await connection_pool.release(request_id)
        else:
            # Cancel queued request if we're still waiting
            connection_pool.cancel_queued(request_id)

        # Signal end of audio stream to Scribe V2
        try:
            await audio_queue.put(None)
        except:
            pass

        # Wait for Scribe task to complete
        if scribe_task:
            try:
                await asyncio.wait_for(scribe_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Scribe V2 task did not complete in time")
                scribe_task.cancel()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        logger.debug("🏁 Scribe V2 WebSocket handler completed")


async def _run_v1_fallback_loop(
    websocket: WebSocket,
    stt_service,
    initial_chunks: list
):
    """
    Run V1 (batch API) fallback mode for transcription.

    Buffers audio and periodically sends to batch API for transcription.
    Uses simple silence detection based on audio energy levels.

    Args:
        websocket: Client WebSocket connection
        stt_service: ElevenLabs STT service instance
        initial_chunks: Any audio chunks already collected before fallback
    """
    logger.info("📝 Starting V1 fallback loop")

    # Notify frontend we're in batch mode
    await websocket.send_json({
        "event": "info",
        "data": {
            "message": "Using batch transcription (V1)",
            "mode": "batch",
            "timestamp": time.time()
        }
    })

    # Audio buffer and timing
    audio_buffer = list(initial_chunks)
    last_transcribe_time = time.time()
    BATCH_INTERVAL_SECS = 2.5  # Transcribe every 2.5 seconds of audio
    MIN_AUDIO_BYTES = 8000  # Minimum audio to transcribe (~0.25s at 16kHz 16-bit)

    try:
        while True:
            try:
                # Use timeout to periodically check if we should transcribe
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=0.5
                )

                if message["type"] == "websocket.disconnect":
                    logger.debug("🔌 Frontend WebSocket disconnected (V1 mode)")
                    break

                # Handle binary audio data
                if "bytes" in message:
                    audio_data = message["bytes"]
                    audio_buffer.append(audio_data)
                    logger.debug(f"📥 V1: Buffered {len(audio_data)} bytes")

                # Handle control messages
                elif "text" in message:
                    try:
                        json_data = json.loads(message["text"])
                        if json_data.get("type") == "stop":
                            logger.info("🛑 Stop command received (V1 mode)")
                            break
                        elif json_data.get("type") == "ping":
                            await websocket.send_json({"event": "pong", "data": {}})
                    except json.JSONDecodeError:
                        pass

            except asyncio.TimeoutError:
                # Check if we should transcribe the buffer
                pass
            except WebSocketDisconnect:
                logger.info("🔌 WebSocket disconnected (V1 mode)")
                break

            # Check if we should transcribe
            current_time = time.time()
            time_since_last = current_time - last_transcribe_time
            total_audio_bytes = sum(len(chunk) for chunk in audio_buffer)

            if audio_buffer and (
                time_since_last >= BATCH_INTERVAL_SECS or
                total_audio_bytes >= 64000  # ~2s of audio at 16kHz 16-bit
            ):
                if total_audio_bytes >= MIN_AUDIO_BYTES:
                    # Combine and transcribe
                    combined_audio = b''.join(audio_buffer)
                    audio_buffer.clear()
                    last_transcribe_time = current_time

                    logger.debug(f"📤 V1: Sending {len(combined_audio)} bytes for transcription")

                    try:
                        # Convert PCM to WAV format for batch API
                        wav_audio = _pcm_to_wav(combined_audio, sample_rate=16000)

                        result = await stt_service.transcribe_audio(
                            wav_audio,
                            audio_format="wav"
                        )

                        if result.get("text"):
                            text = result["text"].strip()
                            if text:
                                # Add period for sentence separation
                                text = text + ". "
                                logger.info(f"✅ V1 Transcription: {text}")
                                await websocket.send_json({
                                    "event": "transcription_segment",
                                    "data": {
                                        "text": text,
                                        "is_final": True,
                                        "mode": "batch",
                                        "timestamp": time.time()
                                    }
                                })
                        elif result.get("error"):
                            error_msg = result['error']
                            logger.error(f"❌ V1 transcription error: {error_msg}")
                            # Check for quota/billing errors - stop retrying
                            if "quota" in error_msg.lower() or "billing" in error_msg.lower() or "insufficient" in error_msg.lower():
                                logger.error("💸 V1 API quota exhausted - stopping transcription")
                                await websocket.send_json({
                                    "event": "error",
                                    "data": {
                                        "message": "Transcription quota exhausted. Please try again later.",
                                        "code": "quota_exceeded",
                                        "timestamp": time.time()
                                    }
                                })
                                return  # Exit the fallback loop

                    except Exception as e:
                        logger.error(f"❌ V1 transcription failed: {e}")

        # Transcribe any remaining audio
        if audio_buffer:
            total_audio_bytes = sum(len(chunk) for chunk in audio_buffer)
            if total_audio_bytes >= MIN_AUDIO_BYTES:
                combined_audio = b''.join(audio_buffer)
                logger.info(f"📤 V1: Final transcription of {len(combined_audio)} bytes")

                try:
                    wav_audio = _pcm_to_wav(combined_audio, sample_rate=16000)
                    result = await stt_service.transcribe_audio(wav_audio, audio_format="wav")

                    if result.get("text"):
                        text = result["text"].strip()
                        if text:
                            text = text + ". "
                            await websocket.send_json({
                                "event": "transcription_segment",
                                "data": {
                                    "text": text,
                                    "is_final": True,
                                    "mode": "batch",
                                    "timestamp": time.time()
                                }
                            })
                except Exception as e:
                    logger.error(f"❌ V1 final transcription failed: {e}")

    except Exception as e:
        logger.error(f"❌ Error in V1 fallback loop: {e}")

    logger.info("🏁 V1 fallback loop completed")


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """
    Convert raw PCM audio data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes (16-bit signed integers)
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        bits_per_sample: Bits per sample

    Returns:
        WAV file bytes
    """
    import struct
    import io

    # WAV header
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)
    file_size = 36 + data_size

    wav_buffer = io.BytesIO()

    # RIFF header
    wav_buffer.write(b'RIFF')
    wav_buffer.write(struct.pack('<I', file_size))
    wav_buffer.write(b'WAVE')

    # fmt chunk
    wav_buffer.write(b'fmt ')
    wav_buffer.write(struct.pack('<I', 16))  # Subchunk1Size (16 for PCM)
    wav_buffer.write(struct.pack('<H', 1))   # AudioFormat (1 = PCM)
    wav_buffer.write(struct.pack('<H', channels))
    wav_buffer.write(struct.pack('<I', sample_rate))
    wav_buffer.write(struct.pack('<I', byte_rate))
    wav_buffer.write(struct.pack('<H', block_align))
    wav_buffer.write(struct.pack('<H', bits_per_sample))

    # data chunk
    wav_buffer.write(b'data')
    wav_buffer.write(struct.pack('<I', data_size))
    wav_buffer.write(pcm_data)

    return wav_buffer.getvalue()
