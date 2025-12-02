"""Audio recording service for capturing and managing audio streams."""

import os
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json

logger = logging.getLogger(__name__)

class AudioRecorder:
    """Manages audio recording sessions and buffers."""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.audio_chunks: Dict[str, List[bytes]] = {}
        self.transcriptions: Dict[str, List[str]] = {}
        
        # Recording settings
        self.max_session_duration = 3600  # 1 hour max
        self.chunk_size = 1024 * 1024  # 1MB chunks
        self.max_buffer_chunks = 750  # 5 minutes of audio
        
        # Storage directory - use config or environment variable
        from ..config import get_settings
        settings = get_settings()
        self.storage_dir = settings.recording_storage_path
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def create_session(self, user_id: str) -> str:
        """Create a new recording session."""
        session_id = str(uuid.uuid4())
        
        self.sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "start_time": datetime.now().isoformat(),
            "status": "recording",
            "metadata": {}
        }
        
        self.audio_chunks[session_id] = []
        self.transcriptions[session_id] = []
        
        logger.info(f"Created recording session: {session_id}")
        return session_id
    
    def add_audio_chunk(self, session_id: str, chunk_data: bytes) -> bool:
        """Add an audio chunk to a session."""
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return False
        
        if self.sessions[session_id]["status"] != "recording":
            logger.error(f"Session not recording: {session_id}")
            return False
        
        # Add chunk to buffer
        self.audio_chunks[session_id].append(chunk_data)
        
        # Maintain buffer size limit
        if len(self.audio_chunks[session_id]) > self.max_buffer_chunks:
            # Remove oldest chunks
            self.audio_chunks[session_id] = self.audio_chunks[session_id][-self.max_buffer_chunks:]
            logger.debug(f"Trimmed audio buffer for session {session_id}")
        
        # Log progress
        return True
    
    def get_audio_buffer(self, session_id: str) -> Optional[bytes]:
        """Get the current audio buffer for a session."""
        if session_id not in self.audio_chunks:
            return None
        
        if not self.audio_chunks[session_id]:
            return None
        
        # Combine all chunks
        return b''.join(self.audio_chunks[session_id])
    
    def clear_audio_buffer(self, session_id: str) -> None:
        """Clear the audio buffer for a session."""
        if session_id in self.audio_chunks:
            self.audio_chunks[session_id] = []
            logger.debug(f"Cleared audio buffer for session {session_id}")
    
    def add_transcription(self, session_id: str, text: str, timestamp: Optional[float] = None):
        """Add transcription text to a session."""
        if session_id not in self.sessions:
            return
        
        self.transcriptions[session_id].append({
            "text": text,
            "timestamp": timestamp or datetime.now().timestamp()
        })
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id].copy()
        session["buffer_size"] = len(self.audio_chunks.get(session_id, []))
        session["transcription_count"] = len(self.transcriptions.get(session_id, []))
        
        return session
    
    async def stop_session(self, session_id: str) -> Optional[str]:
        """Stop a recording session and save the audio."""
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return None
        
        self.sessions[session_id]["status"] = "stopped"
        self.sessions[session_id]["end_time"] = datetime.now().isoformat()
        
        # Save combined audio if present
        if self.audio_chunks.get(session_id):
            combined_audio = b''.join(self.audio_chunks[session_id])
            
            # Save to file
            audio_path = os.path.join(self.storage_dir, f"{session_id}.webm")
            with open(audio_path, 'wb') as f:
                f.write(combined_audio)
            
            # Save metadata
            metadata_path = os.path.join(self.storage_dir, f"{session_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump({
                    "session": self.sessions[session_id],
                    "transcriptions": self.transcriptions.get(session_id, [])
                }, f, indent=2)
            
            logger.info(f"Saved session {session_id}: audio={audio_path}, metadata={metadata_path}")
            
            # Clean up memory
            self.clear_session(session_id)
            
            return audio_path
        
        return None
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a recording session."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        duration = 0
        if session["start_time"] and session.get("end_time"):
            duration = session["end_time"] - session["start_time"]
        elif session["start_time"]:
            duration = time.time() - session["start_time"]
        
        return {
            "status": session["status"],
            "duration": duration,
            "user_id": session.get("user_id"),
            "start_time": session.get("start_time"),
            "end_time": session.get("end_time")
        }
    
    def get_transcription(self, session_id: str) -> str:
        """Get the transcription for a session."""
        return " ".join(self.transcriptions.get(session_id, []))
    
    def clear_session(self, session_id: str) -> None:
        """Clear all data for a session from memory."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.audio_chunks:
            del self.audio_chunks[session_id]
        if session_id in self.transcriptions:
            del self.transcriptions[session_id]
        
        logger.debug(f"Cleared session {session_id} from memory")
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            self.get_session_info(session_id)
            for session_id in self.sessions
        ]


# Singleton instance
_audio_recorder = None


def get_audio_recorder() -> AudioRecorder:
    """Get or create the audio recorder singleton"""
    global _audio_recorder
    if _audio_recorder is None:
        _audio_recorder = AudioRecorder()
    return _audio_recorder