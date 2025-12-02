import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/Auth0Context.jsx';
import apiService from '../services/apiService';
import { Modal } from './base-ui/Modal';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './base-ui/Card';
import { Select } from './base-ui/Select';
import { Button } from './base-ui/Button';
import { Input } from './base-ui/Input';
import { Alert } from './base-ui/Alert';

const CampaignManager = ({
  onCampaignSelect,
  currentCampaignId,
  onClose,
  isOpen,
  mode = 'select', // 'select' (default) or 'navigate' (for landing page)
  onRequestNewCampaign // callback to trigger campaign setup wizard (only used when mode='navigate')
}) => {
  const navigate = useNavigate();
  const { user, getAccessTokenSilently } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [sortBy, setSortBy] = useState('last_played');
  const [ascending, setAscending] = useState(false);
  
  // Form state
  const [newCampaign, setNewCampaign] = useState({
    title: '',
    description: '',
    game_style: 'balanced'
  });

  // Edit state
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');

  const [showSimple, setShowSimple] = useState(true);
  const [simpleCampaigns, setSimpleCampaigns] = useState([]);
  const [simpleLoading, setSimpleLoading] = useState(false);
  const [inviteTokenInput, setInviteTokenInput] = useState('');
  const [joinLoading, setJoinLoading] = useState(false);
  const [joinStatus, setJoinStatus] = useState({ success: null, message: '' });

  // Set up Auth0 token provider for apiService
  useEffect(() => {
    if (getAccessTokenSilently && !apiService.getAccessToken) {
      apiService.setTokenProvider(async () => {
        try {
          return await getAccessTokenSilently();
        } catch (error) {
          console.error('🔐 CampaignManager: Failed to get access token:', error);
          return null;
        }
      });
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    if (isOpen) {
      if (showSimple) {
        fetchSimpleCampaigns();
      } else {
        loadCampaigns();
      }
    }
  }, [sortBy, ascending, showSimple, isOpen]);

  const loadCampaigns = async () => {
    try {
      setLoading(true);
      
      const data = await apiService.listCampaigns({
        sortBy: sortBy,
        ascending: ascending,
        limit: 50
      });
      
      if (data.campaigns) {
        // Apply client-side sorting as well to ensure consistency
        const sortedCampaigns = sortCampaigns(data.campaigns, sortBy, ascending);
        setCampaigns(sortedCampaigns);
      } else {
        setCampaigns([]);
      }
    } catch (error) {
      console.error('Error loading campaigns:', error);
      setCampaigns([]);
    } finally {
      setLoading(false);
    }
  };

  const createCampaign = async () => {
    try {
      const data = await apiService.createCampaign({
        name: newCampaign.title,
        description: newCampaign.description,
        game_style: newCampaign.game_style
      });
      
      if (data.id) {
        setShowCreateForm(false);
        setNewCampaign({ title: '', description: '', game_style: 'balanced' });
        loadCampaigns();
        if (onCampaignSelect) {
          onCampaignSelect(data.id);
        }
      }
    } catch (error) {
      console.error('Error creating campaign:', error);
    }
  };

  const deleteCampaign = async (campaignId) => {
    if (!window.confirm('Are you sure you want to delete this campaign?')) {
      return;
    }

    try {
      const data = await apiService.deleteCampaign(campaignId);
      
      if (data.status === 'deleted') {
        if (showSimple) {
          await fetchSimpleCampaigns();
        } else {
          await loadCampaigns();
        }
        if (currentCampaignId === campaignId && onCampaignSelect) {
          onCampaignSelect(null);
        }
      }
    } catch (error) {
      console.error('Error deleting campaign:', error);
    }
  };

  const startEditCampaign = (campaign) => {
    setEditingCampaign(campaign.id || campaign.campaign_id);
    setEditTitle(campaign.name || campaign.title);
    setEditDescription(campaign.description || '');
  };

  const cancelEditCampaign = () => {
    setEditingCampaign(null);
    setEditTitle('');
    setEditDescription('');
  };

  const updateCampaign = async (campaignId) => {
    try {
      const data = await apiService.saveCampaign(campaignId, {
        name: editTitle,
        description: editDescription
      });
      
      if (data.status === 'updated') {
        setEditingCampaign(null);
        setEditTitle('');
        setEditDescription('');
        loadCampaigns();
      }
    } catch (error) {
      console.error('Error updating campaign:', error);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '-';
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const formatPlaytime = (hours) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)} minutes`;
    }
    return `${hours.toFixed(1)} hours`;
  };

  // Client-side sorting function
  const sortCampaigns = (campaigns, sortBy, ascending) => {
    const sorted = [...campaigns].sort((a, b) => {
      let aVal;
      let bVal;

      switch (sortBy) {
        case 'title': {
          aVal = (a.name || a.title || '').toLowerCase();
          bVal = (b.name || b.title || '').toLowerCase();
          break;
        }
        case 'created': {
          const aRaw = a.created_at || a.created;
          const bRaw = b.created_at || b.created;
          if (!aRaw && !bRaw) {
            // Fallback to title when timestamps are missing
            aVal = (a.name || a.title || '').toLowerCase();
            bVal = (b.name || b.title || '').toLowerCase();
          } else {
            aVal = new Date(aRaw || 0).getTime();
            bVal = new Date(bRaw || 0).getTime();
          }
          break;
        }
        case 'message_count': {
          const aCount = a.message_count || a.total_sessions || 0;
          const bCount = b.message_count || b.total_sessions || 0;
          aVal = aCount;
          bVal = bCount;
          break;
        }
        case 'last_played':
        default: {
          const aRaw = a.last_played || a.updated_at || a.created_at;
          const bRaw = b.last_played || b.updated_at || b.created_at;
          if (!aRaw && !bRaw) {
            // Fallback to title when timestamps are missing (common for simple campaigns)
            aVal = (a.name || a.title || '').toLowerCase();
            bVal = (b.name || b.title || '').toLowerCase();
          } else {
            aVal = new Date(aRaw || 0).getTime();
            bVal = new Date(bRaw || 0).getTime();
          }
          break;
        }
      }

      if (aVal < bVal) return ascending ? -1 : 1;
      if (aVal > bVal) return ascending ? 1 : -1;
      return 0;
    });
    
    return sorted;
  };

  const fetchSimpleCampaigns = async () => {
    setSimpleLoading(true);
    try {
      // Use role: 'dm' to fetch campaigns owned by the user.
      let data = await apiService.listSimpleCampaigns({ role: 'dm' });

      console.log(`📋 Fetched campaigns: role=dm, count=${data?.campaigns?.length || 0}`);

      if (data?.campaigns && data.campaigns.length > 0) {
        // Backend now handles filtering - no client-side filtering needed
        const sortedCampaigns = sortCampaigns(data.campaigns, sortBy, ascending);
        setSimpleCampaigns(sortedCampaigns);
      } else {
        setSimpleCampaigns([]);
      }
    } catch (error) {
      console.error('Error fetching simple campaigns:', error);
      setSimpleCampaigns([]);
    } finally {
      setSimpleLoading(false);
    }
  };

  // Ensure simple view uses a meaningful default sort
  useEffect(() => {
    if (showSimple && sortBy !== 'last_played') {
      setSortBy('last_played');
    }
  }, [showSimple]);

  useEffect(() => {
    if (isOpen) {
      setInviteTokenInput('');
      setJoinStatus({ success: null, message: '' });
    }
  }, [isOpen]);

  // If switching to structured view with a simple-only sort, reset to default
  useEffect(() => {
    if (!showSimple && sortBy === 'message_count') {
      setSortBy('last_played');
    }
  }, [showSimple]);

  const loadSimpleCampaignIntoGame = async (campaignId) => {
    try {
      // If in navigate mode, just navigate to the DM view
      if (mode === 'navigate') {
        navigate(`/${campaignId}/dm`);
        if (onClose) {
          onClose();
        }
        return;
      }

      // Otherwise, use the existing select mode behavior
      const data = await apiService.loadSimpleCampaign(campaignId);

      if (data.success && data.activated) {
        if (onCampaignSelect) {
          onCampaignSelect(campaignId);
        }
        if (onClose) {
          onClose();
        }
      }
    } catch (err) {
      console.error('Error loading simple campaign into game:', err);
    }
  };

  const handleJoinByToken = async () => {
    if (!inviteTokenInput.trim()) {
      setJoinStatus({ success: false, message: 'Enter an invite token to join.' });
      return;
    }
    try {
      setJoinLoading(true);
      const response = await apiService.joinSessionByInvite(inviteTokenInput.trim());
      setJoinStatus({ success: true, message: 'Joined session successfully.' });
      setInviteTokenInput('');
      if (onCampaignSelect) {
        await onCampaignSelect(response.session_id);
      }
      if (onClose) {
        onClose();
      }
    } catch (error) {
      console.error('Error joining session by invite:', error);
      setJoinStatus({ success: false, message: error.message || 'Failed to join session.' });
    } finally {
      setJoinLoading(false);
    }
  };

  const simpleSortOptions = [
    { value: 'last_played', label: 'Last Played' },
    { value: 'title', label: 'Title' },
    { value: 'message_count', label: 'Sessions' },
  ];

  const structuredSortOptions = [
    { value: 'last_played', label: 'Last Played' },
    { value: 'created', label: 'Created' },
    { value: 'title', label: 'Title' }
  ];

  const sortOptions = showSimple ? simpleSortOptions : structuredSortOptions;

  const gameStyleOptions = [
    { value: 'balanced', label: 'Balanced' },
    { value: 'roleplay', label: 'Roleplay Heavy' },
    { value: 'combat', label: 'Combat Heavy' },
    { value: 'exploration', label: 'Exploration' }
  ];

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Campaign Manager"
      width="max-w-4xl"
      className="h-[80vh]"
    >
      <div className="flex flex-col h-full">
        {/* Header Controls */}
        <div className="flex items-center justify-between mb-4">
          <Button
            onClick={() => setShowSimple(!showSimple)}
            variant="secondary"
          >
            {showSimple ? 'Show Structured Campaigns' : 'Show Simple Campaigns'}
          </Button>
          
          <div className="flex items-center gap-2">
            <Select
              value={sortBy}
              onChange={setSortBy}
              options={sortOptions}
              className="w-40"
              isInModal={true}
              forceNative={true}
            />
            <Button
              onClick={() => setAscending(!ascending)}
              variant="ghost"
              size="sm"
            >
              {ascending ? '↑' : '↓'}
            </Button>
            {mode === 'navigate' && (
              <Button
                onClick={() => {
                  if (onRequestNewCampaign) {
                    onRequestNewCampaign();
                  }
                }}
                variant="primary"
              >
                ✨ Create New Campaign
              </Button>
            )}
            {!showSimple && mode !== 'navigate' && (
              <Button
                onClick={() => setShowCreateForm(true)}
                variant="primary"
              >
                Create New
              </Button>
            )}
          </div>
        </div>

        {/* Create Campaign Form - Only show in select mode */}
        {showCreateForm && mode !== 'navigate' && (
          <Alert variant="info" className="mb-4">
            <div className="space-y-3">
              <Input
                value={newCampaign.title}
                onChange={(e) => setNewCampaign({...newCampaign, title: e.target.value})}
                placeholder="Campaign Title"
                label="Title"
              />
              <Input
                value={newCampaign.description}
                onChange={(e) => setNewCampaign({...newCampaign, description: e.target.value})}
                placeholder="Campaign Description"
                label="Description"
                multiline
                rows={3}
              />
              <Select
                value={newCampaign.game_style}
                onChange={(value) => setNewCampaign({...newCampaign, game_style: value})}
                options={gameStyleOptions}
                label="Game Style"
                isInModal={true}
                forceNative={true}
              />
              <div className="flex gap-2">
                <Button onClick={createCampaign} variant="primary">
                  Create
                </Button>
                <Button onClick={() => setShowCreateForm(false)} variant="secondary">
                  Cancel
                </Button>
              </div>
            </div>
          </Alert>
        )}

        {/* Join Shared Session */}
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="text-white text-base">Join Shared Session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={inviteTokenInput}
              onChange={(e) => {
                setInviteTokenInput(e.target.value);
                if (joinStatus.message) {
                  setJoinStatus({ success: null, message: '' });
                }
              }}
              placeholder="Enter invite token"
              label="Invite Token"
              disabled={joinLoading}
            />
            {joinStatus.message && (
              <Alert variant={joinStatus.success ? 'success' : 'error'}>
                {joinStatus.message}
              </Alert>
            )}
          </CardContent>
          <CardFooter className="flex justify-end gap-2">
            <Button
              onClick={handleJoinByToken}
              variant="primary"
              disabled={joinLoading || !inviteTokenInput.trim()}
            >
              {joinLoading ? 'Joining…' : 'Join Session'}
            </Button>
          </CardFooter>
        </Card>

        {/* Campaign List */}
        <div className="flex-1 overflow-y-auto">
          {showSimple ? (
            // Simple Campaigns
            <div>
              <h3 className="text-green-400 text-lg font-semibold mb-4">📁 Simple Campaigns</h3>
              {simpleLoading ? (
                <div className="text-center py-8 text-gray-400">Loading simple campaigns...</div>
              ) : simpleCampaigns.length === 0 ? (
                <Alert variant="info">No simple campaigns found.</Alert>
              ) : (
                <div className="space-y-3">
                  {simpleCampaigns.map((campaign) => (
                    <Card
                      key={campaign.id}
                      hover
                      selected={campaign.id === currentCampaignId}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="text-white font-semibold text-lg flex items-center gap-2">
                            {campaign.name}
                            {campaign.is_owner && (
                              <span className="text-xs px-2 py-0.5 rounded bg-green-800 text-green-100">Owner</span>
                            )}
                          </h4>
                          <p className="text-gray-400 text-sm">ID: {campaign.id}</p>
                          {(campaign.owner_email || (campaign.members && campaign.members.length)) && (
                            <div className="text-xs text-gray-500 mt-1 space-y-0.5">
                              {campaign.owner_email && (
                                <div>Owner: <span className="text-gray-300">{campaign.owner_email}</span></div>
                              )}
                              {campaign.members && campaign.members.length > 0 && (
                                <div>
                                  Members: <span className="text-gray-300">{Array.isArray(campaign.members) ? campaign.members.join(', ') : String(campaign.members)}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => loadSimpleCampaignIntoGame(campaign.id)}
                            variant="primary"
                            size="sm"
                          >
                            Load
                          </Button>
                          <Button
                            onClick={() => deleteCampaign(campaign.id)}
                            variant="danger"
                            size="sm"
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          ) : (
            // Structured Campaigns
            <div>
              <h3 className="text-blue-400 text-lg font-semibold mb-4">🏗️ Structured Campaigns</h3>
              {loading ? (
                <div className="text-center py-8 text-gray-400">Loading campaigns...</div>
              ) : campaigns.length === 0 ? (
                <Alert variant="info">No campaigns found. Create your first campaign!</Alert>
              ) : (
                <div className="space-y-3">
                  {campaigns.map((campaign) => {
                    const campaignId = campaign.id || campaign.campaign_id;
                    return (
                      <Card
                        key={campaignId}
                        hover
                        selected={campaignId === currentCampaignId}
                      >
                        {editingCampaign === campaignId ? (
                          <div className="space-y-3">
                            <Input
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              placeholder="Campaign Title"
                            />
                            <Input
                              value={editDescription}
                              onChange={(e) => setEditDescription(e.target.value)}
                              placeholder="Campaign Description"
                              multiline
                              rows={3}
                            />
                            <div className="flex gap-2">
                              <Button
                                onClick={() => updateCampaign(campaignId)}
                                variant="primary"
                                size="sm"
                              >
                                Save
                              </Button>
                              <Button
                                onClick={cancelEditCampaign}
                                variant="secondary"
                                size="sm"
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <CardHeader>
                              <CardTitle>{campaign.name || campaign.title}</CardTitle>
                            </CardHeader>
                            <CardContent>
                              {campaign.description && (
                                <p className="text-gray-400 mb-3">{campaign.description}</p>
                              )}
                              <div className="flex gap-4 text-sm text-gray-500 mb-2">
                                <span className="bg-purple-900/30 px-2 py-1 rounded">
                                  {campaign.game_style}
                                </span>
                                <span>Sessions: {campaign.message_count || campaign.total_sessions || 0}</span>
                                <span>Playtime: {formatPlaytime(campaign.total_playtime_hours || 0)}</span>
                              </div>
                              <div className="text-xs text-gray-600">
                                <div>Created: {formatDate(campaign.created_at)}</div>
                                <div>Last played: {formatDate(campaign.last_played)}</div>
                              </div>
                            </CardContent>
                            <CardFooter>
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => {
                                    if (mode === 'navigate') {
                                      navigate(`/${campaignId}/dm`);
                                      if (onClose) {
                                        onClose();
                                      }
                                    } else if (onCampaignSelect) {
                                      onCampaignSelect(campaignId);
                                    }
                                  }}
                                  variant="primary"
                                  size="sm"
                                >
                                  Load
                                </Button>
                                <Button
                                  onClick={() => startEditCampaign(campaign)}
                                  variant="secondary"
                                  size="sm"
                                >
                                  ✏️ Edit
                                </Button>
                                <Button
                                  onClick={() => deleteCampaign(campaignId)}
                                  variant="danger"
                                  size="sm"
                                >
                                  🗑️ Delete
                                </Button>
                              </div>
                            </CardFooter>
                          </>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default CampaignManager;
