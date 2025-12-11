import React, { useEffect, useRef, forwardRef, useImperativeHandle, useState, useCallback } from 'react';
import ImageGenerateButton from './ImageGenerateButton';
import TTSProviderSelector from './TTSProviderSelector';
import apiService from '../services/apiService';
import { useSFX } from '../context/sfxContext';
import { Card } from './base-ui/Card';
import { Alert } from './base-ui/Alert';
import './ControlPanel.css';

const ControlPanel = forwardRef(({ selectedVoice, onVoiceSelect, gameDashboardRef, onImageGenerated, campaignId, selectedProvider, onProviderChange }, ref) => {
  const sfx = useSFX();
  const imageButtonRef = useRef(null);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);
  const fetchingRef = useRef(false);
  const retryTimeoutRef = useRef(null);
  const playbackStateRef = useRef({ isProcessing: false });
  
  // Helper functions - moved to top to avoid initialization errors
  const formatVoiceDescription = (voice) => {
    const parts = [];
    if (voice.gender) parts.push(voice.gender);
    if (voice.style) parts.push(voice.style);
    return parts.length > 0 ? parts.join(' • ') : voice.description || 'Character Voice';
  };

  const sortVoicesByCharacterRole = (voices) => {
    const characterRoleOrder = [
      'DM/Narrator',
      'Noble NPC',
      'Innkeeper',
      'Worker',
      'Spirited',
      'Evil'
    ];
    
    return voices.sort((a, b) => {
      const aRole = a.character_role || '';
      const bRole = b.character_role || '';
      const aIndex = characterRoleOrder.indexOf(aRole);
      const bIndex = characterRoleOrder.indexOf(bRole);
      
      // If both roles are in the order list, sort by their position
      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex;
      }
      // If only one is in the order list, prioritize it
      if (aIndex !== -1) return -1;
      if (bIndex !== -1) return 1;
      // If neither is in the order list, sort alphabetically
      return aRole.localeCompare(bRole);
    });
  };
  
  // Expose control methods to GameDashboard
    const fetchAvailableVoices = async (retryCount = 0) => {
    // Prevent concurrent fetches
    if (fetchingRef.current && retryCount === 0) {
      console.log('Already fetching voices, skipping...');
      return;
    }
    
    fetchingRef.current = true;
    
    try {
      setIsLoadingVoices(true);
      console.log(`Fetching voices for provider: ${selectedProvider} (attempt ${retryCount + 1})`);
      
      const data = await apiService.getTTSVoices();

      if (data) {
        if (data.voices && data.voices.length > 0) {
          // Only get voices for the selected provider
          const selectedProviderVoices = data.voices.filter(voice => voice.provider === selectedProvider);
          console.log(`Found ${selectedProviderVoices.length} voices for provider ${selectedProvider}:`, selectedProviderVoices);
          
          if (selectedProviderVoices.length > 0) {
            setAvailableVoices(selectedProviderVoices);
          } else {
            // No voices available for the selected provider
            console.log(`No voices available for provider ${selectedProvider}`);
            setAvailableVoices([]);
          }
        } else {
          setAvailableVoices([]);
        }
        fetchingRef.current = false;
        setIsLoadingVoices(false);
      } else {
        console.error('Voice API response not ok');
        setAvailableVoices([]);
        fetchingRef.current = false;
        setIsLoadingVoices(false);
      }
    } catch (error) {
      console.error('Failed to fetch voices:', error);
      setAvailableVoices([]);
      
      // Retry logic for TTS server startup timing issues - but only if we have a provider selected
      if (retryCount < 3 && selectedProvider) {
        console.log(`Retrying voice fetch in 2 seconds... (attempt ${retryCount + 1})`);
        retryTimeoutRef.current = setTimeout(() => {
          fetchingRef.current = false;
          fetchAvailableVoices(retryCount + 1);
        }, 2000);
        return; // Don't set loading to false yet
      } else {
        // Max retries reached or no provider selected
        fetchingRef.current = false;
        setIsLoadingVoices(false);
      }
    }
  };

  // Fetch available voices when provider changes
  useEffect(() => {
    // Clear any pending retries when provider changes
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    fetchAvailableVoices();
    
    // Cleanup on unmount or provider change
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      fetchingRef.current = false;
    };
  }, [selectedProvider]); // Remove fetchAvailableVoices from dependencies

  // Ensure default voice is selected when available voices change
  useEffect(() => {
    if (availableVoices.length > 0) {
      const sortedVoices = sortVoicesByCharacterRole(availableVoices);
      if (sortedVoices.length > 0) {
        const defaultVoice = sortedVoices[0];
        onVoiceSelect(defaultVoice.id);
      }
    } else {
      // Clear selected voice when no voices are available
      console.log(`No voices available for provider ${selectedProvider}, clearing selected voice`);
      onVoiceSelect('');
    }
  }, [availableVoices, selectedProvider, onVoiceSelect]);

  const handleRefreshTTS = () => {
    console.log('Manual TTS refresh triggered');
    fetchAvailableVoices();
  };

  // Generate character-voice mappings based on available voices
  const sortedVoices = sortVoicesByCharacterRole(availableVoices.slice(0, 8));
  const characterVoiceMappings = sortedVoices.map((voice, index) => ({
    number: index + 1,
    character: voice.character_role || voice.name,
    voice: voice.id,
    description: formatVoiceDescription(voice)
  }));

  const triggerSelectedTextPlayback = useCallback(async (voiceOverride = null) => {
    if (typeof window === 'undefined') {
      return;
    }
    const selection = window.getSelection();
    const selectedText = selection ? selection.toString().trim() : '';
    if (!selectedText) {
      console.log('[TTS] No highlighted text detected, skipping playback trigger');
      return;
    }
    if (!characterVoiceMappings.length && !selectedVoice && !voiceOverride) {
      console.warn('[TTS] No available voices to use for playback');
      return;
    }

    const voiceToUse = voiceOverride || selectedVoice || characterVoiceMappings[0]?.voice || 'nathaniel';
    const sessionForRequest =
      !campaignId || campaignId === 'default' ? 'default-session' : campaignId;

    playbackStateRef.current.isProcessing = true;
    try {
      await apiService.synthesizeTTS(
        {
          text: selectedText,
          voice: voiceToUse,
          speed: 1.0,
        },
        sessionForRequest,
      );
      console.log('[TTS] Triggered playback via keyboard shortcut', {
        sessionId: sessionForRequest,
        voice: voiceToUse,
        length: selectedText.length,
      });
    } catch (error) {
      console.error('Failed to trigger keyboard playback:', error);
    } finally {
      playbackStateRef.current.isProcessing = false;
    }
  }, [campaignId, characterVoiceMappings, selectedVoice]);

  // Trigger sound effect generation for selected text
  const triggerSoundEffect = useCallback(async () => {
    if (typeof window === 'undefined') {
      return;
    }
    const selection = window.getSelection();
    const selectedText = selection ? selection.toString().trim() : '';
    if (!selectedText) {
      console.log('[SFX] No highlighted text detected, skipping sound effect generation');
      return;
    }

    const sessionForRequest =
      !campaignId || campaignId === 'default' ? 'default-session' : campaignId;

    // Use the SFX context to generate sound effects
    await sfx.generateSoundEffect(selectedText, sessionForRequest);
  }, [campaignId, sfx]);

  React.useLayoutEffect(() => {
    if (gameDashboardRef && gameDashboardRef.current) {
      gameDashboardRef.current.triggerImageGeneration = () => {
        if (imageButtonRef.current) {
          imageButtonRef.current.generateFromSelection();
        }
      };
      gameDashboardRef.current.triggerAudioPlayback = () => {
        triggerSelectedTextPlayback();
      };
    }
  }, [gameDashboardRef, triggerSelectedTextPlayback]);
  
  // Expose control methods via ref for keyboard shortcuts
  useImperativeHandle(ref, () => ({
    triggerImageGeneration: () => {
      if (imageButtonRef.current) {
        imageButtonRef.current.generateFromSelection();
      }
    },
    triggerImageGenerationWithType: (imageType) => {
      if (imageButtonRef.current) {
        imageButtonRef.current.generateFromSelectionWithType(imageType);
      }
    },
    triggerAudioPlayback: () => {
      triggerSelectedTextPlayback();
    },
    triggerSoundEffect: () => {
      triggerSoundEffect();
    },
  }), [triggerSelectedTextPlayback, triggerSoundEffect]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Don't trigger if user is typing in an input field
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      // Handle number keys 1-8 (matching available voices for TTS)
      if (e.key >= '1' && e.key <= '8') {
        const numberPressed = parseInt(e.key);
        const mapping = characterVoiceMappings.find(m => m.number === numberPressed);
        if (mapping) {
          console.log(`Keyboard shortcut ${numberPressed} pressed. Selecting voice:`, mapping);
          // Select the voice
          onVoiceSelect(mapping.voice);

          // Attempt to play highlighted text immediately with the selected voice
          // Pass the voice directly to avoid race condition with state update
          triggerSelectedTextPlayback(mapping.voice);
        }
      }

      // Handle key 9 for sound effect generation
      if (e.key === '9') {
        console.log('Keyboard shortcut 9 pressed. Generating sound effect for selected text.');
        triggerSoundEffect();
      }
    };

    // Add event listener
    document.addEventListener('keydown', handleKeyPress);

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleKeyPress);
    };
  }, [onVoiceSelect, characterVoiceMappings, triggerSelectedTextPlayback, triggerSoundEffect]);

  return (
    <div className="control-panel-modal">
      <div className="voice-selection-container">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-gaia-success/20">
          <h3 className="m-0 text-gaia-accent text-lg font-semibold">Character Voices</h3>
          <TTSProviderSelector selectedProvider={selectedProvider} onProviderChange={onProviderChange} onRefresh={handleRefreshTTS} />
        </div>
        <div className="text-xs text-gaia-muted italic mb-2 text-center">
          Highlight text, then press 1-8 to narrate or 9 for sound effects
        </div>

        {isLoadingVoices ? (
          <Alert variant="info" className="text-center">
            Loading voices for {selectedProvider}...
          </Alert>
        ) : characterVoiceMappings.length === 0 ? (
          <Alert variant="error">
            No voices available for {selectedProvider}. The provider may not be configured or running. Try switching to a different provider.
          </Alert>
        ) : (
          <div className="voice-grid" style={{display: 'grid', gridTemplateColumns: 'repeat(4, 200px)', gridTemplateRows: 'repeat(2, auto)', gap: '1rem', maxWidth: 'calc(4 * 200px + 3 * 1rem)'}}>
            {characterVoiceMappings.map((mapping) => (
              <Card
                key={mapping.number}
                className={`cursor-pointer transition-all duration-200 hover:bg-gaia-success/20 hover:border-gaia-success/50 hover:translate-x-1 ${
                  selectedVoice === mapping.voice 
                    ? 'bg-gaia-success/30 border-gaia-success shadow-[0_0_8px_rgba(34,139,34,0.3)]' 
                    : ''
                }`}
                onClick={() => onVoiceSelect(mapping.voice)}
                title={mapping.description}
              >
                <div className="flex items-center p-2">
                  <span className={`flex items-center justify-center w-7 h-7 rounded-full font-bold text-sm mr-3 flex-shrink-0 ${
                    selectedVoice === mapping.voice
                      ? 'bg-gaia-success border-2 border-gaia-success text-white'
                      : 'bg-gaia-success/20 border-2 border-gaia-success/50 text-gaia-accent'
                  }`}>
                    {mapping.number}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-gaia-accent text-sm mb-0.5">
                      {mapping.character}
                    </div>
                    <div className="text-xs text-gaia-muted whitespace-nowrap overflow-hidden text-ellipsis">
                      {mapping.voice}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="controls-container">
        <div>
          <h3 className="m-0 mb-3 text-gaia-accent text-lg font-semibold text-center">Image Generation</h3>
          <div className="text-xs text-gaia-muted italic mb-2 text-center">
            Press Alt+s=scene, Alt+c=character, Alt+p=portrait, Alt+i=item, Alt+b=beast, Alt+m=moment
          </div>
          <ImageGenerateButton ref={imageButtonRef} onImageGenerated={onImageGenerated} campaignId={campaignId} />
        </div>
      </div>
    </div>
  );
});

ControlPanel.displayName = 'ControlPanel';

export default ControlPanel;
