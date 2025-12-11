import { useState, useCallback, useEffect } from 'react';
import apiService from '../services/apiService.js';

/**
 * Custom hook to manage session sharing and invite token functionality
 * Handles invite token generation, copying, and modal state
 *
 * @param {string} currentCampaignId - The active campaign ID
 * @param {Function} setInfoBanner - Function to show info banner messages
 * @returns {Object} Share and invite management interface
 */
export function useShareInvite(currentCampaignId, setInfoBanner) {
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareState, setShareState] = useState({
    loading: false,
    token: '',
    expiresAt: null,
    error: null,
    copied: false,
  });

  /**
   * Fetch or regenerate invite token for current campaign
   * @param {boolean} regenerate - Whether to regenerate existing token
   */
  const fetchInviteToken = useCallback(
    async (regenerate = false) => {
      if (!currentCampaignId) {
        setShareState((prev) => ({
          ...prev,
          loading: false,
          token: '',
          expiresAt: null,
          error: 'Select a campaign before sharing.',
          copied: false,
        }));
        return;
      }
      setShareState((prev) => ({
        ...prev,
        loading: true,
        error: null,
        copied: false,
      }));
      try {
        const response = await apiService.createSessionInvite(currentCampaignId, {
          regenerate,
        });
        setShareState({
          loading: false,
          token: response.invite_token,
          expiresAt: response.expires_at || null,
          error: null,
          copied: false,
        });
      } catch (err) {
        setShareState((prev) => ({
          ...prev,
          loading: false,
          token: '',
          expiresAt: null,
          error: err.message || 'Failed to create invite token',
          copied: false,
        }));
      }
    },
    [currentCampaignId]
  );

  /**
   * Auto-fetch invite token when share modal opens
   */
  useEffect(() => {
    if (!showShareModal) {
      return;
    }
    fetchInviteToken(false);
  }, [showShareModal, fetchInviteToken]);

  /**
   * Copy invite link to clipboard
   */
  const handleCopyInviteLink = useCallback(async () => {
    if (!shareState.token) {
      return;
    }
    try {
      const inviteLink = `${window.location.origin}/?invite=${shareState.token}`;
      await navigator.clipboard.writeText(inviteLink);
      setShareState((prev) => ({ ...prev, copied: true }));
      setInfoBanner('Invite link copied to clipboard.');
    } catch (err) {
      setShareState((prev) => ({
        ...prev,
        error: 'Failed to copy invite link',
        copied: false,
      }));
    }
  }, [shareState.token, setInfoBanner]);

  /**
   * Fetch invite token and immediately copy link to clipboard
   * Used for Share button click and auto-copy after campaign creation
   */
  const fetchAndCopyInviteLink = useCallback(
    async (campaignIdOverride = null) => {
      const targetCampaignId = campaignIdOverride || currentCampaignId;
      if (!targetCampaignId) {
        setInfoBanner('Select a campaign before sharing.');
        return;
      }
      try {
        const response = await apiService.createSessionInvite(targetCampaignId, {
          regenerate: false,
        });
        const token = response.invite_token;
        if (token) {
          const link = `${window.location.origin}/?invite=${token}`;
          await navigator.clipboard.writeText(link);
          setInfoBanner('Invite link copied to clipboard!');
          setShareState({
            loading: false,
            token,
            expiresAt: response.expires_at || null,
            error: null,
            copied: true,
          });
        }
      } catch (err) {
        console.error('Failed to fetch/copy invite link:', err);
        setInfoBanner('Failed to copy invite link.');
      }
    },
    [currentCampaignId, setInfoBanner]
  );

  /**
   * Computed invite link URL
   */
  const inviteLink =
    shareState.token && typeof window !== 'undefined'
      ? `${window.location.origin}/?invite=${shareState.token}`
      : '';

  return {
    // Modal state
    showModal: showShareModal,
    setShowModal: setShowShareModal,

    // Share state
    shareState,

    // Operations
    fetchToken: fetchInviteToken,
    copyInviteLink: handleCopyInviteLink,
    fetchAndCopyInviteLink,

    // Computed
    inviteLink,
  };
}
