import { useMemo, useState, useEffect, useRef } from 'react';
import { componentZIndex, zIndexClasses } from '../../lib/zIndexLayers';

export const Combobox = ({
  value,
  onChange,
  options = [],
  placeholder = 'Type or choose...',
  className = '',
  disabled = false,
  label,
  isInModal = false,
  isInPopup = false,
}) => {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value || '');
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const rootRef = useRef(null);
  const [_placeAbove, setPlaceAbove] = useState(false);
  const [popupMaxH, setPopupMaxH] = useState('60vh');
  const [popupStyle, setPopupStyle] = useState({});

  useEffect(() => {
    setInputValue(value || '');
  }, [value]);

  useEffect(() => {
    const onDocClick = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const recomputePlacement = () => {
    const el = rootRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const vh = window.innerHeight || document.documentElement.clientHeight;
    const spaceBelow = Math.max(0, vh - rect.bottom);
    const spaceAbove = Math.max(0, rect.top);
    const shouldPlaceAbove = spaceBelow < 240 && spaceAbove > spaceBelow;
    setPlaceAbove(shouldPlaceAbove);
    const available = shouldPlaceAbove ? spaceAbove : spaceBelow;
    const usable = Math.max(0, available - 12);
    setPopupMaxH(`${Math.min(usable, Math.floor(vh * 0.6))}px`);
    // Position as fixed to avoid clipping by scroll containers
    const left = Math.max(0, rect.left);
    const width = Math.max(0, rect.width);
    if (shouldPlaceAbove) {
      setPopupStyle({ position: 'fixed', left: `${left}px`, width: `${width}px`, bottom: `${vh - rect.top + 4}px` });
    } else {
      setPopupStyle({ position: 'fixed', left: `${left}px`, width: `${width}px`, top: `${rect.bottom + 4}px` });
    }
  };

  useEffect(() => {
    if (open) {
      recomputePlacement();
    }
  }, [open]);

  useEffect(() => {
    const onScroll = () => open && recomputePlacement();
    const onResize = () => open && recomputePlacement();
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, [open]);

  // Use a higher z-index for popups to avoid being covered
  const dropdownZIndex = isInPopup
    ? zIndexClasses.critical
    : isInModal
    ? componentZIndex.selectDropdownInModal
    : componentZIndex.selectDropdownDefault;

  const filtered = useMemo(() => {
    if (!Array.isArray(options)) return [];
    const q = (inputValue || '').toLowerCase();
    if (!q) return options;
    return options.filter((opt) =>
      (opt.label || String(opt.value)).toLowerCase().includes(q)
    );
  }, [options, inputValue]);

  const commit = (next) => {
    const nextVal = (next ?? '').toString();
    setInputValue(nextVal);
    onChange?.(nextVal);
    setOpen(false);
    setHighlightIndex(-1);
  };

  const onKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightIndex >= 0 && filtered[highlightIndex]) {
        commit(filtered[highlightIndex].value);
      } else {
        commit(inputValue);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className={`relative ${className}`} ref={rootRef}>
      {label && (
        <label className="block text-sm font-medium text-purple-200 mb-1">
          {label}
        </label>
      )}
      <div
        className={`
          w-full px-4 py-2 text-left
          bg-gray-800 border border-purple-600/30 rounded-lg
          text-gray-200 hover:bg-gray-700 hover:border-purple-500/40
          focus-within:ring-2 focus-within:ring-purple-500/50
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-all flex items-center justify-between
          ${disabled ? 'opacity-50 pointer-events-none' : ''}
        `}
        onClick={() => {
          if (!disabled) {
            setOpen(true);
            // next tick to ensure layout is stable
            setTimeout(recomputePlacement, 0);
          }
        }}
      >
        <input
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => commit(inputValue)}
          placeholder={placeholder}
          className="bg-transparent outline-none w-full text-gray-200 placeholder-gray-500"
          disabled={disabled}
        />
        <svg
          className={`w-4 h-4 ml-2 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {open && (
        <div
          className={`${dropdownZIndex} overflow-y-auto bg-gray-800 border border-purple-600/30 rounded-lg shadow-xl animate-in fade-in`}
          style={{ ...popupStyle, maxHeight: popupMaxH }}
          onWheel={(e) => {
            // Prevent parent scroll while hovering menu
            e.stopPropagation();
          }}
        >
          {filtered.length === 0 ? (
            <div className="px-4 py-2 text-gray-500">No matches</div>
          ) : (
            filtered.map((opt, idx) => (
              <div
                key={opt.value}
                className={`
                  px-4 py-2 cursor-pointer transition-colors
                  hover:bg-purple-600/20 hover:text-purple-200
                  ${idx === highlightIndex ? 'bg-purple-600/30 text-purple-200' : 'text-gray-300'}
                `}
                onMouseEnter={() => setHighlightIndex(idx)}
                onMouseDown={(e) => {
                  // prevent input blur before click
                  e.preventDefault();
                }}
                onClick={() => commit(opt.value)}
              >
                {opt.label}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default Combobox;
