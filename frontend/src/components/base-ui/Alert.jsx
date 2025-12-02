import React from 'react';

export const Alert = ({
  children,
  variant = 'info',
  className = '',
  onClose,
  title,
}) => {
  const variants = {
    info: 'bg-blue-900/20 border-blue-500/30 text-blue-200',
    success: 'bg-green-900/20 border-green-500/30 text-green-200',
    warning: 'bg-yellow-900/20 border-yellow-500/30 text-yellow-200',
    error: 'bg-red-900/20 border-red-500/30 text-red-200',
  };

  const icons = {
    info: '💡',
    success: '✅',
    warning: '⚠️',
    error: '❌',
  };

  return (
    <div
      className={`
        border rounded-lg p-4 flex items-start gap-3
        ${variants[variant]}
        ${className}
      `}
      role="alert"
    >
      <span className="text-xl" aria-hidden="true">{icons[variant]}</span>
      <div className="flex-1">
        {title && (
          <h4 className="font-semibold mb-1">{title}</h4>
        )}
        <div>{children}</div>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="ml-2 opacity-70 hover:opacity-100 transition-opacity"
          aria-label="Close alert"
        >
          ✕
        </button>
      )}
    </div>
  );
};