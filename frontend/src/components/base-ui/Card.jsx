import React from 'react';

export const Card = ({
  children,
  className = '',
  onClick,
  hover = false,
  selected = false,
  padding = 'p-4',
}) => {
  const baseClasses = `
    bg-gray-800 border border-purple-600/20 rounded-lg
    ${padding}
    ${hover ? 'hover:bg-gray-700 hover:border-purple-500/40 transition-all cursor-pointer' : ''}
    ${selected ? 'border-purple-500 bg-gray-700' : ''}
  `;

  return (
    <div
      className={`${baseClasses} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      } : undefined}
    >
      {children}
    </div>
  );
};

export const CardHeader = ({ children, className = '' }) => (
  <div className={`mb-4 pb-2 border-b border-purple-600/20 ${className}`}>
    {children}
  </div>
);

export const CardTitle = ({ children, className = '' }) => (
  <h3 className={`text-lg font-semibold text-purple-200 ${className}`}>
    {children}
  </h3>
);

export const CardContent = ({ children, className = '' }) => (
  <div className={`text-gray-300 ${className}`}>
    {children}
  </div>
);

export const CardFooter = ({ children, className = '' }) => (
  <div className={`mt-4 pt-2 border-t border-purple-600/20 ${className}`}>
    {children}
  </div>
);