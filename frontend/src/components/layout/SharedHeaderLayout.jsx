import React from 'react';
import { UserMenu } from '../../AppWithAuth0.jsx';

const SharedHeaderLayout = ({ children }) => {
  return (
    <header className="bg-gaia-border px-3 py-1 border-b-2 border-gaia-border flex justify-between items-center">
      {/* --- 1. Left Side (Always Visible) --- */}
      <h1 className="text-sm font-semibold text-gaia-success m-0">Fable Table</h1>

      {/* --- 2. Middle Section (Context-Specific Buttons) --- */}
      <div className="flex gap-2 items-center">
        {children}
      </div>

      {/* --- 3. Right Side (Always Visible) --- */}
      <UserMenu />
    </header>
  );
};

export default SharedHeaderLayout;
