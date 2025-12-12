import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../../contexts/Auth0Context';

const CampaignInspector = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [environmentFilter, setEnvironmentFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [turnFilter, setTurnFilter] = useState('');
  const [expandedEvents, setExpandedEvents] = useState(new Set());
  const { getAccessTokenSilently } = useAuth();

  // Fetch campaign statistics
  const fetchStats = async () => {
    try {
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/campaigns/stats', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  // Fetch campaigns list
  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      let url = '/api/admin/campaigns?limit=100';
      if (environmentFilter) url += `&environment=${environmentFilter}`;
      if (activeFilter !== '') url += `&is_active=${activeFilter}`;
      if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;

      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch campaigns');
      const data = await response.json();
      setCampaigns(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch campaign details
  const fetchCampaignDetails = async (campaignId) => {
    try {
      setLoading(true);
      setEvents([]);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/campaigns/${campaignId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch campaign details');
      const data = await response.json();
      setSelectedCampaign(data);
      // Also fetch events
      await fetchCampaignEvents(campaignId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch campaign events
  const fetchCampaignEvents = async (campaignId) => {
    try {
      const token = await getAccessTokenSilently();
      let url = `/api/admin/campaigns/${campaignId}/events?limit=200`;
      if (eventTypeFilter) url += `&event_type=${eventTypeFilter}`;
      if (turnFilter) url += `&turn_number=${turnFilter}`;

      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch events');
      const data = await response.json();
      setEvents(data);
    } catch (err) {
      console.error('Error fetching events:', err);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchCampaigns();
  }, []);

  useEffect(() => {
    fetchCampaigns();
  }, [environmentFilter, activeFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCampaigns();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Refetch events when filters change
  useEffect(() => {
    if (selectedCampaign) {
      fetchCampaignEvents(selectedCampaign.external_campaign_id);
    }
  }, [eventTypeFilter, turnFilter]);

  // Get unique environments from campaigns
  const environments = useMemo(() => {
    return [...new Set(campaigns.map(c => c.environment))].filter(Boolean);
  }, [campaigns]);

  // Get unique turn numbers from events
  const turnNumbers = useMemo(() => {
    return [...new Set(events.map(e => e.turn_number))].sort((a, b) => a - b);
  }, [events]);

  // Group events by turn
  const eventsByTurn = useMemo(() => {
    return events.reduce((acc, event) => {
      const turn = event.turn_number;
      if (!acc[turn]) acc[turn] = [];
      acc[turn].push(event);
      return acc;
    }, {});
  }, [events]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const formatShortDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const toggleEventExpanded = (eventId) => {
    const newExpanded = new Set(expandedEvents);
    if (newExpanded.has(eventId)) {
      newExpanded.delete(eventId);
    } else {
      newExpanded.add(eventId);
    }
    setExpandedEvents(newExpanded);
  };

  const getEventTypeColor = (type) => {
    switch (type) {
      case 'player_input': return 'bg-blue-100 text-blue-700';
      case 'dm_input': return 'bg-purple-100 text-purple-700';
      case 'turn_input': return 'bg-yellow-100 text-yellow-700';
      case 'assistant': return 'bg-green-100 text-green-700';
      case 'system': return 'bg-gray-100 text-gray-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getRoleColor = (role) => {
    switch (role) {
      case 'player': return 'bg-blue-50 text-blue-600';
      case 'dm': return 'bg-purple-50 text-purple-600';
      case 'assistant': return 'bg-green-50 text-green-600';
      case 'system': return 'bg-gray-50 text-gray-600';
      default: return 'bg-gray-50 text-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">Campaign Inspector</h1>
        {stats && (
          <div className="flex gap-6 mt-2 text-sm text-gray-600">
            <span>Total: <strong>{stats.total_campaigns}</strong></span>
            <span>Active: <strong className="text-green-600">{stats.active_campaigns}</strong></span>
            <span>Inactive: <strong className="text-red-600">{stats.inactive_campaigns}</strong></span>
            <span>Processing: <strong className="text-yellow-600">{stats.campaigns_processing}</strong></span>
            <span>Events: <strong>{stats.total_events}</strong></span>
          </div>
        )}
      </div>

      <div className="flex h-[calc(100vh-100px)]">
        {/* Campaign List */}
        <div className="w-96 border-r border-gray-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-gray-200 bg-gray-50 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Campaigns</h2>
              <button
                onClick={() => { fetchCampaigns(); fetchStats(); }}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-sm transition-colors"
              >
                Refresh
              </button>
            </div>

            {/* Search */}
            <div className="relative">
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search campaigns..."
                className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-8"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 px-2 text-gray-400 hover:text-gray-600"
                  onClick={() => setSearchQuery('')}
                >
                  x
                </button>
              )}
            </div>

            {/* Filters */}
            <div className="flex gap-2 flex-wrap">
              <select
                value={environmentFilter}
                onChange={(e) => setEnvironmentFilter(e.target.value)}
                className="bg-white border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Environments</option>
                {environments.map(env => (
                  <option key={env} value={env}>{env}</option>
                ))}
              </select>
              <select
                value={activeFilter}
                onChange={(e) => setActiveFilter(e.target.value)}
                className="bg-white border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Status</option>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
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
            {loading && campaigns.length === 0 ? (
              <p className="text-gray-500 text-sm p-2">Loading campaigns...</p>
            ) : campaigns.length === 0 ? (
              <p className="text-gray-500 text-sm p-2">No campaigns found.</p>
            ) : (
              <div className="space-y-2">
                {campaigns.map((campaign) => {
                  const isSelected = selectedCampaign?.campaign_id === campaign.campaign_id;
                  return (
                    <div
                      key={campaign.campaign_id}
                      onClick={() => fetchCampaignDetails(campaign.external_campaign_id)}
                      className={`p-3 cursor-pointer transition-all rounded-lg border ${
                        isSelected
                          ? 'bg-blue-50 border-blue-300 shadow-sm'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      } ${!campaign.is_active ? 'opacity-60' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 truncate">
                            {campaign.name || campaign.external_campaign_id}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5 font-mono truncate">
                            {campaign.external_campaign_id}
                          </div>
                          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                              campaign.environment === 'production' ? 'bg-green-100 text-green-700' :
                              campaign.environment === 'staging' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {campaign.environment}
                            </span>
                            {campaign.is_processing && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-600 text-white">
                                PROCESSING
                              </span>
                            )}
                            {!campaign.is_active && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-600 text-white">
                                INACTIVE
                              </span>
                            )}
                            <span className="text-xs text-gray-500">
                              Turn {campaign.current_turn}
                            </span>
                            <span className="text-xs text-gray-400">
                              {campaign.event_count} events
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Campaign Details */}
        <div className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
          {!selectedCampaign ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-base">Select a campaign to view details</p>
            </div>
          ) : (
            <>
              {/* Sticky Header */}
              <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-semibold text-gray-900">
                        {selectedCampaign.name || selectedCampaign.external_campaign_id}
                      </h2>
                      {!selectedCampaign.is_active && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                          Inactive
                        </span>
                      )}
                      {selectedCampaign.state?.is_processing && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-600 text-white">
                          Processing
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 mt-1 font-mono">
                      {selectedCampaign.external_campaign_id}
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedCampaign(null)}
                    className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Basic Info */}
                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <h3 className="text-base font-medium mb-3 text-gray-700">Campaign Information</h3>
                  <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-gray-500">Campaign ID (DB)</dt>
                      <dd className="font-mono text-gray-900 text-xs">{selectedCampaign.campaign_id}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Environment</dt>
                      <dd className="text-gray-900">{selectedCampaign.environment}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Owner</dt>
                      <dd className="text-gray-900">{selectedCampaign.owner_id || 'N/A'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Status</dt>
                      <dd className="text-gray-900">{selectedCampaign.is_active ? 'Active' : 'Inactive'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Created</dt>
                      <dd className="text-gray-900">{formatDate(selectedCampaign.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Last Updated</dt>
                      <dd className="text-gray-900">{formatDate(selectedCampaign.updated_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Total Events</dt>
                      <dd className="text-gray-900">{selectedCampaign.event_count}</dd>
                    </div>
                  </dl>
                  {selectedCampaign.description && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <dt className="text-gray-500 text-sm mb-1">Description</dt>
                      <dd className="text-gray-900 text-sm">{selectedCampaign.description}</dd>
                    </div>
                  )}
                </div>

                {/* Campaign State */}
                {selectedCampaign.state && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Campaign State</h3>
                    <dl className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <dt className="text-gray-500">Current Turn</dt>
                        <dd className="text-2xl font-bold text-blue-600">{selectedCampaign.state.current_turn}</dd>
                      </div>
                      <div>
                        <dt className="text-gray-500">Processing Status</dt>
                        <dd className={`font-medium ${selectedCampaign.state.is_processing ? 'text-yellow-600' : 'text-green-600'}`}>
                          {selectedCampaign.state.is_processing ? 'Processing Turn...' : 'Idle'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-gray-500">Last Turn Started</dt>
                        <dd className="text-gray-900">{formatDate(selectedCampaign.state.last_turn_started_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-gray-500">Last Turn Completed</dt>
                        <dd className="text-gray-900">{formatDate(selectedCampaign.state.last_turn_completed_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-gray-500">State Version</dt>
                        <dd className="text-gray-900">{selectedCampaign.state.version}</dd>
                      </div>
                    </dl>
                    {selectedCampaign.state.active_turn && (
                      <div className="mt-4 pt-4 border-t border-gray-100">
                        <dt className="text-gray-500 text-sm mb-2">Active Turn Data</dt>
                        <pre className="bg-gray-50 p-3 rounded-lg text-xs text-gray-900 overflow-x-auto">
                          {JSON.stringify(selectedCampaign.state.active_turn, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Turn Events */}
                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-base font-medium text-gray-700">Turn Events ({events.length})</h3>
                    <div className="flex gap-2">
                      <select
                        value={eventTypeFilter}
                        onChange={(e) => setEventTypeFilter(e.target.value)}
                        className="bg-white border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700"
                      >
                        <option value="">All Types</option>
                        <option value="player_input">Player Input</option>
                        <option value="dm_input">DM Input</option>
                        <option value="turn_input">Turn Input</option>
                        <option value="assistant">Assistant</option>
                        <option value="system">System</option>
                      </select>
                      <select
                        value={turnFilter}
                        onChange={(e) => setTurnFilter(e.target.value)}
                        className="bg-white border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700"
                      >
                        <option value="">All Turns</option>
                        {turnNumbers.map(turn => (
                          <option key={turn} value={turn}>Turn {turn}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {events.length === 0 ? (
                    <p className="text-gray-500 text-sm">No events found.</p>
                  ) : (
                    <div className="space-y-4">
                      {Object.entries(eventsByTurn).map(([turn, turnEvents]) => (
                        <div key={turn} className="border border-gray-200 rounded-lg overflow-hidden">
                          <div className="px-4 py-2 bg-gray-50 text-sm font-semibold text-gray-700 flex items-center justify-between">
                            <span>Turn {turn}</span>
                            <span className="text-xs text-gray-500 font-normal">{turnEvents.length} events</span>
                          </div>
                          <div className="divide-y divide-gray-100">
                            {turnEvents.map((event) => {
                              const isExpanded = expandedEvents.has(event.event_id);
                              // Extract readable content preview
                              const getContentPreview = () => {
                                if (!event.content) return null;
                                // For player/dm input, show the text
                                if (event.content.text) return event.content.text;
                                // For turn_input, show the combined prompt
                                if (event.content.combined_prompt) return event.content.combined_prompt;
                                // For assistant responses, try to find narrative or text
                                if (event.content.narrative) return event.content.narrative;
                                if (event.content.response) return event.content.response;
                                if (event.content.message) return event.content.message;
                                // For system messages
                                if (typeof event.content === 'string') return event.content;
                                return null;
                              };
                              const contentPreview = getContentPreview();

                              return (
                                <div key={event.event_id} className="p-3">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getEventTypeColor(event.type)}`}>
                                        {event.type}
                                      </span>
                                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${getRoleColor(event.role)}`}>
                                        {event.role}
                                      </span>
                                      <span className="text-xs text-gray-400">
                                        idx: {event.event_index}
                                      </span>
                                    </div>
                                    <span className="text-xs text-gray-400 shrink-0">
                                      {formatShortDate(event.created_at)}
                                    </span>
                                  </div>

                                  {/* Always show content preview */}
                                  {contentPreview && (
                                    <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap break-words bg-gray-50 rounded p-2 max-h-48 overflow-y-auto">
                                      {contentPreview}
                                    </div>
                                  )}

                                  {/* Expandable raw JSON section */}
                                  <div className="mt-2">
                                    <button
                                      onClick={() => toggleEventExpanded(event.event_id)}
                                      className="text-xs text-blue-600 hover:text-blue-800"
                                    >
                                      {isExpanded ? '- Hide raw data' : '+ Show raw data'}
                                    </button>
                                    {isExpanded && (
                                      <div className="mt-2 space-y-2">
                                        <div className="text-xs text-gray-500 font-mono">
                                          ID: {event.event_id}
                                        </div>
                                        <div>
                                          <div className="text-xs text-gray-500 mb-1">Content:</div>
                                          <pre className="bg-gray-100 p-3 rounded text-xs text-gray-900 overflow-x-auto max-h-64">
                                            {JSON.stringify(event.content, null, 2)}
                                          </pre>
                                        </div>
                                        {event.event_metadata && Object.keys(event.event_metadata).length > 0 && (
                                          <div>
                                            <div className="text-xs text-gray-500 mb-1">Metadata:</div>
                                            <pre className="bg-gray-100 p-3 rounded text-xs text-gray-900 overflow-x-auto">
                                              {JSON.stringify(event.event_metadata, null, 2)}
                                            </pre>
                                          </div>
                                        )}
                                      </div>
                                    )}
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
              </div>
            </>
          )}
        </div>

        {/* Stats Panel */}
        <div className="w-64 border-l border-gray-200 bg-white flex flex-col">
          <div className="border-b border-gray-200 px-4 py-4 bg-gray-50">
            <h3 className="font-semibold text-gray-900 text-base">Statistics</h3>
          </div>
          {stats ? (
            <div className="p-4 space-y-4 text-sm">
              <div>
                <h4 className="font-medium text-gray-700 mb-2">By Environment</h4>
                {Object.keys(stats.campaigns_by_environment || {}).length === 0 ? (
                  <div className="text-gray-500">No environment data</div>
                ) : (
                  <div className="space-y-1">
                    {Object.entries(stats.campaigns_by_environment || {}).map(([env, count]) => (
                      <div key={env} className="flex justify-between">
                        <span className="text-gray-600">{env}</span>
                        <span className="font-medium text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Events by Type</h4>
                {Object.keys(stats.events_by_type || {}).length === 0 ? (
                  <div className="text-gray-500">No event data</div>
                ) : (
                  <div className="space-y-1">
                    {Object.entries(stats.events_by_type || {}).map(([type, count]) => (
                      <div key={type} className="flex justify-between">
                        <span className="text-gray-600">{type}</span>
                        <span className="font-medium text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Status</h4>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Active</span>
                    <span className="font-medium text-green-600">{stats.active_campaigns}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Inactive</span>
                    <span className="font-medium text-gray-600">{stats.inactive_campaigns}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Processing</span>
                    <span className="font-medium text-yellow-600">{stats.campaigns_processing}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 text-gray-500 text-sm">Loading stats...</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CampaignInspector;
