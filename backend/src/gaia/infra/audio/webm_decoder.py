"""WebM audio decoder for voice activity detection."""

import subprocess
import tempfile
import os
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def decode_webm_chunk(webm_data: bytes) -> Optional[np.ndarray]:
    """
    Decode WebM chunk to raw PCM audio for analysis.
    
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
                tmp_pcm_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
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
        logger.error(f"Error decoding WebM chunk: {e}")
        return None


def analyze_audio_chunk(audio_array: np.ndarray, sample_rate: int = 48000) -> Tuple[bool, float, dict]:
    """
    Analyze audio chunk for voice activity using frequency analysis.
    
    Args:
        audio_array: Raw audio samples
        sample_rate: Sample rate (default 48kHz)
        
    Returns:
        Tuple of (has_voice, confidence, analysis_data)
    """
    if len(audio_array) == 0:
        return False, 0.0, {}
    
    # Calculate RMS (volume)
    rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))
    rms_normalized = min(100, (rms / 32768) * 100)
    
    # Perform FFT for frequency analysis
    fft = np.fft.rfft(audio_array)
    freqs = np.fft.rfftfreq(len(audio_array), 1/sample_rate)
    magnitude = np.abs(fft)
    
    # Voice frequency range (85-2500 Hz)
    voice_mask = (freqs >= 85) & (freqs <= 2500)
    voice_energy = np.sum(magnitude[voice_mask])
    total_energy = np.sum(magnitude)
    
    voice_ratio = voice_energy / total_energy if total_energy > 0 else 0
    
    # Find dominant frequency
    dominant_freq_idx = np.argmax(magnitude[voice_mask])
    dominant_freq = freqs[voice_mask][dominant_freq_idx] if len(magnitude[voice_mask]) > 0 else 0
    
    # Voice detection criteria
    has_voice = (
        rms_normalized > 2.5 and  # Minimum volume (increased from 1.0)
        voice_ratio > 0.35 and    # Significant energy in voice frequencies (increased from 0.3)
        dominant_freq > 100       # Dominant frequency in voice range
    )
    
    # Calculate confidence
    confidence = min(100, (rms_normalized * voice_ratio))
    
    analysis_data = {
        'rms': rms_normalized,
        'voice_ratio': voice_ratio,
        'dominant_freq': dominant_freq
    }
    
    return has_voice, confidence, analysis_data