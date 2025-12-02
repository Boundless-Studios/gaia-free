"""Windows audio utilities for WSL environments."""

import os
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class WindowsAudioRouter:
    """Routes audio through Windows audio system for proper capture by screen sharing tools."""
    
    def __init__(self):
        self.windows_temp_dir = "C:\\Windows\\Temp\\gaia_audio"
        self.wsl_temp_dir = "/mnt/c/Windows/Temp/gaia_audio"
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure Windows temp directory exists."""
        try:
            os.makedirs(self.wsl_temp_dir, exist_ok=True)
            logger.info(f"Windows audio directory ready: {self.windows_temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create Windows audio directory: {e}")
    
    async def play_through_windows(self, audio_path: str) -> bool:
        """
        Play audio through Windows audio system invisibly for screen sharing.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            True if playback succeeded, False otherwise
        """
        try:
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return False
            
            # Copy to Windows accessible location
            filename = os.path.basename(audio_path)
            windows_audio_path = os.path.join(self.wsl_temp_dir, filename)
            
            # Copy file to Windows temp
            copy_cmd = f"cp '{audio_path}' '{windows_audio_path}'"
            copy_process = await asyncio.create_subprocess_shell(
                copy_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await copy_process.communicate()
            
            if copy_process.returncode != 0:
                logger.error(f"Failed to copy audio to Windows: {audio_path}")
                return False
            
            # Convert to Windows path
            windows_path = f"{self.windows_temp_dir}\\{filename}"
            
            # Check file extension
            file_ext = filename.lower().split('.')[-1]
            
            # For MP3 files, use Windows Media ActiveX invisibly
            if file_ext == 'mp3':
                logger.info(f"Playing MP3 invisibly: {windows_path}")
                
                # Create a VBScript for truly invisible MP3 playback that waits for completion
                vbs_content = f'''Set objPlayer = CreateObject("WMPlayer.OCX")
objPlayer.URL = "{windows_path}"
objPlayer.settings.volume = 100
objPlayer.controls.play
While objPlayer.playState <> 1
    WScript.Sleep 100
Wend
objPlayer.close'''
                
                # Write VBS to temp file
                vbs_path = os.path.join(self.wsl_temp_dir, "play_mp3.vbs")
                with open(vbs_path, 'w') as f:
                    f.write(vbs_content)
                
                # Execute VBScript invisibly and wait for completion
                vbs_cmd = f'wscript.exe //B "{self.windows_temp_dir}\\play_mp3.vbs"'
                
                process = await asyncio.create_subprocess_shell(
                    vbs_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Wait for completion like the WAV method does
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info("MP3 played successfully")
                    return True
                else:
                    logger.error(f"MP3 playback failed: {stderr.decode()}")
                    return False
            
            # For WAV files, use PowerShell with SoundPlayer (already invisible)
            elif file_ext == 'wav':
                logger.info(f"Playing WAV invisibly: {windows_path}")
                
                wav_cmd = f'''powershell.exe -WindowStyle Hidden -Command "\\$player = New-Object System.Media.SoundPlayer('{windows_path}'); \\$player.PlaySync(); Write-Host 'Done'"'''
                
                process = await asyncio.create_subprocess_shell(
                    wav_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info("WAV played successfully")
                    return True
                else:
                    logger.error(f"WAV playback failed: {stderr.decode()}")
                    return False
            
            else:
                logger.error(f"Unsupported audio format: {file_ext}")
                return False
                
        except Exception as e:
            logger.error(f"Windows audio routing failed: {e}")
            return False
    
    async def play_through_windows_with_process(self, audio_path: str) -> Optional[asyncio.subprocess.Process]:
        """
        Play audio through Windows audio system and return the process.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            The audio process if playback started successfully, None otherwise
        """
        try:
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return None
            
            # Copy to Windows accessible location
            filename = os.path.basename(audio_path)
            windows_audio_path = os.path.join(self.wsl_temp_dir, filename)
            
            # Copy file to Windows temp
            copy_cmd = f"cp '{audio_path}' '{windows_audio_path}'"
            copy_process = await asyncio.create_subprocess_shell(
                copy_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await copy_process.communicate()
            
            if copy_process.returncode != 0:
                logger.error(f"Failed to copy audio to Windows: {audio_path}")
                return None
            
            # Convert to Windows path
            windows_path = f"{self.windows_temp_dir}\\{filename}"
            
            # Check file extension
            file_ext = filename.lower().split('.')[-1]
            
            # For MP3 files, use Windows Media ActiveX invisibly
            if file_ext == 'mp3':
                logger.info(f"Playing MP3 invisibly: {windows_path}")
                
                # Create a VBScript for truly invisible MP3 playback
                vbs_content = f'''Set objPlayer = CreateObject("WMPlayer.OCX")
objPlayer.URL = "{windows_path}"
objPlayer.settings.volume = 100
objPlayer.controls.play
While objPlayer.playState <> 1
    WScript.Sleep 100
Wend
objPlayer.close'''
                
                # Write VBS to temp file
                vbs_path = os.path.join(self.wsl_temp_dir, "play_mp3.vbs")
                with open(vbs_path, 'w') as f:
                    f.write(vbs_content)
                
                # Execute VBScript invisibly
                vbs_cmd = f'wscript.exe //B "{self.windows_temp_dir}\\play_mp3.vbs"'
                
                process = await asyncio.create_subprocess_shell(
                    vbs_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                return process
            
            # For WAV files, use PowerShell with SoundPlayer
            elif file_ext == 'wav':
                logger.info(f"Playing WAV invisibly: {windows_path}")
                
                wav_cmd = f'''powershell.exe -WindowStyle Hidden -Command "\\$player = New-Object System.Media.SoundPlayer('{windows_path}'); \\$player.PlaySync(); Write-Host 'Done'"'''
                
                process = await asyncio.create_subprocess_shell(
                    wav_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                return process
            
            else:
                logger.error(f"Unsupported audio format: {file_ext}")
                return None
                
        except Exception as e:
            logger.error(f"Windows audio routing with process failed: {e}")
            return None
    
    async def cleanup_old_files(self, max_age_minutes: int = 30):
        """Clean up old audio files from Windows temp directory."""
        try:
            import time
            current_time = time.time()
            
            for file in os.listdir(self.wsl_temp_dir):
                file_path = os.path.join(self.wsl_temp_dir, file)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > (max_age_minutes * 60):
                        os.remove(file_path)
                        logger.debug(f"Cleaned up old audio file: {file}")
        except Exception as e:
            logger.error(f"Failed to clean up old audio files: {e}")

# Global instance
windows_audio_router = WindowsAudioRouter()