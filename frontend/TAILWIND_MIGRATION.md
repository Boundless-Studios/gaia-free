# Tailwind CSS Migration Guide

## CSS to Tailwind Class Mappings

### Color Palette
- `#0a0a0a` → `bg-gaia-dark`
- `#050505` → `bg-gaia-darker`
- `#1a1a1a` → `bg-gaia-light`
- `#2a2a2a` → `bg-gaia-border` (for borders) or `bg-gaia-border` (for backgrounds)
- `#e0e0e0` → `text-gaia-text`
- `#a0a0a0` → `text-gaia-text-dim`
- `#8b5cf6` → `bg-gaia-accent` / `text-gaia-accent`
- `#7c3aed` → `bg-gaia-accent-hover`
- `#10b981` → `bg-gaia-success` / `text-gaia-success`
- `#ef4444` → `bg-gaia-error` / `text-gaia-error`
- `#f59e0b` → `bg-gaia-warning` / `text-gaia-warning`
- `#3b82f6` → `bg-gaia-info` / `text-gaia-info`

### Common Components

#### Buttons
```css
/* Old CSS */
.button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.5rem;
  background: #3a3a3a;
  color: #ffffff;
  cursor: pointer;
  transition: background-color 0.2s;
}

/* Tailwind equivalent */
className="btn-secondary" // Using our custom component class
// OR
className="px-4 py-2 bg-gaia-light text-white rounded-lg hover:bg-gaia-border transition-colors duration-200 cursor-pointer"
```

#### Cards
```css
/* Old CSS */
.card {
  background: #2a2a2a;
  border-radius: 0.5rem;
  padding: 1rem;
  border: 1px solid #3a3a3a;
}

/* Tailwind equivalent */
className="card" // Using our custom component class
// OR
className="bg-gaia-light rounded-lg p-4 border border-gaia-border"
```

#### Input Fields
```css
/* Old CSS */
input {
  padding: 0.5rem;
  border: 1px solid #3a3a3a;
  border-radius: 0.25rem;
  background: #1a1a1a;
  color: #ffffff;
}

/* Tailwind equivalent */
className="input-field" // Using our custom component class
// OR
className="px-3 py-2 bg-gaia-dark border border-gaia-border rounded-md text-gaia-text focus:outline-none focus:border-gaia-accent"
```

### Layout Utilities

#### Flexbox
- `display: flex` → `flex`
- `flex-direction: column` → `flex-col`
- `flex-direction: row` → `flex-row`
- `justify-content: space-between` → `justify-between`
- `align-items: center` → `items-center`
- `gap: 1rem` → `gap-4`
- `flex: 1` → `flex-1`
- `flex: 2` → `flex-[2]`

#### Spacing
- `padding: 1rem` → `p-4`
- `margin: 1rem` → `m-4`
- `padding: 0.5rem 1rem` → `px-4 py-2`
- `margin-bottom: 1rem` → `mb-4`

#### Sizing
- `width: 100%` → `w-full`
- `height: 100vh` → `h-screen`
- `min-height: 0` → `min-h-0`
- `max-width: 800px` → `max-w-[800px]`

### Responsive Design
- `@media (max-width: 1200px)` → `xl:` prefix
- `@media (max-width: 768px)` → `md:` prefix
- `@media (max-width: 640px)` → `sm:` prefix

### Animation Classes
- Pulse animation → `animate-pulse-slow`
- Glow effect → `glow-effect`
- Hover lift → `hover-lift`

## Component Migration Status

- [ ] App.jsx
- [ ] App.css → Remove after migration
- [ ] CampaignManager.jsx / .css
- [ ] CampaignSetup.jsx / .css
- [ ] CampaignView.jsx / .css
- [ ] ChatMessage.jsx / .css
- [ ] GameDashboard.jsx / .css
- [ ] ControlPanel.jsx / .css
- [ ] CharacterManagement.jsx / .css
- [ ] DMView.jsx / .css
- [ ] ImageGallery.jsx / .css
- [ ] ImageProcessor.jsx / .css
- [ ] NarrativeView.jsx / .css
- [ ] StatusView.jsx / .css
- [ ] TurnView.jsx / .css
- [ ] CharactersView.jsx / .css

## Migration Process

1. **Phase 1**: Update component files to use Tailwind classes
2. **Phase 2**: Remove component-specific CSS files
3. **Phase 3**: Clean up App.css
4. **Phase 4**: Test all components
5. **Phase 5**: Remove unused CSS

## Notes

- Keep utility classes in index.css for commonly used patterns
- Use component classes (btn-primary, card, etc.) for consistency
- Prefer Tailwind's built-in classes over custom CSS
- Use the custom color palette for brand consistency