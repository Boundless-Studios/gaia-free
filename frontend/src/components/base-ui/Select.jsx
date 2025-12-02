import { Select as BaseSelect } from '@base-ui-components/react/select';
import { componentZIndex } from '../../lib/zIndexLayers';

export const Select = ({
  value,
  onChange,
  options,
  placeholder = 'Select an option',
  className = '',
  disabled = false,
  label,
  isInModal = false,
  isInPopup = false,
  forceNative = false,
}) => {
  const selectedOption = Array.isArray(options)
    ? options.find((opt) => opt?.value === value)
    : undefined;

  // Determine appropriate z-index based on context
  const dropdownZIndex = isInPopup
    ? componentZIndex.selectDropdownInPopup
    : isInModal
    ? componentZIndex.selectDropdownInModal
    : componentZIndex.selectDropdownDefault;

  // Normalize change payload across event/value shapes
  const handleValueChange = (next) => {
    let normalized;
    if (typeof next === 'string') {
      normalized = next;
    } else if (next && typeof next === 'object') {
      normalized = next.value ?? next.target?.value ?? '';
    } else {
      normalized = String(next ?? '');
    }
    if (onChange) onChange(normalized);
  };

  // Native fallback (reliable inside complex modals/scroll containers)
  if (forceNative) {
    return (
      <div className={`relative ${className}`}>
        {label && (
          <label className="block text-sm font-medium text-purple-200 mb-1">
            {label}
          </label>
        )}
        <select
          className={`
            w-full px-4 py-2 text-left
            bg-gray-800 border border-purple-600/30 rounded-lg
            text-gray-200 hover:bg-gray-700 hover:border-purple-500/40
            focus:outline-none focus:ring-2 focus:ring-purple-500/50
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all cursor-pointer
          `}
          value={value ?? ''}
          onChange={(e) => handleValueChange(e)}
          disabled={disabled}
        >
          {Array.isArray(options) && options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-purple-200 mb-1">
          {label}
        </label>
      )}
      <BaseSelect.Root value={value} onValueChange={handleValueChange} disabled={disabled}>
        <BaseSelect.Trigger
          className={`
            w-full px-4 py-2 text-left
            bg-gray-800 border border-purple-600/30 rounded-lg
            text-gray-200 hover:bg-gray-700 hover:border-purple-500/40
            focus:outline-none focus:ring-2 focus:ring-purple-500/50
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all cursor-pointer
            flex items-center justify-between
          `}
        >
          <span className="truncate mr-2">
            <BaseSelect.Value placeholder={placeholder} />
          </span>
          <BaseSelect.Icon>
            <svg
              className="w-4 h-4 transition-transform ui-expanded:rotate-180"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </BaseSelect.Icon>
        </BaseSelect.Trigger>

        <BaseSelect.Portal>
          <BaseSelect.Positioner>
            <BaseSelect.Popup
              className={`${dropdownZIndex} w-full max-h-[60vh] overflow-y-auto bg-gray-800 border border-purple-600/30 rounded-lg shadow-xl animate-in fade-in`}
            >
              {Array.isArray(options) &&
                options.map((option) => (
                  <BaseSelect.Item
                    key={option.value}
                    value={option.value}
                    className={`
                      px-4 py-2 cursor-pointer transition-colors
                      hover:bg-purple-600/20 hover:text-purple-200
                      ui-selected:bg-purple-600/30 ui-selected:text-purple-200
                      text-gray-300
                    `}
                  >
                    <BaseSelect.ItemText>{option.label}</BaseSelect.ItemText>
                  </BaseSelect.Item>
                ))}
            </BaseSelect.Popup>
          </BaseSelect.Positioner>
        </BaseSelect.Portal>
      </BaseSelect.Root>
    </div>
  );
};

export const SelectOption = ({ value, label }) => ({ value, label });
