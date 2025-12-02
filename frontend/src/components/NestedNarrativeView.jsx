import React, { useState } from 'react';
import './NestedNarrativeView.css';
import './ChatMessage.css';

const NestedNarrativeView = ({ narrative, className = '' }) => {
  const [expandedSections, setExpandedSections] = useState(new Set());

  const toggleSection = (sectionKey) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionKey)) {
      newExpanded.delete(sectionKey);
    } else {
      newExpanded.add(sectionKey);
    }
    setExpandedSections(newExpanded);
  };

  const renderValue = (value, key = '') => {
    if (typeof value === 'string') {
      return (
        <div className="chat-message-container user">
          <div className="chat-message-content">{value}</div>
        </div>
      );
    } else if (Array.isArray(value)) {
      return (
        <ul className="narrative-list">
          {value.map((item, index) => (
            <li key={index} className="narrative-list-item">
              {renderValue(item)}
            </li>
          ))}
        </ul>
      );
    } else if (typeof value === 'object' && value !== null) {
      return renderObject(value, key);
    }
    return (
      <div className="chat-message-container user">
        <div className="chat-message-content">{String(value)}</div>
      </div>
    );
  };

  const renderObject = (obj, parentKey = '') => {
    return (
      <div className="narrative-object">
        {Object.entries(obj).map(([key, value]) => {
          const sectionKey = parentKey ? `${parentKey}.${key}` : key;
          const isExpanded = expandedSections.has(sectionKey);
          const hasNestedContent = typeof value === 'object' && value !== null && !Array.isArray(value);
          
          return (
            <div key={key} className="narrative-section">
              <div 
                className={`narrative-section-header ${hasNestedContent ? 'clickable' : ''}`}
                onClick={() => hasNestedContent && toggleSection(sectionKey)}
              >
                <div className="narrative-section-title">
                  {hasNestedContent && (
                    <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>
                      {isExpanded ? '▼' : '▶'}
                    </span>
                  )}
                  <span className="section-name">{formatSectionName(key)}</span>
                </div>
              </div>
              
              <div className={`narrative-section-content ${hasNestedContent && !isExpanded ? 'collapsed' : ''}`}>
                {renderValue(value, sectionKey)}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const formatSectionName = (name) => {
    // Convert camelCase or snake_case to Title Case
    return name
      .replace(/([A-Z])/g, ' $1')
      .replace(/_/g, ' ')
      .replace(/^\w/, c => c.toUpperCase())
      .trim();
  };

  // If narrative is a string, render it as a chat message
  if (typeof narrative === 'string') {
    return (
      <div className={`nested-narrative-view ${className}`}>
        <div className="chat-message-container user">
          <div className="chat-message-content">{narrative}</div>
        </div>
      </div>
    );
  }

  // If narrative is an object, render it as nested structure
  if (typeof narrative === 'object' && narrative !== null) {
    return (
      <div className={`nested-narrative-view ${className}`}>
        {renderObject(narrative)}
      </div>
    );
  }

  return (
    <div className={`nested-narrative-view ${className}`}>
      <div className="chat-message-container user">
        <div className="chat-message-content">No narrative content available.</div>
      </div>
    </div>
  );
};

export default NestedNarrativeView; 