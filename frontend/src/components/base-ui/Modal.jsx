import React, { useEffect, useRef } from 'react';
import { Dialog } from '@base-ui-components/react/dialog';
import { Button } from './Button';

export const Modal = ({
  open,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  showCloseButton = true,
  className = '',
  preventBackdropClose = false,
}) => {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (open) {
      // Focus trap and ESC key handling
      const handleEsc = (e) => {
        if (e.key === 'Escape' && !preventBackdropClose) {
          onClose();
        }
      };
      document.addEventListener('keydown', handleEsc);
      return () => document.removeEventListener('keydown', handleEsc);
    }
  }, [open, onClose, preventBackdropClose]);

  if (!open) return null;

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !preventBackdropClose) {
      onClose();
    }
  };

  return (
    <Dialog.Root open={open}>
      <Dialog.Portal>
        <Dialog.Backdrop 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 animate-in fade-in"
          onClick={handleBackdropClick}
        />
        <Dialog.Popup
          ref={dialogRef}
          className={`fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 
            bg-gray-900 border border-purple-600/30 rounded-lg shadow-2xl 
            ${width} w-full max-h-[90vh] flex flex-col z-50 
            animate-in fade-in zoom-in-95 ${className}`}
        >
          {title && (
            <Dialog.Title className="flex items-center justify-between p-6 border-b border-purple-600/20 text-2xl font-bold text-purple-200">
              {title}
              {showCloseButton && (
                <Button
                  onClick={onClose}
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  aria-label="Close modal"
                >
                  ✕
                </Button>
              )}
            </Dialog.Title>
          )}
          <div className="flex-1 overflow-y-auto p-6">
            {children}
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
};