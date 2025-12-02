import { useEffect } from 'react';

/**
 * Custom hook to manage global keyboard shortcuts
 * Handles image generation shortcuts and recording toggle
 *
 * @param {Object} refs - References to components that keyboard shortcuts interact with
 * @param {React.RefObject} refs.controlPanelRef - Reference to ControlPanel component
 * @param {React.RefObject} refs.transcriptionRef - Reference to ContinuousTranscription component
 */
export function useKeyboardShortcuts({ controlPanelRef, transcriptionRef }) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Check for Ctrl+G (Generate Image)
      if (event.ctrlKey && (event.key === 'g' || event.key === 'G')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering image generation via keyboard shortcut');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGeneration) {
          controlPanelRef.current.triggerImageGeneration();
        } else {
          console.log('❌ Cannot trigger image generation - control panel ref not available');
        }
      }

      // Check for Alt+S (Generate Scene Image)
      if (event.altKey && (event.key === 's' || event.key === 'S')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering scene image generation via Alt+S');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('scene');
        }
      }

      // Check for Alt+C (Generate Character Image)
      if (event.altKey && (event.key === 'c' || event.key === 'C')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering character image generation via Alt+C');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('character');
        }
      }

      // Check for Alt+P (Generate Portrait Image)
      if (event.altKey && (event.key === 'p' || event.key === 'P')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering portrait image generation via Alt+P');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('portrait');
        }
      }

      // Check for Alt+I (Generate Item Image)
      if (event.altKey && (event.key === 'i' || event.key === 'I')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering item image generation via Alt+I');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('item');
        }
      }

      // Check for Alt+B (Generate Beast Image)
      if (event.altKey && (event.key === 'b' || event.key === 'B')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering beast image generation via Alt+B');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('beast');
        }
      }

      // Check for Alt+M (Generate Moment Image)
      if (event.altKey && (event.key === 'm' || event.key === 'M')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering moment image generation via Alt+M');

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
