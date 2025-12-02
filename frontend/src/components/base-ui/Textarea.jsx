import React, { forwardRef } from 'react';

export const Textarea = forwardRef(({
  label,
  error,
  helperText,
  required = false,
  className = '',
  rows = 4,
  resize = 'vertical',
  ...props
}, ref) => {
  const resizeClass = {
    'none': 'resize-none',
    'vertical': 'resize-y',
    'horizontal': 'resize-x',
    'both': 'resize'
  }[resize] || 'resize-y';

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-purple-200">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}
      
      <textarea
        ref={ref}
        rows={rows}
        className={`
          w-full px-3 py-2 
          bg-gray-800 border rounded-lg
          text-white placeholder-gray-500
          transition-all duration-200
          ${resizeClass}
          ${error 
            ? 'border-red-500 focus:border-red-400 focus:ring-red-400/20' 
            : 'border-purple-600/30 focus:border-purple-500 focus:ring-purple-500/20'
          }
          focus:outline-none focus:ring-2
          disabled:opacity-50 disabled:cursor-not-allowed
          ${className}
        `}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={error ? 'error-message' : helperText ? 'helper-text' : undefined}
        {...props}
      />
      
      {error && (
        <p id="error-message" className="text-sm text-red-400 mt-1">
          {error}
        </p>
      )}
      
      {helperText && !error && (
        <p id="helper-text" className="text-sm text-gray-400 mt-1">
          {helperText}
        </p>
      )}
    </div>
  );
});

Textarea.displayName = 'Textarea';