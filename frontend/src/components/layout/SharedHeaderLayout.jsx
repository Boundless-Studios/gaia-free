import React from 'react';
import { Link } from 'react-router-dom';
import { UserMenu } from '../../AppWithAuth0.jsx';

const SharedHeaderLayout = ({ children }) => {
  return (
    <header className="bg-gaia-border px-3 py-1 border-b-2 border-gaia-border flex justify-between items-center">
      {/* --- 1. Left Side (Always Visible) --- */}
      <Link
        to="/"
        className="text-sm font-semibold text-gaia-success m-0 hover:text-amber-400 transition-colors"
      >
        Fable Table
      </Link>

      {/* --- 2. Middle Section (Context-Specific Buttons) --- */}
      <div className="flex gap-2 items-center">
        {children}
      </div>

      {/* --- 3. Right Side (Always Visible) --- */}
      <div className="flex gap-3 items-center">
        <Link
          to="/about"
          className="px-3 py-1 bg-gaia-success text-white rounded text-xs hover:bg-green-600 transition-colors font-medium"
        >
          About
        </Link>
        <UserMenu />
      </div>
    </header>
  );
};

export default SharedHeaderLayout;
