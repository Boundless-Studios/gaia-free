import re
import logging
from typing import List, Optional
import os
import asyncio
import base64
import aiohttp

logger = logging.getLogger(__name__)

# Import centralized audio configuration
try:
    from gaia.infra.audio.voice_and_tts_config import get_all_config
    _config_available = True
except ImportError:
    logger.warning("Could not import centralized audio config, using fallback paths")
    _config_available = False

def _get_windows_temp_path():
    """Get Windows temp path from centralized config or fallback."""
    if _config_available:
        try:
            config = get_all_config()
            windows_temp_path = config['paths'].get('windows_temp', "C:\\Windows\\Temp\\gaia_narration.wav")
            return os.path.dirname(windows_temp_path)
        except Exception as e:
            logger.warning(f"Failed to get Windows temp path from config: {e}")
    
    # Fallback
    return "C:\\Windows\\Temp"

def chunk_text_by_sentences(
    text: str,
    target_chunk_size: int = 250,
    max_chunk_size: int = 300,
    sentences_per_chunk: int = 3
) -> List[str]:
    """
    Split text into chunks based on sentences and paragraphs.
    Groups sentences together, up to target_chunk_size/max_chunk_size and sentences_per_chunk.
    Respects paragraph boundaries for natural pauses.
    """
    if not text or not text.strip():
        return []
    
    # First split by paragraphs (double newlines)
    paragraphs = re.split(r'\n\s*\n', text.strip())
    
    all_chunks = []
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        # Split by sentence endings
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, paragraph.strip())
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            continue
        
        # Process sentences within this paragraph
        current_chunk = []
        current_length = 0
        sentence_count = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # Check if adding this sentence would exceed limits
            would_exceed_size = current_length + sentence_length > max_chunk_size
            has_enough_sentences = sentence_count >= sentences_per_chunk
            is_good_chunk_size = current_length >= target_chunk_size
            
            # Start a new chunk if needed
            if current_chunk and (would_exceed_size or (has_enough_sentences and is_good_chunk_size)):
                all_chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0
                sentence_count = 0
            
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space
            sentence_count += 1
        
        # Add the last chunk from this paragraph
        if current_chunk:
            all_chunks.append(' '.join(current_chunk))
            
        # Add a paragraph break marker (empty string) if not the last paragraph
        if paragraph != paragraphs[-1]:
            all_chunks.append("__PARAGRAPH_BREAK__")
    
    logger.info(f"Split text into {len(all_chunks)} chunks across {len(paragraphs)} paragraphs")
    for i, chunk in enumerate(all_chunks):
        if chunk == "__PARAGRAPH_BREAK__":
            logger.debug(f"Chunk {i+1}: [PARAGRAPH BREAK]")
        else:
            logger.debug(f"Chunk {i+1}: {len(chunk)} chars, {chunk[:50]}...")
    
    return all_chunks 

async def play_audio_unix_with_process(audio_path: str) -> Optional[asyncio.subprocess.Process]:
    """Play audio file on Unix/Linux systems and return the process."""
    if not os.path.exists(audio_path):
        logger.warning(f"Audio file not found: {audio_path}")
        return None
    audio_players = [
        ["paplay"],
        ["aplay"],
        ["ffplay", "-nodisp", "-autoexit"],
        ["mpv", "--no-video"],
        ["mplayer", "-quiet"],
        ["play"],
        ["afplay"],
        ["cvlc", "--intf", "dummy", "--play-and-exit"],
    ]
    for player_cmd in audio_players:
        try:
            check_result = await asyncio.create_subprocess_shell(
                f"which {player_cmd[0]}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await check_result.wait()
            if check_result.returncode == 0:
                cmd = player_cmd + [audio_path]
                logger.debug(f"Playing audio with: {' '.join(cmd)}")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                return process
        except Exception as e:
            logger.debug(f"Failed to use {player_cmd[0]}: {e}")
            continue
    logger.warning("No suitable audio player found on this Unix system")
    return None

async def play_audio_unix(audio_path: str) -> None:
    """Play audio file on Unix/Linux systems."""
    if not os.path.exists(audio_path):
        logger.warning(f"Audio file not found: {audio_path}")
        return
    audio_players = [
        ["paplay"],
        ["aplay"],
        ["ffplay", "-nodisp", "-autoexit"],
        ["mpv", "--no-video"],
        ["mplayer", "-quiet"],
        ["play"],
        ["afplay"],
        ["cvlc", "--intf", "dummy", "--play-and-exit"],
    ]
    for player_cmd in audio_players:
        try:
            check_result = await asyncio.create_subprocess_shell(
                f"which {player_cmd[0]}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await check_result.wait()
            if check_result.returncode == 0:
                cmd = player_cmd + [audio_path]
                logger.debug(f"Playing audio with: {' '.join(cmd)}")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await process.communicate()
                if process.returncode == 0:
                    logger.info(f"Audio played successfully with {player_cmd[0]}")
                    return
                else:
                    logger.debug(f"{player_cmd[0]} failed: {stderr.decode()}")
        except Exception as e:
            logger.debug(f"Failed to use {player_cmd[0]}: {e}")
            continue
    logger.warning("No suitable audio player found on this Unix system")
    logger.info("Try installing: pulseaudio-utils, alsa-utils, ffmpeg, mpv, or vlc")

async def play_audio_windows(audio_path: str) -> None:
    """Play audio file through Windows audio system."""
    try:
        is_wsl = False
        is_windows = False
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    is_wsl = True
        except:
            pass
        import platform
        if platform.system() == "Windows":
            is_windows = True
        if not (is_wsl or is_windows):
            logger.info("Not in Windows/WSL environment, skipping Windows audio playback")
            return
        if not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            return
        wsl_path = os.path.abspath(audio_path)
        wslpath_result = await asyncio.create_subprocess_shell(
            f"wslpath -w '{wsl_path}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await wslpath_result.communicate()
        if wslpath_result.returncode == 0:
            windows_path = stdout.decode().strip()
            logger.info(f"Converted path: {wsl_path} -> {windows_path}")
        else:
            windows_temp = _get_windows_temp_path()
            filename = os.path.basename(wsl_path)
            windows_path = f"{windows_temp}\\{filename}"
            # Convert Windows path to WSL mount path
            wsl_temp_path = windows_temp.replace("C:\\", "/mnt/c/").replace("\\", "/")
            copy_command = f"cp '{wsl_path}' '{wsl_temp_path}/{filename}'"
            copy_process = await asyncio.create_subprocess_shell(
                copy_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await copy_process.communicate()
            if copy_process.returncode != 0:
                logger.warning(f"Cannot copy file to Windows temp: {wsl_path}")
                return
        play_command = f"powershell.exe -Command \"try {{ $sound = New-Object System.Media.SoundPlayer('{windows_path}'); $sound.PlaySync(); Write-Host 'Audio played' }} catch {{ Write-Host 'Error: ' $_.Exception.Message }}\""
        process = await asyncio.create_subprocess_shell(
            play_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            logger.info("Audio playback completed successfully")
        else:
            logger.warning(f"Audio playback may have failed: {stderr.decode()}")
    except Exception as e:
        logger.error(f"Windows audio playback failed: {e}")

async def play_audio_auto(audio_path: str) -> None:
    """Automatically detect environment and play audio accordingly."""
    try:
        # Check if we are in Docker first
        if os.path.exists("/.dockerenv"):
            logger.info("Auto-detected Docker environment, using Unix audio")
            await play_audio_unix(audio_path)
            return
        
        import platform
        is_wsl = False
        is_windows = platform.system() == "Windows"
        if not is_windows:
            try:
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        is_wsl = True
            except:
                pass
        if is_windows or is_wsl:
            logger.info("Auto-detected Windows/WSL environment, using screenshare method")
            await play_audio_screenshare(audio_path)
        else:
            logger.info("Auto-detected Unix environment")
            await play_audio_unix(audio_path)
    except Exception as e:
        logger.error(f"Auto audio playback failed: {e}")
async def play_audio_screenshare(audio_path: str) -> None:
    """Play audio through Windows Media Player for screen sharing compatibility."""
    from gaia.utils.windows_audio_utils import windows_audio_router
    try:
        success = await windows_audio_router.play_through_windows(audio_path)
        if not success:
            logger.warning("Falling back to standard Windows audio")
            await play_audio_windows(audio_path)
    except Exception as e:
        logger.error(f"Screen share audio playback failed: {e}")
        await play_audio_windows(audio_path) 

async def play_audio_windows_with_process(audio_path: str) -> Optional[asyncio.subprocess.Process]:
    """Play audio file through Windows audio system and return the process."""
    try:
        is_wsl = False
        is_windows = False
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    is_wsl = True
        except:
            pass
        import platform
        if platform.system() == "Windows":
            is_windows = True
        if not (is_wsl or is_windows):
            logger.info("Not in Windows/WSL environment, skipping Windows audio playback")
            return None
        if not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            return None
        wsl_path = os.path.abspath(audio_path)
        wslpath_result = await asyncio.create_subprocess_shell(
            f"wslpath -w '{wsl_path}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await wslpath_result.communicate()
        if wslpath_result.returncode == 0:
            windows_path = stdout.decode().strip()
            logger.info(f"Converted path: {wsl_path} -> {windows_path}")
        else:
            windows_temp = _get_windows_temp_path()
            filename = os.path.basename(wsl_path)
            windows_path = f"{windows_temp}\\{filename}"
            # Convert Windows path to WSL mount path
            wsl_temp_path = windows_temp.replace("C:\\", "/mnt/c/").replace("\\", "/")
            copy_command = f"cp '{wsl_path}' '{wsl_temp_path}/{filename}'"
            copy_process = await asyncio.create_subprocess_shell(
                copy_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await copy_process.communicate()
            if copy_process.returncode != 0:
                logger.warning(f"Cannot copy file to Windows temp: {wsl_path}")
                return None
        play_command = f"powershell.exe -Command \"try {{ $sound = New-Object System.Media.SoundPlayer('{windows_path}'); $sound.PlaySync(); Write-Host 'Audio played' }} catch {{ Write-Host 'Error: ' $_.Exception.Message }}\""
        process = await asyncio.create_subprocess_shell(
            play_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        return process
    except Exception as e:
        logger.error(f"Windows audio playback failed: {e}")
        return None

async def play_audio_screenshare_with_process(audio_path: str) -> Optional[asyncio.subprocess.Process]:
    """Play audio through Windows Media Player for screen sharing compatibility and return the process."""
    from gaia.utils.windows_audio_utils import windows_audio_router
    try:
        # Use the dedicated windows_audio_utils for proper file copying and format handling
        return await windows_audio_router.play_through_windows_with_process(audio_path)
    except Exception as e:
        logger.error(f"Screen share audio playback failed: {e}")
        # Fall back to generic Windows method
        return await play_audio_windows_with_process(audio_path)

async def play_audio_auto_with_process(audio_path: str) -> Optional[asyncio.subprocess.Process]:
    """Automatically detect environment and play audio accordingly, returning the process."""
    try:
        import platform
        is_wsl = False
        is_windows = platform.system() == "Windows"
        if not is_windows:
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        is_wsl = True
            except:
                pass
        if is_windows or is_wsl:
            logger.info("Auto-detected Windows/WSL environment, using screenshare method")
            return await play_audio_screenshare_with_process(audio_path)
        else:
            logger.info("Auto-detected Unix environment")
            return await play_audio_unix_with_process(audio_path)
    except Exception as e:
        logger.error(f"Auto audio playback failed: {e}")
        return None