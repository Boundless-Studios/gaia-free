/**
 * GameSettingsPanel - UI for managing game preferences
 *
 * Handles three types of settings:
 * - DM Preferences: Auto-generation settings for dungeon masters
 * - Player Preferences: Audio and notification settings
 * - Campaign Settings: Tone, pace, difficulty, and model configuration
 */

import React, { useState, useEffect, useCallback } from 'react';
import apiService from '../services/apiService';
import { Alert } from './base-ui/Alert';
import { Select } from './base-ui/Select';
import { useRoom } from '../contexts/RoomContext.jsx';
import { loggers } from '../utils/logger.js';

const log = loggers.settings || loggers.api;

// Toggle Switch component
const Toggle = ({ checked, onChange, disabled = false, label }) => (
  <label className="flex items-center cursor-pointer">
    <div className="relative">
      <input
        type="checkbox"
        className="sr-only"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <div className={`w-10 h-6 rounded-full transition-colors ${
        checked ? 'bg-gaia-success' : 'bg-gray-600'
      } ${disabled ? 'opacity-50' : ''}`}>
        <div className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0'
        }`} />
      </div>
    </div>
    {label && <span className="ml-3 text-sm text-gray-200">{label}</span>}
  </label>
);

// Slider component for volume
const Slider = ({ value, onChange, min = 0, max = 100, label }) => (
  <div className="w-full">
    {label && <label className="block text-sm font-medium text-purple-200 mb-1">{label}</label>}
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-gaia-accent"
      />
      <span className="text-sm text-gray-300 w-10 text-right">{value}%</span>
    </div>
  </div>
);

// Section header component
const SectionHeader = ({ title, description }) => (
  <div className="mb-4 pb-2 border-b border-gaia-accent/20">
    <h4 className="text-lg font-semibold text-gaia-accent">{title}</h4>
    {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
  </div>
);

// Setting row component
const SettingRow = ({ label, description, children }) => (
  <div className="flex items-center justify-between py-3 border-b border-gray-700/50 last:border-b-0">
    <div className="flex-1 mr-4">
      <div className="text-sm font-medium text-gray-200">{label}</div>
      {description && <div className="text-xs text-gray-400 mt-0.5">{description}</div>}
    </div>
    <div className="flex-shrink-0">
      {children}
    </div>
  </div>
);

const GameSettingsPanel = ({ campaignId }) => {
  // Get room context to determine if user is DM
  const roomContext = useRoom();
  const isDM = roomContext?.isDMSeated ?? false;

  // State for each preference type
  const [dmPrefs, setDmPrefs] = useState(null);
  const [playerPrefs, setPlayerPrefs] = useState(null);
  const [campaignSettings, setCampaignSettings] = useState(null);

  // Loading and error states
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Active tab - defaults to 'dm' if user is DM, otherwise 'player'
  const [activeTab, setActiveTab] = useState('player');

  // Option definitions
  const toneOptions = [
    { value: 'serious', label: 'Serious' },
    { value: 'balanced', label: 'Balanced' },
    { value: 'lighthearted', label: 'Lighthearted' },
    { value: 'comedic', label: 'Comedic' },
  ];

  const paceOptions = [
    { value: 'slow', label: 'Slow & Deliberate' },
    { value: 'medium', label: 'Medium' },
    { value: 'fast', label: 'Fast-Paced' },
  ];

  const difficultyOptions = [
    { value: 'easy', label: 'Easy' },
    { value: 'medium', label: 'Medium' },
    { value: 'hard', label: 'Hard' },
    { value: 'deadly', label: 'Deadly' },
  ];

  // Fetch preferences on mount
  useEffect(() => {
    const fetchPreferences = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch based on role and campaign
        const promises = [];

        if (isDM) {
          promises.push(apiService.getDMPreferences().catch(e => {
            log.warn('Failed to fetch DM preferences:', e.message);
            return null;
          }));
        }

        promises.push(apiService.getPlayerPreferences().catch(e => {
          log.warn('Failed to fetch player preferences:', e.message);
          return null;
        }));

        if (campaignId) {
          promises.push(apiService.getCampaignSettings(campaignId).catch(e => {
            log.warn('Failed to fetch campaign settings:', e.message);
            return null;
          }));
        }

        const results = await Promise.all(promises);

        let idx = 0;
        if (isDM) {
          setDmPrefs(results[idx++]);
        }
        setPlayerPrefs(results[idx++]);
        if (campaignId) {
          setCampaignSettings(results[idx]);
        }

      } catch (err) {
        log.error('Failed to fetch preferences:', err);
        setError('Failed to load preferences');
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, [campaignId, isDM]);

  // Save handlers
  const saveDMPrefs = useCallback(async (updates) => {
    setSaving(true);
    setError(null);
    try {
      const result = await apiService.updateDMPreferences(updates);
      setDmPrefs(result);
      setSuccessMessage('DM preferences saved');
      setTimeout(() => setSuccessMessage(null), 2000);
    } catch (err) {
      log.error('Failed to save DM preferences:', err);
      setError('Failed to save DM preferences');
    } finally {
      setSaving(false);
    }
  }, []);

  const savePlayerPrefs = useCallback(async (updates) => {
    setSaving(true);
    setError(null);
    try {
      const result = await apiService.updatePlayerPreferences(updates);
      setPlayerPrefs(result);
      setSuccessMessage('Player preferences saved');
      setTimeout(() => setSuccessMessage(null), 2000);
    } catch (err) {
      log.error('Failed to save player preferences:', err);
      setError('Failed to save player preferences');
    } finally {
      setSaving(false);
    }
  }, []);

  const saveCampaignSettings = useCallback(async (updates) => {
    if (!campaignId) return;
    setSaving(true);
    setError(null);
    try {
      const result = await apiService.updateCampaignSettings(campaignId, updates);
      setCampaignSettings(result);
      setSuccessMessage('Campaign settings saved');
      setTimeout(() => setSuccessMessage(null), 2000);
    } catch (err) {
      log.error('Failed to save campaign settings:', err);
      setError('Failed to save campaign settings');
    } finally {
      setSaving(false);
    }
  }, [campaignId]);

  // Update handlers that auto-save
  const updateDMPref = (field, value) => {
    const updates = { [field]: value };
    setDmPrefs(prev => ({ ...prev, ...updates }));
    saveDMPrefs(updates);
  };

  const updatePlayerPref = (field, value) => {
    const updates = { [field]: value };
    setPlayerPrefs(prev => ({ ...prev, ...updates }));
    savePlayerPrefs(updates);
  };

  const updateCampaignSetting = (field, value) => {
    const updates = { [field]: value };
    setCampaignSettings(prev => ({ ...prev, ...updates }));
    saveCampaignSettings(updates);
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="text-gray-400">Loading preferences...</div>
      </div>
    );
  }

  return (
    <div className="game-settings-panel">
      {/* Status messages */}
      {error && (
        <Alert variant="error" className="mb-4">{error}</Alert>
      )}
      {successMessage && (
        <Alert variant="success" className="mb-4">{successMessage}</Alert>
      )}

      {/* Tab navigation */}
      <div className="flex border-b border-gray-700 mb-4">
        {isDM && (
          <button
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'dm'
                ? 'text-gaia-accent border-b-2 border-gaia-accent'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            onClick={() => setActiveTab('dm')}
          >
            DM Settings
          </button>
        )}
        <button
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'player'
              ? 'text-gaia-accent border-b-2 border-gaia-accent'
              : 'text-gray-400 hover:text-gray-200'
          }`}
          onClick={() => setActiveTab('player')}
        >
          Player Settings
        </button>
        {campaignId && isDM && (
          <button
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'campaign'
                ? 'text-gaia-accent border-b-2 border-gaia-accent'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            onClick={() => setActiveTab('campaign')}
          >
            Campaign Settings
          </button>
        )}
      </div>

      {/* DM Preferences Tab */}
      {activeTab === 'dm' && dmPrefs && (
        <div className="space-y-4">
          <SectionHeader
            title="Auto-Generation"
            description="Control automatic content generation during gameplay"
          />

          <SettingRow
            label="Auto Portrait Generation"
            description="Automatically generate portraits for new characters"
          >
            <Toggle
              checked={dmPrefs.auto_generate_portraits}
              onChange={(v) => updateDMPref('auto_generate_portraits', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow
            label="Auto Scene Images"
            description="Automatically generate images for new scenes"
          >
            <Toggle
              checked={dmPrefs.auto_scene_image_generation}
              onChange={(v) => updateDMPref('auto_scene_image_generation', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow
            label="Auto Audio Playback"
            description="Automatically play narration audio"
          >
            <Toggle
              checked={dmPrefs.auto_audio_playback}
              onChange={(v) => updateDMPref('auto_audio_playback', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow
            label="Show Dice Rolls"
            description="Display dice roll results in the game log"
          >
            <Toggle
              checked={dmPrefs.show_dice_rolls}
              onChange={(v) => updateDMPref('show_dice_rolls', v)}
              disabled={saving}
            />
          </SettingRow>

          <SectionHeader
            title="Gameplay"
            description="Default gameplay settings"
          />

          <SettingRow label="Default Difficulty">
            <Select
              value={dmPrefs.default_difficulty}
              onChange={(v) => updateDMPref('default_difficulty', v)}
              options={difficultyOptions}
              disabled={saving}
              isInModal={true}
              className="w-40"
            />
          </SettingRow>

          <SettingRow
            label="Critical Success"
            description="Enable natural 20 critical success"
          >
            <Toggle
              checked={dmPrefs.enable_critical_success}
              onChange={(v) => updateDMPref('enable_critical_success', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow
            label="Critical Failure"
            description="Enable natural 1 critical failure"
          >
            <Toggle
              checked={dmPrefs.enable_critical_failure}
              onChange={(v) => updateDMPref('enable_critical_failure', v)}
              disabled={saving}
            />
          </SettingRow>
        </div>
      )}

      {/* Player Preferences Tab */}
      {activeTab === 'player' && playerPrefs && (
        <div className="space-y-4">
          <SectionHeader
            title="Audio"
            description="Sound and music settings"
          />

          <SettingRow
            label="Enable Audio"
            description="Master audio toggle"
          >
            <Toggle
              checked={playerPrefs.enable_audio}
              onChange={(v) => updatePlayerPref('enable_audio', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow label="Audio Volume">
            <div className="w-48">
              <Slider
                value={playerPrefs.audio_volume}
                onChange={(v) => updatePlayerPref('audio_volume', v)}
                disabled={saving || !playerPrefs.enable_audio}
              />
            </div>
          </SettingRow>

          <SettingRow
            label="Background Music"
            description="Play ambient background music"
          >
            <Toggle
              checked={playerPrefs.enable_background_music}
              onChange={(v) => updatePlayerPref('enable_background_music', v)}
              disabled={saving || !playerPrefs.enable_audio}
            />
          </SettingRow>

          <SettingRow
            label="Sound Effects"
            description="Play combat and action sound effects"
          >
            <Toggle
              checked={playerPrefs.enable_sound_effects}
              onChange={(v) => updatePlayerPref('enable_sound_effects', v)}
              disabled={saving || !playerPrefs.enable_audio}
            />
          </SettingRow>

          <SectionHeader
            title="Notifications"
            description="In-game notification settings"
          />

          <SettingRow
            label="Turn Notifications"
            description="Notify when it's your turn"
          >
            <Toggle
              checked={playerPrefs.enable_turn_notifications}
              onChange={(v) => updatePlayerPref('enable_turn_notifications', v)}
              disabled={saving}
            />
          </SettingRow>

          <SettingRow
            label="Combat Notifications"
            description="Notify for combat events"
          >
            <Toggle
              checked={playerPrefs.enable_combat_notifications}
              onChange={(v) => updatePlayerPref('enable_combat_notifications', v)}
              disabled={saving}
            />
          </SettingRow>
        </div>
      )}

      {/* Campaign Settings Tab */}
      {activeTab === 'campaign' && campaignSettings && (
        <div className="space-y-4">
          <SectionHeader
            title="Campaign Style"
            description="Set the tone and pace of your campaign"
          />

          <SettingRow label="Campaign Tone">
            <Select
              value={campaignSettings.tone}
              onChange={(v) => updateCampaignSetting('tone', v)}
              options={toneOptions}
              disabled={saving}
              isInModal={true}
              className="w-40"
            />
          </SettingRow>

          <SettingRow label="Campaign Pace">
            <Select
              value={campaignSettings.pace}
              onChange={(v) => updateCampaignSetting('pace', v)}
              options={paceOptions}
              disabled={saving}
              isInModal={true}
              className="w-40"
            />
          </SettingRow>

          <SettingRow label="Difficulty">
            <Select
              value={campaignSettings.difficulty}
              onChange={(v) => updateCampaignSetting('difficulty', v)}
              options={difficultyOptions}
              disabled={saving}
              isInModal={true}
              className="w-40"
            />
          </SettingRow>

          <SectionHeader
            title="Player Configuration"
            description="Configure player limits and rules"
          />

          <SettingRow label="Maximum Players">
            <Select
              value={campaignSettings.max_players?.toString()}
              onChange={(v) => updateCampaignSetting('max_players', parseInt(v))}
              options={[1,2,3,4,5,6,7,8].map(n => ({ value: n.toString(), label: n.toString() }))}
              disabled={saving}
              isInModal={true}
              className="w-24"
            />
          </SettingRow>

          <SettingRow
            label="Allow PvP"
            description="Allow player vs player combat"
          >
            <Toggle
              checked={campaignSettings.allow_pvp}
              onChange={(v) => updateCampaignSetting('allow_pvp', v)}
              disabled={saving}
            />
          </SettingRow>
        </div>
      )}

      {/* Saving indicator */}
      {saving && (
        <div className="mt-4 text-center text-sm text-gray-400">
          Saving...
        </div>
      )}
    </div>
  );
};

export default GameSettingsPanel;
