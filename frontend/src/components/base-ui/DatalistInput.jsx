import React, { useState, useRef, useEffect } from 'react';

/**
 * DatalistInput - Shows dropdown with options on click, allows free text entry.
 * No validation - accepts any value.
 */
export const DatalistInput = ({
  value,
  onChange,
  options = [],
  placeholder = 'Type or select...',
  className = '',
  disabled = false,
  label,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value || '');
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Update input when value prop changes
  useEffect(() => {
    setInputValue(value || '');
  }, [value]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e) => {
    const newValue = e.target.value;
    setInputValue(newValue);
    if (onChange) onChange(newValue);
    // Don't auto-open dropdown while typing - user can click arrow to see options
  };

  const handleOptionSelect = (optionValue) => {
    setInputValue(optionValue);
    if (onChange) onChange(optionValue);
    setIsOpen(false);
    // Return focus to input
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  // Always show ALL options - no filtering
  // This allows users to see all defaults even if they have a custom value typed in
  const filteredOptions = options;

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {label && (
        <label className="block text-sm font-medium text-purple-200 mb-1">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          className={`
            w-full px-4 py-2 pr-10
            bg-gray-800 border border-purple-600/30 rounded-lg
            text-gray-200 placeholder-gray-500
            focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/40
            hover:bg-gray-700 hover:border-purple-500/40
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all
          `}
          value={inputValue}
          onChange={handleInputChange}
          placeholder={placeholder}
          disabled={disabled}
        />
        <button
          type="button"
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-200 transition-colors"
          onClick={toggleDropdown}
          disabled={disabled}
          tabIndex={-1}
        >
          <svg
            className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-gray-800 border border-purple-600/30 rounded-lg shadow-xl">
          {options.length === 0 ? (
            <div className="px-4 py-2 text-gray-500 text-sm">
              No options available
            </div>
          ) : (
            options.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`
                  w-full px-4 py-2 text-left cursor-pointer transition-colors
                  hover:bg-purple-600/20 hover:text-purple-200
                  ${inputValue === option.value ? 'bg-purple-600/30 text-purple-200' : 'text-gray-300'}
                `}
                onClick={() => handleOptionSelect(option.value)}
              >
                {option.label || option.value}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default DatalistInput;
