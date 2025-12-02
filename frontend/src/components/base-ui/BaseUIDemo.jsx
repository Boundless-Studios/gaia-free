/**
 * Base UI Components Demo Page
 * Demonstrates all Base UI components integrated with Gaia's dark gaming theme
 */

import React, { useState } from 'react';
import Button, { ButtonVariants, ButtonSizes } from './Button';
import Input, { Textarea } from './Input';

const BaseUIDemo = () => {
  const [inputValue, setInputValue] = useState('');
  const [textareaValue, setTextareaValue] = useState('');
  const [showError, setShowError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      setIsLoading(false);
      alert('Form submitted!');
    }, 2000);
  };

  // Example icons for buttons
  const DiceIcon = () => (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M10 2L3 7v6l7 5 7-5V7l-7-5z"/>
    </svg>
  );

  const SwordIcon = () => (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M3 17l6-6 8 8M9 11l8-8-1-1-8 8"/>
    </svg>
  );

  return (
    <div className="min-h-screen bg-gaia-dark p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gaia-text mb-2">
            Base UI Components Demo
          </h1>
          <p className="text-gaia-text-secondary">
            Accessible, touch-friendly components for Gaia D&D
          </p>
        </div>

        {/* Button Examples */}
        <section className="bg-gaia-light rounded-lg p-6 border border-gaia-border">
          <h2 className="text-2xl font-bold text-gaia-text mb-4">Buttons</h2>
          
          <div className="space-y-4">
            {/* Button Variants */}
            <div>
              <h3 className="text-sm font-medium text-gaia-text-secondary mb-2">Variants</h3>
              <div className="flex flex-wrap gap-2">
                <Button variant="primary">Primary</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="danger">Danger</Button>
                <Button variant="ghost">Ghost</Button>
              </div>
            </div>

            {/* Button Sizes */}
            <div>
              <h3 className="text-sm font-medium text-gaia-text-secondary mb-2">Sizes</h3>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="small">Small</Button>
                <Button size="medium">Medium</Button>
                <Button size="large">Large</Button>
              </div>
            </div>

            {/* Button States */}
            <div>
              <h3 className="text-sm font-medium text-gaia-text-secondary mb-2">States</h3>
              <div className="flex flex-wrap gap-2">
                <Button disabled>Disabled</Button>
                <Button loading>Loading</Button>
                <Button icon={<DiceIcon />}>With Icon</Button>
                <Button icon={<SwordIcon />} iconPosition="right">Icon Right</Button>
              </div>
            </div>

            {/* Full Width Button */}
            <div>
              <h3 className="text-sm font-medium text-gaia-text-secondary mb-2">Full Width</h3>
              <Button fullWidth variant="primary" icon={<DiceIcon />}>
                Roll for Initiative
              </Button>
            </div>
          </div>
        </section>

        {/* Input Examples */}
        <section className="bg-gaia-light rounded-lg p-6 border border-gaia-border">
          <h2 className="text-2xl font-bold text-gaia-text mb-4">Form Inputs</h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Basic Input */}
            <Input
              label="Character Name"
              placeholder="Enter your character's name"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              required
            />

            {/* Input with Helper Text */}
            <Input
              label="Player Email"
              type="email"
              placeholder="player@example.com"
              helperText="We'll use this to save your campaign progress"
            />

            {/* Input with Error */}
            <Input
              label="Campaign Code"
              placeholder="Enter 6-digit code"
              error={showError}
              helperText={showError ? "Invalid campaign code" : "Join an existing campaign"}
              onChange={(e) => setShowError(e.target.value.length > 0 && e.target.value.length < 6)}
            />

            {/* Disabled Input */}
            <Input
              label="Dungeon Master"
              value="Auto-assigned"
              disabled
              helperText="The DM will be assigned automatically"
            />

            {/* Textarea */}
            <Textarea
              label="Character Backstory"
              placeholder="Tell us about your character's history..."
              value={textareaValue}
              onChange={(e) => setTextareaValue(e.target.value)}
              helperText="Optional: Add depth to your character"
              rows={6}
            />

            {/* Form Actions */}
            <div className="flex gap-2 pt-4">
              <Button 
                type="submit" 
                variant="primary" 
                loading={isLoading}
                icon={<SwordIcon />}
              >
                Start Adventure
              </Button>
              <Button 
                type="button" 
                variant="secondary"
                onClick={() => {
                  setInputValue('');
                  setTextareaValue('');
                }}
              >
                Clear Form
              </Button>
            </div>
          </form>
        </section>

        {/* Mobile Touch Targets Demo */}
        <section className="bg-gaia-light rounded-lg p-6 border border-gaia-border">
          <h2 className="text-2xl font-bold text-gaia-text mb-4">Mobile-Friendly Touch Targets</h2>
          <p className="text-gaia-text-secondary mb-4">
            All interactive elements meet the 44px minimum touch target size for mobile accessibility
          </p>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Button variant="primary" className="aspect-square">
              <DiceIcon />
            </Button>
            <Button variant="secondary" className="aspect-square">
              <SwordIcon />
            </Button>
            <Button variant="danger" className="aspect-square">
              ❌
            </Button>
            <Button variant="ghost" className="aspect-square">
              ⚙️
            </Button>
          </div>
        </section>

        {/* Integration Example */}
        <section className="bg-gaia-light rounded-lg p-6 border border-gaia-border">
          <h2 className="text-2xl font-bold text-gaia-text mb-4">Game Integration Example</h2>
          
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Enter your action..."
                fullWidth
                className="flex-1"
              />
              <Button variant="primary" icon={<DiceIcon />}>
                Roll
              </Button>
            </div>
            
            <div className="grid grid-cols-3 gap-2">
              <Button variant="secondary" fullWidth>Attack</Button>
              <Button variant="secondary" fullWidth>Defend</Button>
              <Button variant="secondary" fullWidth>Cast Spell</Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default BaseUIDemo;