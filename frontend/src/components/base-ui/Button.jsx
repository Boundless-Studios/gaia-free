/**
 * Base UI Button Component
 * A fully accessible, touch-friendly button using Base UI's unstyled Button primitive
 * with our Gaia dark gaming theme applied
 */

import React from 'react';
import { cn, getButtonClasses } from './baseUIConfig';

const Button = React.forwardRef((props, ref) => {
  const {
    children,
    variant = 'primary',
    size = 'medium', 
    disabled = false,
    loading = false,
    loadingCount = 0,
    icon = null,
    iconPosition = 'left',
    fullWidth = false,
    className,
    type = 'button',
    onClick,
    ...other
  } = props;

  // Generate the appropriate classes based on props
  const buttonClasses = cn(
    getButtonClasses(variant, size, disabled || loading),
    fullWidth && 'w-full',
    loading && 'cursor-wait',
    'inline-flex items-center justify-center gap-2',
    className
  );

  // Loading spinner component
  const LoadingSpinner = () => (
    <span className="relative flex items-center justify-center">
      <svg
        className="animate-spin h-4 w-4 text-current"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
      {Number.isFinite(loadingCount) && loadingCount > 0 && (
        <span
          className="absolute -top-1.5 -right-1.5 min-w-[1.1rem] h-[1.1rem] px-[3px] rounded-full bg-gaia-accent text-white text-[0.6rem] font-semibold leading-[1.1rem] text-center shadow-lg shadow-purple-900/50"
          aria-live="polite"
        >
          {loadingCount > 9 ? '9+' : loadingCount}
        </span>
      )}
    </span>
  );

  return (
    <button
      ref={ref}
      type={type}
      className={buttonClasses}
      disabled={disabled || loading}
      onClick={onClick}
      aria-busy={loading}
      aria-disabled={disabled || loading}
      {...other}
    >
      {loading && <LoadingSpinner />}
      {!loading && icon && iconPosition === 'left' && icon}
      {children}
      {!loading && icon && iconPosition === 'right' && icon}
    </button>
  );
});

Button.displayName = 'Button';

// Export variants for easy reference
export const ButtonVariants = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  DANGER: 'danger',
  GHOST: 'ghost'
};

export const ButtonSizes = {
  SMALL: 'small',
  MEDIUM: 'medium',
  LARGE: 'large'
};

export { Button };
export default Button;
