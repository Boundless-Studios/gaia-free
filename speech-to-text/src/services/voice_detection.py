"""
Voice Activity Detection Service
Provides frequency-based voice detection for audio streams
"""

import numpy as np
import logging
from typing import Optional, Tuple, Dict
import time
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


class VoiceDetectionService:
    """Service for detecting voice activity in audio streams"""
    
    def __init__(self):
        # Voice detection parameters (must match backend exactly)
        self.voice_freq_min = 85  # Hz - minimum human voice frequency
        self.voice_freq_max = 2500  # Hz - maximum relevant voice frequency (matching backend)
        self.energy_threshold = 0.01  # Minimum energy threshold
        self.voice_activity_duration = 1000  # ms - how long voice is considered active
        self.silence_threshold = 2000  # ms - silence duration to end segment
        
        # Activity tracking
        self.voice_activity_tracker = {}
        
    def decode_webm_to_pcm(self, webm_data: bytes) -> Optional[np.ndarray]:
        """
        Decode WebM audio data to raw PCM for frequency analysis.
        
        Args:
            webm_data: WebM encoded audio data
            
        Returns:
            Numpy array of audio samples, or None if decoding fails
        """
        try:
            # Write WebM data to temporary file
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_webm:
                tmp_webm.write(webm_data)
                tmp_webm_path = tmp_webm.name
            
            # Output temporary file for PCM
            tmp_pcm_path = tmp_webm_path.replace('.webm', '.pcm')
            
            try:
                # Use ffmpeg to decode WebM to raw PCM
                # -f s16le: 16-bit signed little-endian
                # -ar 48000: 48kHz sample rate
                # -ac 1: mono
                cmd = [
                    'ffmpeg', '-i', tmp_webm_path,
                    '-f', 's16le',
                    '-ar', '48000',
                    '-ac', '1',
                    '-y',  # Overwrite output
                    '-loglevel', 'error',  # Only show errors
                    tmp_pcm_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.debug(f"FFmpeg decoding failed: {result.stderr}")
                    return None
                
                # Read PCM data
                if os.path.exists(tmp_pcm_path) and os.path.getsize(tmp_pcm_path) > 0:
                    with open(tmp_pcm_path, 'rb') as f:
                        pcm_data = f.read()
                    
                    # Convert to numpy array
                    audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                    return audio_array
                else:
                    return None
                    
            finally:
                # Clean up temporary files
                if os.path.exists(tmp_webm_path):
                    os.unlink(tmp_webm_path)
                if os.path.exists(tmp_pcm_path):
                    os.unlink(tmp_pcm_path)
                    
        except Exception as e:
            logger.debug(f"Error decoding WebM: {e}")
            return None
    
    def detect_voice_in_webm(self, webm_data: bytes, use_advanced: bool = True) -> Tuple[bool, float]:
        """
        Detect voice activity in WebM audio data (matches backend implementation).
        
        Args:
            webm_data: WebM audio data
            use_advanced: If True, use frequency analysis
            
        Returns:
            Tuple of (has_voice, confidence_level)
        """
        chunk_size = len(webm_data)
        
        # Basic size check
        if chunk_size < 100:
            return False, 0.0
        
        if use_advanced:
            # Decode and analyze frequencies
            audio_array = self.decode_webm_to_pcm(webm_data)
            if audio_array is not None and len(audio_array) > 0:
                # Perform frequency analysis
                has_voice, confidence = self.analyze_audio_frequencies(audio_array, sample_rate=48000)
                return has_voice, confidence
        
        # Fallback to size-based detection
        if chunk_size < 500:
            return False, 0.0
        elif chunk_size < 1200:
            return False, 20.0
        elif chunk_size < 2000:
            return False, 45.0
        elif chunk_size < 3500:
            return True, 70.0
        else:
            return True, 85.0
    
    def analyze_audio_frequencies(self, audio_array: np.ndarray, sample_rate: int = 48000) -> Tuple[bool, float]:
        """
        Analyze audio frequencies for voice detection (matches backend exactly).
        
        Returns:
            Tuple of (has_voice, confidence)
        """
        if len(audio_array) == 0:
            return False, 0.0
        
        # Convert to float and normalize
        audio_array = audio_array.astype(np.float32) / 32768.0
        
        # Calculate RMS (volume)
        rms = np.sqrt(np.mean(audio_array ** 2))
        rms_normalized = min(100, rms * 100)
        
        # Perform FFT for frequency analysis
        fft = np.fft.rfft(audio_array)
        freqs = np.fft.rfftfreq(len(audio_array), 1/sample_rate)
        magnitude = np.abs(fft)
        
        # Voice frequency range (85-2500 Hz)
        voice_mask = (freqs >= self.voice_freq_min) & (freqs <= self.voice_freq_max)
        if len(magnitude[voice_mask]) == 0:
            return False, 0.0
            
        voice_energy = np.sum(magnitude[voice_mask] ** 2)
        total_energy = np.sum(magnitude ** 2)
        
        voice_ratio = voice_energy / total_energy if total_energy > 0 else 0
        
        # Find dominant frequency
        dominant_freq = 0
        if len(magnitude[voice_mask]) > 0:
            dominant_freq_idx = np.argmax(magnitude[voice_mask])
            dominant_freq = freqs[voice_mask][dominant_freq_idx]
        
        # Voice detection criteria (matching backend exactly)
        has_voice = (
            rms_normalized > 2.5 and  # Minimum volume
            voice_ratio > 0.35 and    # Significant energy in voice frequencies
            dominant_freq > 100       # Dominant frequency in voice range
        )
        
        # Calculate confidence
        confidence = min(100, rms_normalized * voice_ratio)
        
        # Debug logging to understand what's happening
        if rms_normalized > 0.5:  # Only log if there's some audio
            logger.debug(f"Frequency analysis: rms={rms_normalized:.1f}, voice_ratio={voice_ratio:.2f}, dominant_freq={dominant_freq:.0f}Hz")
        
        return has_voice, confidence
    
    def detect_voice_in_audio(self, audio_data: bytes, sample_rate: int = 48000) -> bool:
        """
        Detect if audio contains voice using frequency analysis
        
        Args:
            audio_data: Raw audio bytes (WebM encoded)
            sample_rate: Audio sample rate in Hz
            
        Returns:
            True if voice is detected, False otherwise
        """
        try:
            # First decode WebM to PCM
            audio_array = self.decode_webm_to_pcm(audio_data)
            
            if audio_array is None or len(audio_array) == 0:
                return False
            
            # Convert to float and normalize
            audio_array = audio_array.astype(np.float32)
            
            if len(audio_array) == 0:
                return False
            
            # Normalize audio
            audio_array = audio_array / 32768.0
            
            # Calculate energy
            energy = np.mean(audio_array ** 2)
            
            # Check if energy is above threshold
            if energy < self.energy_threshold:
                return False
            
            # Perform FFT for frequency analysis
            fft = np.fft.rfft(audio_array)
            freqs = np.fft.rfftfreq(len(audio_array), 1/sample_rate)
            
            # Get magnitude spectrum
            magnitude = np.abs(fft)
            
            # Find frequencies in voice range
            voice_indices = np.where(
                (freqs >= self.voice_freq_min) & 
                (freqs <= self.voice_freq_max)
            )[0]
            
            if len(voice_indices) == 0:
                return False
            
            # Calculate energy in voice frequency range
            voice_energy = np.sum(magnitude[voice_indices] ** 2)
            total_energy = np.sum(magnitude ** 2)
            
            # Check if voice frequencies dominate (matching backend threshold)
            if total_energy > 0:
                voice_ratio = voice_energy / total_energy
                has_voice = voice_ratio > 0.35  # Voice should be at least 35% of total energy (matching backend)
                
                if has_voice:
                    logger.debug(f"Voice detected: energy={energy:.4f}, voice_ratio={voice_ratio:.2f}")
                
                return has_voice
            
            return False
            
        except Exception as e:
            logger.error(f"Error in voice detection: {e}")
            return False
    
    def update_activity(self, session_id: str, has_voice: bool) -> None:
        """
        Update voice activity tracking for a session
        
        Args:
            session_id: Session identifier
            has_voice: Whether voice was detected
        """
        current_time = int(time.time() * 1000)  # milliseconds
        
        if has_voice:
            self.voice_activity_tracker[session_id] = current_time
            logger.debug(f"Voice activity updated for session {session_id}")
    
    def get_activity_status(self, session_id: str) -> bool:
        """
        Check if voice was detected recently for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if voice was detected within the activity duration
        """
        if session_id not in self.voice_activity_tracker:
            return False
        
        last_voice_time = self.voice_activity_tracker[session_id]
        current_time = int(time.time() * 1000)
        time_since_voice = current_time - last_voice_time
        
        is_active = time_since_voice < self.voice_activity_duration
        
        if is_active:
            logger.debug(f"Voice is active for session {session_id} (last: {time_since_voice}ms ago)")
        
        return is_active
    
    def check_silence_threshold(self, session_id: str) -> bool:
        """
        Check if silence threshold has been reached
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if silence threshold exceeded
        """
        if session_id not in self.voice_activity_tracker:
            return True
        
        last_voice_time = self.voice_activity_tracker[session_id]
        current_time = int(time.time() * 1000)
        time_since_voice = current_time - last_voice_time
        
        return time_since_voice >= self.silence_threshold
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear voice activity tracking for a session
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.voice_activity_tracker:
            del self.voice_activity_tracker[session_id]
            logger.debug(f"Cleared voice activity for session {session_id}")


# Singleton instance
_voice_detection_service = None


def get_voice_detection_service() -> VoiceDetectionService:
    """Get or create the voice detection service singleton"""
    global _voice_detection_service
    if _voice_detection_service is None:
        _voice_detection_service = VoiceDetectionService()
    return _voice_detection_service