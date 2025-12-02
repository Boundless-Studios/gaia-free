/**
 * Base UI Input Component
 * Simple wrapper around Base UI's Input with our Gaia dark gaming theme
 */

import React from 'react';
import { Input as BaseInput } from '@base-ui-components/react/input';

const Input = React.forwardRef((props, ref) => {
  const {
    className = '',
    error = false,
    disabled = false,
    ...other
  } = props;

  const inputClasses = `
    w-full px-3 py-2 
    bg-gray-800 border rounded-lg
    text-white placeholder-gray-500
    transition-all duration-200
    ${error 
      ? 'border-red-500 focus:border-red-400 focus:ring-red-400/20' 
      : 'border-purple-600/30 focus:border-purple-500 focus:ring-purple-500/20'
    }
    focus:outline-none focus:ring-2
    disabled:opacity-50 disabled:cursor-not-allowed
    ${className}
  `;

  return (
    <BaseInput
      ref={ref}
      className={inputClasses}
      disabled={disabled}
      aria-invalid={error ? 'true' : 'false'}
      {...other}
    />
  );
});

Input.displayName = 'Input';

export { Input };
export default Input;