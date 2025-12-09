import { useEffect } from 'react';

/**
 * Custom hook to manage global keyboard shortcuts
 * Handles image generation shortcuts and recording toggle
 *
 * Mac Support: Uses event.code for physical key detection to ensure Option key works properly
 *
 * @param {Object} refs - References to components that keyboard shortcuts interact with
 * @param {React.RefObject} refs.controlPanelRef - Reference to ControlPanel component
 * @param {React.RefObject} refs.transcriptionRef - Reference to ContinuousTranscription component
 */
export function useKeyboardShortcuts({ controlPanelRef, transcriptionRef }) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Detect Mac platform
      const isMac = /Mac|iPhone|iPod|iPad/.test(navigator.platform);

      // Use event.code for physical key detection (works better with Mac Option key)
      // event.code gives us the physical key (e.g., 'KeyS', 'KeyC') regardless of modifiers
      // This is more reliable than event.key which can produce different characters with Option on Mac

      // Check for Ctrl+G (Generate Image)
      if (event.ctrlKey && event.code === 'KeyG') {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering image generation via keyboard shortcut');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGeneration) {
          controlPanelRef.current.triggerImageGeneration();
        } else {
          console.log('❌ Cannot trigger image generation - control panel ref not available');
        }
      }

      // Check for Alt+S / Option+S (Generate Scene Image)
      if (event.altKey && event.code === 'KeyS') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering scene image generation via ${isMac ? 'Option' : 'Alt'}+S`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('scene');
        }
      }

      // Check for Alt+C / Option+C (Generate Character Image)
      if (event.altKey && event.code === 'KeyC') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering character image generation via ${isMac ? 'Option' : 'Alt'}+C`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('character');
        }
      }

      // Check for Alt+P / Option+P (Generate Portrait Image)
      if (event.altKey && event.code === 'KeyP') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering portrait image generation via ${isMac ? 'Option' : 'Alt'}+P`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('portrait');
        }
      }

      // Check for Alt+I / Option+I (Generate Item Image)
      if (event.altKey && event.code === 'KeyI') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering item image generation via ${isMac ? 'Option' : 'Alt'}+I`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('item');
        }
      }

      // Check for Alt+B / Option+B (Generate Beast Image)
      if (event.altKey && event.code === 'KeyB') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering beast image generation via ${isMac ? 'Option' : 'Alt'}+B`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('beast');
        }
      }

      // Check for Alt+M / Option+M (Generate Moment Image)
      if (event.altKey && event.code === 'KeyM') {
        event.preventDefault();
        event.stopPropagation();

        console.log(`🎨 Triggering moment image generation via ${isMac ? 'Option' : 'Alt'}+M`);

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('moment');
        }
      }

      // Check for Ctrl+/ (Toggle Recording)
      if (event.ctrlKey && event.key === '/') {
        event.preventDefault();

        console.log('🎤 Toggling recording via keyboard shortcut');

        if (transcriptionRef.current) {
          transcriptionRef.current.toggleRecording();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [controlPanelRef, transcriptionRef]);
}
