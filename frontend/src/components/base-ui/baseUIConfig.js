/**
 * Base UI Configuration
 * This file contains the configuration for Base UI components
 * to work with our existing Tailwind CSS dark gaming theme
 */

// Theme colors from Tailwind config
export const gaiaTheme = {
  colors: {
    dark: '#0a0a0a',      // Main background
    light: '#1a1a1a',     // Cards/sections
    border: '#2a2a2a',    // Borders
    accent: '#8b5cf6',    // Primary purple
    success: '#10b981',   // Green
    error: '#ef4444',     // Red
    warning: '#f59e0b',   // Amber
    info: '#3b82f6',      // Blue
    text: {
      primary: '#e0e0e0',
      secondary: '#a0a0a0',
      muted: '#707070'
    }
  },
  
  // Component-specific configurations
  components: {
    button: {
      variants: {
        primary: 'bg-gaia-accent hover:bg-gaia-accent-dark text-white font-semibold py-2 px-4 rounded-md transition-all duration-200 hover:shadow-lg active:scale-95',
        secondary: 'bg-gaia-light hover:bg-gaia-border text-gaia-text border border-gaia-border font-semibold py-2 px-4 rounded-md transition-all duration-200',
        danger: 'bg-gaia-error hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-md transition-all duration-200',
        ghost: 'hover:bg-gaia-light text-gaia-text font-semibold py-2 px-4 rounded-md transition-all duration-200'
      },
      sizes: {
        small: 'py-1 px-2 text-sm',
        medium: 'py-2 px-4',
        large: 'py-3 px-6 text-lg'
      },
      // Touch-friendly minimum size
      touchTarget: 'min-h-[44px] min-w-[44px]'
    },
    
    input: {
      base: 'bg-gaia-light border border-gaia-border text-gaia-text rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gaia-accent focus:border-transparent transition-all duration-200',
      error: 'border-gaia-error focus:ring-gaia-error',
      disabled: 'opacity-50 cursor-not-allowed'
    },
    
    modal: {
      backdrop: 'fixed inset-0 bg-black bg-opacity-75 z-50',
      content: 'bg-gaia-light border border-gaia-border rounded-lg shadow-xl max-w-lg w-full mx-auto',
      title: 'text-xl font-bold text-gaia-text mb-4',
      body: 'text-gaia-text-secondary'
    },
    
    dropdown: {
      trigger: 'bg-gaia-light border border-gaia-border text-gaia-text rounded-md px-3 py-2 cursor-pointer hover:bg-gaia-border transition-all duration-200',
      menu: 'bg-gaia-light border border-gaia-border rounded-md shadow-lg mt-1 py-1',
      item: 'px-3 py-2 text-gaia-text hover:bg-gaia-border transition-all duration-200 cursor-pointer',
      itemSelected: 'bg-gaia-accent text-white'
    },
    
    tooltip: {
      content: 'bg-gaia-dark border border-gaia-border text-gaia-text text-sm px-2 py-1 rounded shadow-lg',
      arrow: 'text-gaia-dark'
    }
  },
  
  // Animation configurations
  animations: {
    fadeIn: 'animate-fadeIn',
    slideUp: 'animate-slideUp',
    slideDown: 'animate-slideDown',
    scaleIn: 'animate-scaleIn'
  },
  
  // Accessibility configurations
  a11y: {
    focusRing: 'focus:outline-none focus:ring-2 focus:ring-gaia-accent focus:ring-offset-2 focus:ring-offset-gaia-dark',
    srOnly: 'sr-only',
    notSrOnly: 'not-sr-only'
  }
};

// Utility function to combine class names
export const cn = (...classes) => {
  return classes.filter(Boolean).join(' ');
};

// Export helper functions for component styling
export const getButtonClasses = (variant = 'primary', size = 'medium', disabled = false) => {
  const classes = [
    gaiaTheme.components.button.variants[variant],
    gaiaTheme.components.button.sizes[size],
    gaiaTheme.components.button.touchTarget,
    gaiaTheme.a11y.focusRing,
    disabled && 'opacity-50 cursor-not-allowed'
  ];
  
  return cn(...classes);
};

export const getInputClasses = (error = false, disabled = false) => {
  const classes = [
    gaiaTheme.components.input.base,
    error && gaiaTheme.components.input.error,
    disabled && gaiaTheme.components.input.disabled
  ];
  
  return cn(...classes);
};

export default gaiaTheme;