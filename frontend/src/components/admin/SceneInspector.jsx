import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../../contexts/Auth0Context';

const SceneInspector = () => {
  const [scenes, setScenes] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedScene, setSelectedScene] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const [campaigns, setCampaigns] = useState([]);
  const { getAccessTokenSilently } = useAuth();

  // Fetch scene statistics
  const fetchStats = async () => {
    try {
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/scenes/stats', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  // Fetch scenes list
  const fetchScenes = async () => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      let url = `/api/admin/scenes?include_deleted=${includeDeleted}&limit=100`;
      if (selectedCampaign) {
        url += `&campaign_id=${selectedCampaign}`;
      }
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch scenes');
      const data = await response.json();
      setScenes(data);

      // Extract unique campaigns
      const uniqueCampaigns = [...new Set(data.map(s => s.campaign_id))];
      setCampaigns(uniqueCampaigns);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch scene details
  const fetchSceneDetails = async (sceneId) => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/scenes/${sceneId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch scene details');
      const data = await response.json();
      setSelectedScene(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Soft delete scene
  const deleteScene = async (sceneId) => {
    if (!confirm('Are you sure you want to soft delete this scene?')) return;
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/scenes/${sceneId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to delete scene');
      await fetchScenes();
      await fetchStats();
      if (selectedScene?.scene_id === sceneId) {
        setSelectedScene(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Restore scene
  const restoreScene = async (sceneId) => {
    try {
      setLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/scenes/${sceneId}/restore`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to restore scene');
      await fetchScenes();
      await fetchStats();
      if (selectedScene?.scene_id === sceneId) {
        await fetchSceneDetails(sceneId);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchScenes();
  }, [includeDeleted, selectedCampaign]);

  // Filter scenes by search query
  const filteredScenes = useMemo(() => {
    if (!searchQuery.trim()) return scenes;
    const query = searchQuery.toLowerCase();
    return scenes.filter(scene =>
      scene.scene_id.toLowerCase().includes(query) ||
      scene.title.toLowerCase().includes(query) ||
      scene.scene_type.toLowerCase().includes(query) ||
      (scene.location_id && scene.location_id.toLowerCase().includes(query))
    );
  }, [scenes, searchQuery]);

  // Group scenes by campaign
  const groupedScenes = useMemo(() => {
    return filteredScenes.reduce((acc, scene) => {
      const campaignId = scene.campaign_id;
      if (!acc[campaignId]) {
        acc[campaignId] = [];
      }
      acc[campaignId].push(scene);
      return acc;
    }, {});
  }, [filteredScenes]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">Scene Inspector</h1>
        {stats && (
          <div className="flex gap-6 mt-2 text-sm text-gray-600">
            <span>Total: <strong>{stats.total_scenes}</strong></span>
            <span>Active: <strong className="text-green-600">{stats.active_scenes}</strong></span>
            <span>Deleted: <strong className="text-red-600">{stats.deleted_scenes}</strong></span>
            <span>Campaigns: <strong>{stats.campaigns_with_scenes}</strong></span>
          </div>
        )}
      </div>

      <div className="flex h-[calc(100vh-100px)]">
        {/* Scene List */}
        <div className="w-96 border-r border-gray-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-gray-200 bg-gray-50 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Scenes</h2>
              <button
                onClick={() => { fetchScenes(); fetchStats(); }}
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
                placeholder="Search scenes..."
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
                value={selectedCampaign}
                onChange={(e) => setSelectedCampaign(e.target.value)}
                className="bg-white border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Campaigns</option>
                {campaigns.map(c => (
                  <option key={c} value={c}>{c.substring(0, 8)}...</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={includeDeleted}
                  onChange={(e) => setIncludeDeleted(e.target.checked)}
                  className="rounded border-gray-300"
                />
                Show deleted
              </label>
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
            {loading && scenes.length === 0 ? (
              <p className="text-gray-500 text-sm p-2">Loading scenes...</p>
            ) : filteredScenes.length === 0 ? (
              <p className="text-gray-500 text-sm p-2">No scenes found.</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(groupedScenes).map(([campaignId, campaignScenes]) => (
                  <div key={campaignId} className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                    <div className="px-3 py-2 text-xs font-semibold text-gray-700 bg-gray-50 uppercase tracking-wide">
                      Campaign: {campaignId.substring(0, 8)}...
                    </div>
                    <div className="divide-y divide-gray-100">
                      {campaignScenes.map((scene) => {
                        const isSelected = selectedScene?.scene_id === scene.scene_id;
                        return (
                          <div
                            key={scene.scene_id}
                            onClick={() => fetchSceneDetails(scene.scene_id)}
                            className={`p-3 cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-blue-50 border-l-3 border-l-blue-500'
                                : 'hover:bg-gray-50 border-l-3 border-l-transparent'
                            } ${scene.is_deleted ? 'opacity-60' : ''}`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-gray-900 truncate">
                                  {scene.title}
                                </div>
                                <div className="text-xs text-gray-500 mt-0.5">
                                  {scene.scene_id}
                                </div>
                                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                    scene.scene_type === 'combat' ? 'bg-red-100 text-red-700' :
                                    scene.scene_type === 'exploration' ? 'bg-green-100 text-green-700' :
                                    scene.scene_type === 'social' ? 'bg-purple-100 text-purple-700' :
                                    'bg-gray-100 text-gray-700'
                                  }`}>
                                    {scene.scene_type}
                                  </span>
                                  {scene.in_combat && (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-600 text-white">
                                      IN COMBAT
                                    </span>
                                  )}
                                  {scene.is_deleted && (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-600 text-white">
                                      DELETED
                                    </span>
                                  )}
                                  <span className="text-xs text-gray-500">
                                    {scene.entity_count} entities
                                  </span>
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
        </div>

        {/* Scene Details */}
        <div className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
          {!selectedScene ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-base">Select a scene to view details</p>
            </div>
          ) : (
            <>
              {/* Sticky Header */}
              <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-semibold text-gray-900">{selectedScene.title}</h2>
                      {selectedScene.is_deleted && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          Deleted
                        </span>
                      )}
                      {selectedScene.in_combat && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-600 text-white">
                          In Combat
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 mt-1">
                      {selectedScene.scene_id} | {selectedScene.scene_type}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    {selectedScene.is_deleted ? (
                      <button
                        onClick={() => restoreScene(selectedScene.scene_id)}
                        disabled={loading}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        Restore
                      </button>
                    ) : (
                      <button
                        onClick={() => deleteScene(selectedScene.scene_id)}
                        disabled={loading}
                        className="px-4 py-2 bg-white border border-red-300 hover:bg-red-50 text-red-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        Soft Delete
                      </button>
                    )}
                    <button
                      onClick={() => setSelectedScene(null)}
                      className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Basic Info */}
                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <h3 className="text-base font-medium mb-3 text-gray-700">Basic Information</h3>
                  <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-gray-500">Campaign ID</dt>
                      <dd className="font-mono text-gray-900">{selectedScene.campaign_id}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Location</dt>
                      <dd className="text-gray-900">{selectedScene.location_id || 'N/A'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Completion Status</dt>
                      <dd className="text-gray-900">{selectedScene.completion_status || 'Active'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Duration</dt>
                      <dd className="text-gray-900">{selectedScene.duration_turns} turns</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Created</dt>
                      <dd className="text-gray-900">{formatDate(selectedScene.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Last Updated</dt>
                      <dd className="text-gray-900">{formatDate(selectedScene.last_updated)}</dd>
                    </div>
                  </dl>
                </div>

                {/* Description */}
                <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                  <h3 className="text-base font-medium mb-3 text-gray-700">Description</h3>
                  <p className="text-sm text-gray-900 whitespace-pre-wrap">{selectedScene.description}</p>
                  {selectedScene.location_description && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <h4 className="text-sm font-medium text-gray-500 mb-2">Location Description</h4>
                      <p className="text-sm text-gray-900">{selectedScene.location_description}</p>
                    </div>
                  )}
                </div>

                {/* Objectives */}
                {(selectedScene.objectives?.length > 0 || selectedScene.objectives_completed?.length > 0) && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Objectives</h3>
                    {selectedScene.objectives?.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-gray-500 mb-2">Active</h4>
                        <ul className="list-disc list-inside text-sm text-gray-900 space-y-1">
                          {selectedScene.objectives.map((obj, i) => (
                            <li key={i}>{obj}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selectedScene.objectives_completed?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-green-600 mb-2">Completed</h4>
                        <ul className="list-disc list-inside text-sm text-green-700 space-y-1">
                          {selectedScene.objectives_completed.map((obj, i) => (
                            <li key={i}>{obj}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Turn Order */}
                {selectedScene.turn_order?.length > 0 && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Turn Order</h3>
                    <div className="flex items-center gap-2 flex-wrap">
                      {selectedScene.turn_order.map((entityId, i) => (
                        <span
                          key={i}
                          className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                            i === selectedScene.current_turn_index
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {i + 1}. {selectedScene.entity_display_names?.[entityId] || entityId}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Entities */}
                {selectedScene.entities?.length > 0 && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">
                      Entities ({selectedScene.entities.length})
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Present</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Joined</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {selectedScene.entities.map((entity) => (
                            <tr key={entity.scene_entity_id} className={!entity.is_present ? 'opacity-50' : ''}>
                              <td className="px-3 py-2 font-mono text-gray-900">
                                {selectedScene.entity_display_names?.[entity.entity_id] || entity.entity_id}
                              </td>
                              <td className="px-3 py-2 text-gray-600">{entity.entity_type}</td>
                              <td className="px-3 py-2 text-gray-600">{entity.role || '-'}</td>
                              <td className="px-3 py-2">
                                {entity.is_present ? (
                                  <span className="text-green-600">Yes</span>
                                ) : (
                                  <span className="text-gray-400">No</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-gray-500 text-xs">
                                {formatDate(entity.joined_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Combat Data */}
                {selectedScene.combat_data && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Combat Data</h3>
                    <pre className="bg-gray-50 p-4 rounded-lg text-xs text-gray-900 overflow-x-auto">
                      {JSON.stringify(selectedScene.combat_data, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Outcomes */}
                {selectedScene.outcomes?.length > 0 && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Outcomes</h3>
                    <ul className="list-disc list-inside text-sm text-gray-900 space-y-1">
                      {selectedScene.outcomes.map((outcome, i) => (
                        <li key={i}>{outcome}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Metadata */}
                {selectedScene.scene_metadata && Object.keys(selectedScene.scene_metadata).length > 0 && (
                  <div className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm">
                    <h3 className="text-base font-medium mb-3 text-gray-700">Scene Metadata</h3>
                    <pre className="bg-gray-50 p-4 rounded-lg text-xs text-gray-900 overflow-x-auto">
                      {JSON.stringify(selectedScene.scene_metadata, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Raw JSON (collapsible) */}
                <details className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <summary className="px-5 py-3 cursor-pointer text-base font-medium text-gray-700 hover:bg-gray-50">
                    Raw JSON Data
                  </summary>
                  <div className="px-5 pb-5">
                    <pre className="bg-gray-50 p-4 rounded-lg text-xs text-gray-900 overflow-x-auto max-h-96">
                      {JSON.stringify(selectedScene, null, 2)}
                    </pre>
                  </div>
                </details>
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
                <h4 className="font-medium text-gray-700 mb-2">By Scene Type</h4>
                <div className="space-y-1">
                  {Object.entries(stats.scenes_by_type).map(([type, count]) => (
                    <div key={type} className="flex justify-between">
                      <span className="text-gray-600 capitalize">{type}</span>
                      <span className="font-medium text-gray-900">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">By Status</h4>
                <div className="space-y-1">
                  {Object.entries(stats.scenes_by_status).map(([status, count]) => (
                    <div key={status} className="flex justify-between">
                      <span className="text-gray-600 capitalize">{status}</span>
                      <span className="font-medium text-gray-900">{count}</span>
                    </div>
                  ))}
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

export default SceneInspector;
