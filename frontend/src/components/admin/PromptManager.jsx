import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useAuth } from '../../contexts/Auth0Context';

// Local storage utility for draft prompts
const PromptDraftStorage = {
  getKey: (promptId) => `prompt_draft_${promptId}`,

  saveDraft: (promptId, text, description) => {
    try {
      localStorage.setItem(
        PromptDraftStorage.getKey(promptId),
        JSON.stringify({ text, description, timestamp: Date.now() })
      );
    } catch (err) {
      console.error('Failed to save draft to localStorage:', err);
    }
  },

  loadDraft: (promptId) => {
    try {
      const item = localStorage.getItem(PromptDraftStorage.getKey(promptId));
      return item ? JSON.parse(item) : null;
    } catch (err) {
      console.error('Failed to load draft from localStorage:', err);
      return null;
    }
  },

  clearDraft: (promptId) => {
    try {
      localStorage.removeItem(PromptDraftStorage.getKey(promptId));
    } catch (err) {
      console.error('Failed to clear draft from localStorage:', err);
    }
  },

  hasDraft: (promptId) => {
    return localStorage.getItem(PromptDraftStorage.getKey(promptId)) !== null;
  }
};

// Local storage utility for UI state persistence
const UIStateStorage = {
  KEYS: {
    COLLAPSED_CATEGORIES: 'prompt_manager_collapsed_categories',
    SELECTED_PROMPT: 'prompt_manager_selected_prompt',
  },

  saveCollapsedCategories: (categories) => {
    try {
      localStorage.setItem(UIStateStorage.KEYS.COLLAPSED_CATEGORIES, JSON.stringify(categories));
    } catch (err) {
      console.error('Failed to save collapsed categories:', err);
    }
  },

  loadCollapsedCategories: () => {
    try {
      const item = localStorage.getItem(UIStateStorage.KEYS.COLLAPSED_CATEGORIES);
      return item ? JSON.parse(item) : null;
    } catch (err) {
      console.error('Failed to load collapsed categories:', err);
      return null;
    }
  },

  saveSelectedPrompt: (agentType, promptKey, versionNumber) => {
    try {
      localStorage.setItem(
        UIStateStorage.KEYS.SELECTED_PROMPT,
        JSON.stringify({ agentType, promptKey, versionNumber })
      );
    } catch (err) {
      console.error('Failed to save selected prompt:', err);
    }
  },

  loadSelectedPrompt: () => {
    try {
      const item = localStorage.getItem(UIStateStorage.KEYS.SELECTED_PROMPT);
      return item ? JSON.parse(item) : null;
    } catch (err) {
      console.error('Failed to load selected prompt:', err);
      return null;
    }
  },

  clearSelectedPrompt: () => {
    try {
      localStorage.removeItem(UIStateStorage.KEYS.SELECTED_PROMPT);
    } catch (err) {
      console.error('Failed to clear selected prompt:', err);
    }
  }
};

const PromptManager = () => {
  const createEmptyPromptForm = () => ({
    agentType: '',
    promptKey: '',
    category: '',
    promptText: '',
    description: '',
  });

  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [versions, setVersions] = useState({});
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [editingVersion, setEditingVersion] = useState(null);
  const [newPromptText, setNewPromptText] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [testInput, setTestInput] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [collapsedCategories, setCollapsedCategories] = useState({});
  const [isInitialized, setIsInitialized] = useState(false);
  const [saveState, setSaveState] = useState('saved'); // 'saved' | 'unsaved' | 'saving'
  const [showRestoreBanner, setShowRestoreBanner] = useState(false);
  const [draftToRestore, setDraftToRestore] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // { promptId, agentType, promptKey, versionNumber }
  const [isCreatePromptModalOpen, setIsCreatePromptModalOpen] = useState(false);
  const [newPromptForm, setNewPromptForm] = useState(createEmptyPromptForm);
  const [creatingPrompt, setCreatingPrompt] = useState(false);
  const [createPromptError, setCreatePromptError] = useState(null);
  const [promptSearchQuery, setPromptSearchQuery] = useState('');
  const { getAccessTokenSilently } = useAuth();

  // Refs for debouncing
  const autoSaveTimeout = useRef(null);
  const lastSavedText = useRef('');
  const editableRef = useRef(null);
  const cursorPositionRef = useRef(0);
  const isComposingRef = useRef(false); // Track if user is actively editing

  // Toggle category collapse
  const toggleCategory = (category) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Auto-save to localStorage with debouncing
  useEffect(() => {
    if (!editingVersion?.prompt_id) return;

    // Clear existing timeout
    if (autoSaveTimeout.current) {
      clearTimeout(autoSaveTimeout.current);
    }

    // Check if text has changed from last saved version
    const hasChanged = newPromptText !== (selectedVersion?.prompt_text || '');

    if (hasChanged) {
      setSaveState('unsaved');

      // Debounce auto-save
      autoSaveTimeout.current = setTimeout(() => {
        PromptDraftStorage.saveDraft(editingVersion.prompt_id, newPromptText, newDescription);
        lastSavedText.current = newPromptText;
      }, 500);
    } else {
      setSaveState('saved');
    }

    return () => {
      if (autoSaveTimeout.current) {
        clearTimeout(autoSaveTimeout.current);
      }
    };
  }, [newPromptText, newDescription, editingVersion?.prompt_id, selectedVersion?.prompt_text]);

  // Warn before navigating away with unsaved changes AND save draft immediately
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (saveState === 'unsaved') {
        // Save draft immediately before page unloads (don't rely on debounced save)
        if (editingVersion?.prompt_id) {
          PromptDraftStorage.saveDraft(editingVersion.prompt_id, newPromptText, newDescription);
        }
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [saveState, editingVersion?.prompt_id, newPromptText, newDescription]);

  // Save collapsed categories to localStorage whenever they change
  useEffect(() => {
    if (isInitialized && Object.keys(collapsedCategories).length > 0) {
      UIStateStorage.saveCollapsedCategories(collapsedCategories);
    }
  }, [collapsedCategories, isInitialized]);

  // Save selected prompt to localStorage whenever it changes
  useEffect(() => {
    if (selectedVersion) {
      UIStateStorage.saveSelectedPrompt(
        selectedVersion.agent_type,
        selectedVersion.prompt_key,
        selectedVersion.version_number
      );
    }
  }, [selectedVersion]);

  // Fetch prompt summaries
  const fetchPrompts = async () => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/prompts/summary', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch prompts');
      const data = await response.json();
      setPrompts(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch versions for a specific prompt
  const fetchVersions = async (agentType, promptKey) => {
    const key = `${agentType}:${promptKey}`;

    // Return cached versions if already loaded
    if (versions[key]) {
      return versions[key];
    }

    try {
      const token = await getAccessTokenSilently();
      const response = await fetch(
        `/api/admin/prompts/versions/${agentType}/${promptKey}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to fetch versions');
      const data = await response.json();
      setVersions(prev => ({ ...prev, [key]: data }));
      return data;
    } catch (err) {
      setError(err.message);
      return [];
    }
  };

  const openCreatePromptModal = () => {
    setNewPromptForm(createEmptyPromptForm());
    setCreatePromptError(null);
    setIsCreatePromptModalOpen(true);
  };

  const closeCreatePromptModal = () => {
    if (creatingPrompt) return;
    setIsCreatePromptModalOpen(false);
  };

  // Handle version selection from dropdown
  const handleVersionSelect = async (prompt, versionNumber) => {
    const key = `${prompt.agent_type}:${prompt.prompt_key}`;
    let versionList = versions[key];

    if (!versionList) {
      versionList = await fetchVersions(prompt.agent_type, prompt.prompt_key);
    }

    const version = versionList?.find(v => v.version_number === parseInt(versionNumber));
    if (version) {
      setSelectedVersion(version);
      setEditingVersion(version);

      // Check for draft in localStorage
      const draft = PromptDraftStorage.loadDraft(version.prompt_id);
      if (draft && draft.text !== version.prompt_text) {
        setShowRestoreBanner(true);
        setDraftToRestore(draft);
        setNewPromptText(version.prompt_text);
        setNewDescription('');
      } else {
        setShowRestoreBanner(false);
        setDraftToRestore(null);
        setNewPromptText(version.prompt_text);
        setNewDescription('');
      }

      setSaveState('saved');
    }
  };

  // Restore draft from localStorage
  const restoreDraft = () => {
    if (draftToRestore) {
      setNewPromptText(draftToRestore.text);
      setNewDescription(draftToRestore.description || '');

      // Update the DOM directly (same pattern as revertToSaved)
      if (editableRef.current) {
        editableRef.current.textContent = draftToRestore.text;
      }

      setShowRestoreBanner(false);
      setSaveState('unsaved');
    }
  };

  // Dismiss restore banner
  const dismissRestoreBanner = () => {
    if (editingVersion?.prompt_id) {
      PromptDraftStorage.clearDraft(editingVersion.prompt_id);
    }
    setShowRestoreBanner(false);
    setDraftToRestore(null);
  };

  // Revert to saved version
  const revertToSaved = () => {
    if (selectedVersion) {
      setNewPromptText(selectedVersion.prompt_text);
      setNewDescription('');

      // Update the DOM directly (useEffect only runs on version change)
      if (editableRef.current) {
        editableRef.current.textContent = selectedVersion.prompt_text;
      }

      if (editingVersion?.prompt_id) {
        PromptDraftStorage.clearDraft(editingVersion.prompt_id);
      }
      setSaveState('saved');
    }
  };

  const handleCreatePrompt = async () => {
    const agentType = newPromptForm.agentType.trim();
    const promptKey = newPromptForm.promptKey.trim();
    const category = newPromptForm.category.trim();
    const promptText = newPromptForm.promptText;
    const description = newPromptForm.description.trim();

    if (!agentType || !promptKey || !promptText.trim()) {
      setCreatePromptError('Agent Type, Prompt Key, and Prompt Text are required.');
      return;
    }

    try {
      setCreatingPrompt(true);
      setCreatePromptError(null);
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/prompts/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agent_type: agentType,
          prompt_key: promptKey,
          category: category || null,
          prompt_text: promptText,
          description: description || null,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to create prompt');
      }

      const createdPrompt = await response.json();
      setIsCreatePromptModalOpen(false);
      setNewPromptForm(createEmptyPromptForm());

      await fetchPrompts();

      const key = `${createdPrompt.agent_type}:${createdPrompt.prompt_key}`;
      setVersions(prev => ({ ...prev, [key]: undefined }));
      const versionList = await fetchVersions(createdPrompt.agent_type, createdPrompt.prompt_key);
      const latestVersion = versionList?.[0] || createdPrompt;

      setSelectedVersion(latestVersion);
      setEditingVersion(latestVersion);
      setNewPromptText(latestVersion.prompt_text || '');
      setNewDescription('');
      setShowRestoreBanner(false);
      setDraftToRestore(null);
      setSaveState('saved');
    } catch (err) {
      setCreatePromptError(err.message || 'Failed to create prompt');
    } finally {
      setCreatingPrompt(false);
    }
  };

  // Create new version
  const createNewVersion = async () => {
    if (!editingVersion || !newPromptText) return;

    try {
      setLoading(true);
      setSaveState('saving');
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/prompts/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agent_type: editingVersion.agent_type,
          prompt_key: editingVersion.prompt_key,
          category: editingVersion.category,
          prompt_text: newPromptText,
          description: newDescription,
        }),
      });

      if (!response.ok) throw new Error('Failed to create version');

      // Clear localStorage draft after successful save
      if (editingVersion.prompt_id) {
        PromptDraftStorage.clearDraft(editingVersion.prompt_id);
      }

      // Refresh versions and prompts
      const key = `${editingVersion.agent_type}:${editingVersion.prompt_key}`;
      setVersions(prev => ({ ...prev, [key]: undefined })); // Clear cache
      await fetchVersions(editingVersion.agent_type, editingVersion.prompt_key);
      await fetchPrompts();
      setNewPromptText('');
      setNewDescription('');
      setEditingVersion(null);
      setSelectedVersion(null);
      setSaveState('saved');
    } catch (err) {
      setError(err.message);
      setSaveState('unsaved');
    } finally {
      setLoading(false);
    }
  };

  // Activate a version
  const activateVersion = async (promptId) => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/prompts/${promptId}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to activate version');

      // Update was successful - refresh data while maintaining selection
      if (selectedVersion) {
        const key = `${selectedVersion.agent_type}:${selectedVersion.prompt_key}`;

        // Clear cache to force refresh
        setVersions(prev => ({ ...prev, [key]: undefined }));

        // Fetch fresh data
        const updatedVersions = await fetchVersions(selectedVersion.agent_type, selectedVersion.prompt_key);
        await fetchPrompts();

        // Update the selected version to reflect new active status
        const updatedVersion = updatedVersions?.find(v => v.prompt_id === promptId);
        if (updatedVersion) {
          setSelectedVersion(updatedVersion);
          setEditingVersion(updatedVersion);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Delete a version or all versions
  const deleteVersion = async (promptId, agentType, promptKey, allVersions = null) => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();

      if (allVersions && allVersions.length > 0) {
        // Delete all versions - delete inactive first, then active last
        const inactiveVersions = allVersions.filter(v => !v.is_active);
        const activeVersions = allVersions.filter(v => v.is_active);
        const errors = [];

        // Delete inactive versions first
        for (const version of inactiveVersions) {
          const response = await fetch(`/api/admin/prompts/${version.prompt_id}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (!response.ok) {
            const errorText = await response.text();
            errors.push(`Version ${version.version_number}: ${errorText || response.statusText}`);
          }
        }

        // Delete active versions last (when they're the only ones remaining)
        for (const version of activeVersions) {
          const response = await fetch(`/api/admin/prompts/${version.prompt_id}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (!response.ok) {
            const errorText = await response.text();
            errors.push(`Version ${version.version_number}: ${errorText || response.statusText}`);
          }
        }

        if (errors.length > 0) {
          throw new Error(`Failed to delete some versions:\n${errors.join('\n')}`);
        }
      } else {
        // Delete single version
        const response = await fetch(`/api/admin/prompts/${promptId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || 'Failed to delete version');
        }
      }

      // Clear delete confirmation
      setDeleteConfirm(null);

      // Clear cache to force refresh
      const key = `${agentType}:${promptKey}`;
      setVersions(prev => ({ ...prev, [key]: undefined }));

      // Fetch fresh data
      await fetchPrompts();

      // Only fetch versions if there are any left
      const updatedPrompt = prompts.find(p => p.agent_type === agentType && p.prompt_key === promptKey);
      if (updatedPrompt && updatedPrompt.total_versions > 0) {
        await fetchVersions(agentType, promptKey);
      }

      // If we deleted the currently selected/editing version, clear the editor
      if (selectedVersion?.agent_type === agentType && selectedVersion?.prompt_key === promptKey) {
        setEditingVersion(null);
        setSelectedVersion(null);
        setNewPromptText('');
        setNewDescription('');
        setSaveState('saved');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Test a prompt
  const testPrompt = async (promptId) => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/prompts/${promptId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          test_input: testInput,
        }),
      });

      if (!response.ok) throw new Error('Failed to test prompt');
      const data = await response.json();
      setTestResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const initPrompts = async () => {
      await fetchPrompts();

      if (!isInitialized && prompts.length > 0) {
        // Try to restore collapsed categories from localStorage
        const savedCategories = UIStateStorage.loadCollapsedCategories();

        if (savedCategories) {
          // Use saved collapsed state
          setCollapsedCategories(savedCategories);
        } else {
          // Collapse all categories by default
          const allCategories = {};
          prompts.forEach(prompt => {
            const category = prompt.category || 'uncategorized';
            allCategories[category] = true; // true means collapsed
          });
          setCollapsedCategories(allCategories);
        }

        // Try to restore selected prompt from localStorage
        const savedPrompt = UIStateStorage.loadSelectedPrompt();
        if (savedPrompt) {
          const { agentType, promptKey, versionNumber } = savedPrompt;

          // Find the prompt in the list
          const prompt = prompts.find(
            p => p.agent_type === agentType && p.prompt_key === promptKey
          );

          if (prompt) {
            // Fetch versions and select the saved version
            try {
              const versionList = await fetchVersions(agentType, promptKey);
              const version = versionList?.find(v => v.version_number === versionNumber);

              if (version) {
                setSelectedVersion(version);
                setEditingVersion(version);
                setNewPromptText(version.prompt_text || '');
                setNewDescription('');

                // Check for unsaved draft
                const draft = PromptDraftStorage.loadDraft(version.prompt_id);
                if (draft && draft.text !== version.prompt_text) {
                  setDraftToRestore(draft);
                  setShowRestoreBanner(true);
                }
              }
            } catch (err) {
              console.error('Failed to restore selected prompt:', err);
            }
          }
        }

        setIsInitialized(true);
      }
    };
    initPrompts();
  }, [prompts.length, isInitialized]);

  // Group prompts by category, then by agent_type
  const normalizedSearchQuery = promptSearchQuery.trim().toLowerCase();

  const filteredPrompts = useMemo(() => {
    if (!normalizedSearchQuery) return prompts;

    const hasColon = normalizedSearchQuery.includes(':');
    const [rawLeft, rawRight] = hasColon
      ? normalizedSearchQuery.split(':', 2).map(part => part.trim())
      : [null, null];

    return prompts.filter(prompt => {
      const composite = `${prompt.agent_type} ${prompt.prompt_key} ${prompt.category || ''}`.toLowerCase();
      const categoryMatch = prompt.category?.toLowerCase().includes(normalizedSearchQuery);

      if (hasColon && rawLeft && rawLeft !== 'category') {
        const agentMatch = prompt.agent_type.toLowerCase().includes(rawLeft);
        const promptMatch = rawRight ? prompt.prompt_key.toLowerCase().includes(rawRight) : true;
        if (agentMatch && promptMatch) {
          return true;
        }
      } else if (hasColon && rawLeft === 'category') {
        return prompt.category?.toLowerCase().includes(rawRight || '');
      }

      return composite.includes(normalizedSearchQuery) || categoryMatch;
    });
  }, [prompts, normalizedSearchQuery]);

  const groupedPrompts = filteredPrompts.reduce((acc, prompt) => {
    const category = prompt.category || 'uncategorized';
    if (!acc[category]) {
      acc[category] = {};
    }
    if (!acc[category][prompt.agent_type]) {
      acc[category][prompt.agent_type] = [];
    }
    acc[category][prompt.agent_type].push(prompt);
    return acc;
  }, {});

  const categoryOptions = useMemo(() => {
    const categories = new Set();
    prompts.forEach(prompt => {
      if (prompt.category) {
        categories.add(prompt.category);
      }
    });
    return Array.from(categories).sort((a, b) => a.localeCompare(b));
  }, [prompts]);

  const promptSearchSuggestions = useMemo(() => {
    const suggestions = new Set();
    prompts.forEach(prompt => {
      suggestions.add(`${prompt.agent_type}:${prompt.prompt_key}`);
    });

    categoryOptions.forEach(category => {
      suggestions.add(`category:${category}`);
    });

    return Array.from(suggestions).sort((a, b) => a.localeCompare(b));
  }, [prompts, categoryOptions]);

  // Handle clicking on a prompt name to select active version
  const handlePromptClick = async (prompt) => {
    const key = `${prompt.agent_type}:${prompt.prompt_key}`;
    let versionList = versions[key];

    if (!versionList) {
      versionList = await fetchVersions(prompt.agent_type, prompt.prompt_key);
    }

    // Find and select the latest version (highest version number)
    const latestVersion = versionList?.[0]; // Already sorted by version desc
    if (latestVersion) {
      setSelectedVersion(latestVersion);
      setEditingVersion(latestVersion);

      // Check for draft in localStorage
      const draft = PromptDraftStorage.loadDraft(latestVersion.prompt_id);
      if (draft && draft.text !== latestVersion.prompt_text) {
        setShowRestoreBanner(true);
        setDraftToRestore(draft);
        setNewPromptText(latestVersion.prompt_text);
        setNewDescription('');
      } else {
        setShowRestoreBanner(false);
        setDraftToRestore(null);
        setNewPromptText(latestVersion.prompt_text || '');
        setNewDescription('');
      }

      setSaveState('saved');
    }
  };

  // Save cursor position
  const saveCursorPosition = () => {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0 && editableRef.current) {
      const range = selection.getRangeAt(0);
      const preCaretRange = range.cloneRange();
      preCaretRange.selectNodeContents(editableRef.current);
      preCaretRange.setEnd(range.endContainer, range.endOffset);
      cursorPositionRef.current = preCaretRange.toString().length;
    }
  };

  // Restore cursor position
  const restoreCursorPosition = () => {
    if (!editableRef.current) return;

    const selection = window.getSelection();
    const range = document.createRange();
    let charCount = 0;
    let nodeStack = [editableRef.current];
    let node, foundStart = false;
    const targetOffset = cursorPositionRef.current;

    while (!foundStart && (node = nodeStack.pop())) {
      if (node.nodeType === Node.TEXT_NODE) {
        const nextCharCount = charCount + node.textContent.length;
        if (targetOffset >= charCount && targetOffset <= nextCharCount) {
          range.setStart(node, targetOffset - charCount);
          range.setEnd(node, targetOffset - charCount);
          foundStart = true;
        }
        charCount = nextCharCount;
      } else {
        for (let i = node.childNodes.length - 1; i >= 0; i--) {
          nodeStack.push(node.childNodes[i]);
        }
      }
    }

    if (foundStart) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
  };

  // Initialize contentEditable when version changes or component mounts
  // But don't interfere when user is actively editing
  useEffect(() => {
    if (editableRef.current && !isComposingRef.current) {
      const currentText = editableRef.current.textContent || '';
      if (currentText !== newPromptText) {
        // Set text content directly without triggering React re-render
        editableRef.current.textContent = newPromptText;
      }
    }
  }, [editingVersion?.prompt_id]); // Only sync when switching to a different prompt version

  // Render prompt text with template variable highlighting
  const renderPromptWithHighlights = (text) => {
    if (!text) return null;

    // Split on template variables {{variable_name}}
    const parts = text.split(/(\{\{[^}]+\}\})/g);

    return parts.map((part, idx) => {
      if (part.match(/^\{\{[^}]+\}\}$/)) {
        return (
          <span key={idx} className="bg-yellow-100 text-yellow-900 px-1 rounded font-semibold">
            {part}
          </span>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">Agent Prompt Manager</h1>
      </div>

      <div className="flex h-[calc(100vh-73px)]">
        {/* Prompt List with Version Dropdowns */}
        <div className="w-80 border-r border-gray-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-gray-200 bg-gray-50 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Prompts</h2>
              <button
                onClick={openCreatePromptModal}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-sm transition-colors"
              >
                <span role="img" aria-hidden="true">➕</span>
                Create
              </button>
            </div>
            <div className="relative">
              <input
                type="search"
                list="prompt-search-suggestions"
                value={promptSearchQuery}
                onChange={(e) => setPromptSearchQuery(e.target.value)}
                placeholder="Search by agent, key, or category..."
                className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-8"
              />
              {promptSearchQuery && (
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 px-2 text-gray-400 hover:text-gray-600"
                  onClick={() => setPromptSearchQuery('')}
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
              <datalist id="prompt-search-suggestions">
                {promptSearchSuggestions.map((suggestion) => (
                  <option key={suggestion} value={suggestion} />
                ))}
              </datalist>
            </div>
          </div>

          {error && (
            <div className="m-4 bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-red-800 text-sm">{error}</p>
              <button
                onClick={() => setError(null)}
                className="mt-2 text-xs text-red-600 hover:text-red-800 underline"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="p-3">
            {loading && prompts.length === 0 ? (
              <p className="text-gray-500 text-sm p-2">Loading prompts...</p>
            ) : (
              <div className="space-y-2">
                {filteredPrompts.length === 0 ? (
                  <p className="text-sm text-gray-500 px-2 py-4">
                    {promptSearchQuery ? 'No prompts match your search.' : 'No prompts available.'}
                  </p>
                ) : (
                  Object.entries(groupedPrompts).sort(([a], [b]) => a.localeCompare(b)).map(([category, agentTypes]) => {
                    const isCollapsed = collapsedCategories[category];

                    return (
                      <div key={category} className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                        {/* Category Header */}
                        <button
                          onClick={() => toggleCategory(category)}
                          className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 transition-colors"
                        >
                          <span className="uppercase tracking-wide">{category}</span>
                          <svg
                            className={`w-4 h-4 transition-transform text-gray-500 ${isCollapsed ? '-rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>

                        {/* Agent Types under Category */}
                        {!isCollapsed && (
                          <div className="divide-y divide-gray-100">
                            {Object.entries(agentTypes).map(([agentType, agentPrompts]) => (
                              <div key={agentType} className="p-2">
                                <h4 className="text-sm font-semibold text-gray-900 px-2 py-1.5 uppercase tracking-wide">
                                  {agentType}
                                </h4>
                                <div className="space-y-1">
                                  {agentPrompts.map((prompt) => {
                                    const key = `${prompt.agent_type}:${prompt.prompt_key}`;
                                    const promptVersions = versions[key] || [];
                                    const isSelected = selectedVersion?.agent_type === prompt.agent_type &&
                                                     selectedVersion?.prompt_key === prompt.prompt_key;

                                    return (
                                      <div
                                        key={key}
                                        className={`rounded-md transition-all ${
                                          isSelected
                                            ? 'bg-blue-50 border-l-3 border-l-blue-500 shadow-sm'
                                            : 'bg-white hover:bg-gray-50 border-l-3 border-l-transparent'
                                        }`}
                                      >
                                        <div className="p-2.5">
                                          <div
                                            className="flex items-start justify-between gap-2 cursor-pointer"
                                            onClick={() => handlePromptClick(prompt)}
                                          >
                                            <div className="flex-1 min-w-0">
                                              <div className="text-xs text-gray-600 mb-0.5">{prompt.prompt_key}</div>
                                              <div className="flex items-center gap-2 text-xs text-gray-500">
                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                                                  {prompt.total_versions} version{prompt.total_versions !== 1 ? 's' : ''}
                                                </span>
                                                {prompt.active_version && (
                                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                                                    ✓ v{prompt.active_version}
                                                  </span>
                                                )}
                                              </div>
                                            </div>
                                            <div className="flex flex-col gap-1.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                                              <select
                                                className="bg-white border border-gray-300 hover:border-gray-400 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                                                value={selectedVersion?.prompt_key === prompt.prompt_key ? selectedVersion?.version_number : (promptVersions.length > 0 ? promptVersions[0]?.version_number : prompt.active_version) || ''}
                                                onChange={(e) => {
                                                  if (e.target.value) {
                                                    handleVersionSelect(prompt, e.target.value);
                                                  }
                                                }}
                                                onFocus={async () => {
                                                  if (!versions[key]) {
                                                    await fetchVersions(prompt.agent_type, prompt.prompt_key);
                                                  }
                                                }}
                                              >
                                                {promptVersions.length > 0 ? (
                                                  promptVersions.map((version) => (
                                                    <option key={version.prompt_id} value={version.version_number}>
                                                      v{version.version_number}
                                                      {version.is_active ? ' ✓' : ''}
                                                    </option>
                                                  ))
                                                ) : prompt.active_version ? (
                                                  <option value={prompt.active_version}>
                                                    v{prompt.active_version} ✓
                                                  </option>
                                                ) : null}
                                              </select>
                                              <div className="flex gap-1">
                                                <button
                                                  onClick={async (e) => {
                                                    e.stopPropagation();
                                                    const versionList = await fetchVersions(prompt.agent_type, prompt.prompt_key);
                                                    const latestVersion = versionList?.[0];
                                                    if (latestVersion) {
                                                      const nextVersion = latestVersion.version_number + 1;
                                                      // Create a new editing version with incremented version number
                                                      setEditingVersion({
                                                        ...latestVersion,
                                                        version_number: nextVersion,
                                                        prompt_id: `new_v${nextVersion}` // Temporary ID for new version
                                                      });
                                                      setSelectedVersion(latestVersion);
                                                      setNewPromptText(latestVersion.prompt_text || '');
                                                      setNewDescription('');
                                                      setSaveState('unsaved');
                                                    }
                                                  }}
                                                  className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium transition-colors shadow-sm"
                                                  title="Create new version"
                                                >
                                                  + New
                                                </button>
                                                <button
                                                  onClick={async (e) => {
                                                    e.stopPropagation();
                                                    const key = `${prompt.agent_type}:${prompt.prompt_key}`;
                                                    let versionList = versions[key];
                                                    if (!versionList) {
                                                      versionList = await fetchVersions(prompt.agent_type, prompt.prompt_key);
                                                    }
                                                    setDeleteConfirm({
                                                      promptId: null,
                                                      agentType: prompt.agent_type,
                                                      promptKey: prompt.prompt_key,
                                                      versionNumber: null,
                                                      allVersions: versionList,
                                                      totalVersions: prompt.total_versions
                                                    });
                                                  }}
                                                  className="px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-medium transition-colors shadow-sm"
                                                  title="Delete all versions of this prompt"
                                                >
                                                  🗑
                                                </button>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* Center Panel - Editor (scrollable) */}
        <div className="flex-1 flex flex-col bg-gray-50">
          {!editingVersion ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-base">Select a prompt to view or edit</p>
            </div>
          ) : (
            <>
              {/* Sticky Header with Save Actions */}
              <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-semibold text-gray-900">
                        {editingVersion.agent_type} • {editingVersion.prompt_key}
                      </h2>
                      {/* Save State Indicator */}
                      {saveState === 'saved' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          Saved
                        </span>
                      )}
                      {saveState === 'unsaved' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                          </svg>
                          Unsaved changes
                        </span>
                      )}
                      {saveState === 'saving' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                          <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Saving...
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <div className="text-sm text-gray-500">
                        Version {editingVersion.version_number} • {selectedVersion ? `Created ${new Date(selectedVersion.created_at).toLocaleString()}` : 'New version'}
                      </div>
                      {selectedVersion?.is_active ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          ✓ Active
                        </span>
                      ) : selectedVersion && (
                        <button
                          onClick={() => activateVersion(selectedVersion.prompt_id)}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-600 hover:bg-green-700 text-white transition-colors"
                          disabled={loading}
                        >
                          {loading ? 'Activating...' : 'Activate'}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    {selectedVersion && (
                      <button
                        onClick={() => setDeleteConfirm({
                          promptId: selectedVersion.prompt_id,
                          agentType: selectedVersion.agent_type,
                          promptKey: selectedVersion.prompt_key,
                          versionNumber: selectedVersion.version_number
                        })}
                        disabled={loading}
                        className="px-4 py-2 bg-white border border-red-300 hover:bg-red-50 text-red-700 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Delete this version"
                      >
                        Delete Version
                      </button>
                    )}
                    {saveState === 'unsaved' && (
                      <button
                        onClick={revertToSaved}
                        className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors"
                      >
                        Revert to Saved
                      </button>
                    )}
                    <button
                      onClick={() => {
                        if (editingVersion?.prompt_id) {
                          PromptDraftStorage.clearDraft(editingVersion.prompt_id);
                        }
                        setEditingVersion(null);
                        setSelectedVersion(null);
                        setNewPromptText('');
                        setNewDescription('');
                        setSaveState('saved');
                      }}
                      className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={createNewVersion}
                      disabled={!newPromptText || loading}
                      className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                    >
                      {loading ? 'Saving...' : 'Save as New Version'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Restore Banner */}
                {showRestoreBanner && draftToRestore && (
                  <div className="bg-blue-50 border-l-4 border-blue-500 p-4 shadow-sm rounded-r-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                          </svg>
                          <h4 className="font-semibold text-blue-900">Unsaved Changes Found</h4>
                        </div>
                        <p className="text-base text-blue-800 mb-3">
                          You have unsaved changes from {new Date(draftToRestore.timestamp).toLocaleString()}.
                        </p>
                        <div className="flex gap-3">
                          <button
                            onClick={restoreDraft}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                          >
                            Restore Draft
                          </button>
                          <button
                            onClick={dismissRestoreBanner}
                            className="px-4 py-2 bg-white border border-blue-300 hover:bg-blue-50 text-blue-700 rounded-lg text-sm font-medium transition-colors"
                          >
                            Discard Draft
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {selectedVersion?.description && (
                  <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
                    <p className="text-base text-blue-900">{selectedVersion.description}</p>
                  </div>
                )}

                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <label className="block text-base font-medium mb-2 text-gray-700">
                    Version Description (optional)
                  </label>
                  <input
                    type="text"
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    placeholder="What changed in this version?"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <label className="block text-base font-medium mb-3 text-gray-700">
                    Prompt Text
                  </label>
                  <div
                    ref={editableRef}
                    contentEditable
                    suppressContentEditableWarning
                    onFocus={() => {
                      isComposingRef.current = true;
                    }}
                    onBlur={() => {
                      isComposingRef.current = false;
                      // Ensure state is synced when user stops editing
                      if (editableRef.current) {
                        setNewPromptText(editableRef.current.textContent || '');
                      }
                    }}
                    onInput={(e) => {
                      // Update state during typing, but don't interfere with the DOM
                      setNewPromptText(e.currentTarget.textContent || '');
                    }}
                    onKeyDown={(e) => {
                      // Handle Tab key
                      if (e.key === 'Tab') {
                        e.preventDefault();
                        document.execCommand('insertText', false, '  ');
                      }
                    }}
                    className="w-full bg-white border border-gray-300 rounded-lg px-4 py-3 font-mono text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent leading-relaxed h-[60vh] whitespace-pre-wrap overflow-auto"
                    style={{ wordBreak: 'break-word' }}
                    data-placeholder="Enter prompt text..."
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Panel - Test (sticky, always visible) */}
        <div className="w-144 border-l border-gray-200 bg-white flex flex-col">
          {!editingVersion ? (
            <div className="flex items-center justify-center h-full text-gray-400 px-6 text-center">
              <p className="text-base">Select a prompt to test it</p>
            </div>
          ) : (
            <>
              <div className="border-b border-gray-200 px-6 py-4 bg-gray-50">
                <h3 className="font-semibold text-gray-900 text-base">Test Prompt</h3>
                <p className="text-sm text-gray-500 mt-1">Enter input to test the agent</p>
              </div>

              <div className="flex-1 overflow-y-auto p-6">
                {testResult && (
                  <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
                    <h4 className="font-semibold mb-2 text-gray-900 text-base">Result:</h4>
                    {testResult.error ? (
                      <p className="text-red-600 text-base">{testResult.error}</p>
                    ) : (
                      <div className="space-y-2 text-base">
                        <p className="text-gray-600 font-medium">Response:</p>
                        <p className="whitespace-pre-wrap text-gray-800">{testResult.agent_response}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="sticky bottom-0 border-t border-gray-200 p-6 bg-white">
                <textarea
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  placeholder="Enter test input for the agent..."
                  rows={4}
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 mb-3 text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={() => testPrompt(editingVersion.prompt_id)}
                  disabled={!testInput || loading || !editingVersion?.prompt_id}
                  className="w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors shadow-sm"
                >
                  {loading ? 'Testing...' : 'Test Prompt'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create Prompt Modal */}
      {isCreatePromptModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40" onClick={closeCreatePromptModal}>
          <div className="bg-white rounded-lg shadow-2xl max-w-3xl w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="border-b border-gray-200 px-6 py-4 bg-gray-50 rounded-t-lg">
              <h3 className="text-lg font-semibold text-gray-900">Create New Prompt</h3>
              <p className="text-sm text-gray-500 mt-1">
                Define a brand new agent type + prompt key combination and its initial version.
              </p>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!creatingPrompt) {
                  handleCreatePrompt();
                }
              }}
            >
              <div className="p-6 space-y-5">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Agent Type<span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newPromptForm.agentType}
                      onChange={(e) => setNewPromptForm(prev => ({ ...prev, agentType: e.target.value }))}
                      placeholder="e.g. dungeon_master"
                      className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Prompt Key<span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newPromptForm.promptKey}
                      onChange={(e) => setNewPromptForm(prev => ({ ...prev, promptKey: e.target.value }))}
                      placeholder="e.g. scene_describer_intro"
                      className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Category
                    </label>
                    <input
                      type="text"
                      list="prompt-category-options"
                      value={newPromptForm.category}
                      onChange={(e) => setNewPromptForm(prev => ({ ...prev, category: e.target.value }))}
                      placeholder="Select or type a category"
                      className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <datalist id="prompt-category-options">
                      {categoryOptions.map(category => (
                        <option key={category} value={category} />
                      ))}
                    </datalist>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Description (optional)
                    </label>
                    <input
                      type="text"
                      value={newPromptForm.description}
                      onChange={(e) => setNewPromptForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Brief summary of this prompt version"
                      className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Prompt Text<span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={newPromptForm.promptText}
                      onChange={(e) => setNewPromptForm(prev => ({ ...prev, promptText: e.target.value }))}
                      rows={10}
                      placeholder="Write the initial prompt content..."
                      className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono whitespace-pre-wrap"
                    />
                  </div>
                </div>

                {createPromptError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {createPromptError}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
                <button
                  type="button"
                  onClick={closeCreatePromptModal}
                  disabled={creatingPrompt}
                  className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingPrompt}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {creatingPrompt ? 'Creating...' : 'Create Prompt'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setDeleteConfirm(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {deleteConfirm.allVersions ? 'Delete All Versions?' : 'Delete Version?'}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">This action cannot be undone</p>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <div className="text-base space-y-1">
                  <p className="text-gray-700">
                    <span className="font-medium">Agent:</span> {deleteConfirm.agentType}
                  </p>
                  <p className="text-gray-700">
                    <span className="font-medium">Prompt:</span> {deleteConfirm.promptKey}
                  </p>
                  {deleteConfirm.allVersions ? (
                    <>
                      <p className="text-gray-700">
                        <span className="font-medium">Versions to delete:</span> {deleteConfirm.totalVersions || deleteConfirm.allVersions.length}
                      </p>
                      {deleteConfirm.allVersions.some(v => v.is_active) && (
                        <p className="text-red-600 font-medium mt-2">
                          ⚠️ Warning: This includes active version(s). Deactivate first or deletion will fail.
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-gray-700">
                      <span className="font-medium">Version:</span> {deleteConfirm.versionNumber}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  disabled={loading}
                  className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteVersion(deleteConfirm.promptId, deleteConfirm.agentType, deleteConfirm.promptKey, deleteConfirm.allVersions)}
                  disabled={loading}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {loading ? 'Deleting...' : (deleteConfirm.allVersions ? 'Delete All Versions' : 'Delete Version')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PromptManager;
