import React, { useState } from 'react';
import { Modal } from './base-ui/Modal';
import { Button } from './base-ui/Button';
import { Textarea } from './base-ui/Textarea';
import './ContextInput.css';

function ContextInput({ onAddContext, isOpen, onClose }) {
  const [contextText, setContextText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (contextText.trim()) {
      onAddContext(contextText);
      setContextText('');
      onClose();
    }
  };

  return (
    <Modal 
      open={isOpen} 
      onClose={onClose}
      title="Add Context to Campaign"
      width="max-w-2xl"
    >
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <p className="text-sm text-gaia-muted">
            Add background information, character details, or story context that will be included 
            in the conversation history without triggering a DM response.
          </p>
          
          <Textarea
            value={contextText}
            onChange={(e) => setContextText(e.target.value)}
            placeholder="Enter context information here..."
            className="w-full"
            rows={8}
            autoFocus
          />
        </div>
        
        <div className="flex gap-3 justify-end mt-6">
          <Button type="button" onClick={onClose} variant="secondary">
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!contextText.trim()}>
            Add Context
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default ContextInput;