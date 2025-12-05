import React, { useState, useEffect } from 'react';
import { API_CONFIG } from '../../config/api.js';

/**
 * Audio Debug Page - Admin tool for diagnosing audio playback issues
 *
 * Features:
 * - List recent audio requests in a table
 * - Diagnose specific requests for sequence issues
 * - View chunk details
 */
export const AudioDebugPage = () => {
  // Recent requests state
  const [recentRequests, setRecentRequests] = useState([]);
  const [recentRequestsLoading, setRecentRequestsLoading] = useState(false);
  const [campaignFilter, setCampaignFilter] = useState('');

  // Diagnosis state
  const [selectedRequestId, setSelectedRequestId] = useState(null);
  const [diagnosisResult, setDiagnosisResult] = useState(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState(null);

  // Load recent requests on mount
  useEffect(() => {
    fetchRecentRequests();
  }, []);

  const fetchRecentRequests = async () => {
    setRecentRequestsLoading(true);

    try {
      const backendUrl = API_CONFIG.BACKEND_URL || '';
      let url = `${backendUrl}/api/debug/recent-audio-requests?limit=50`;
      if (campaignFilter.trim()) {
        url += `&campaign_id=${encodeURIComponent(campaignFilter.trim())}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      setRecentRequests(result.requests || []);
    } catch (err) {
      console.error('Failed to fetch recent requests:', err);
    } finally {
      setRecentRequestsLoading(false);
    }
  };

  const handleDiagnose = async (requestId) => {
    setSelectedRequestId(requestId);
    setDiagnosisLoading(true);
    setDiagnosisError(null);
    setDiagnosisResult(null);

    try {
      const backendUrl = API_CONFIG.BACKEND_URL || '';
      const response = await fetch(`${backendUrl}/api/debug/diagnose-audio/${requestId}`);
      const result = await response.json();

      if (result.error) {
        setDiagnosisError(result.error);
      } else {
        setDiagnosisResult(result);
      }
    } catch (err) {
      setDiagnosisError(err.message);
    } finally {
      setDiagnosisLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: 'bg-green-100 text-green-800',
      generated: 'bg-blue-100 text-blue-800',
      generating: 'bg-yellow-100 text-yellow-800',
      pending: 'bg-gray-100 text-gray-800',
      failed: 'bg-red-100 text-red-800',
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Audio Debug</h1>
        <p className="text-sm text-gray-500 mt-1">Diagnose audio playback issues and view request history</p>
      </div>

      <div className="p-6">
        {/* Filter and Refresh */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Filter by Campaign ID
              </label>
              <input
                type="text"
                value={campaignFilter}
                onChange={(e) => setCampaignFilter(e.target.value)}
                placeholder="Leave empty for all campaigns"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={fetchRecentRequests}
              disabled={recentRequestsLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium disabled:opacity-50"
            >
              {recentRequestsLoading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Requests Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Recent Requests</h2>
              <p className="text-sm text-gray-500">{recentRequests.length} requests</p>
            </div>

            <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Chunks</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Text</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {recentRequests.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-8 text-center text-gray-500">
                        {recentRequestsLoading ? 'Loading...' : 'No requests found'}
                      </td>
                    </tr>
                  ) : (
                    recentRequests.map((req) => (
                      <tr
                        key={req.request_id}
                        className={`hover:bg-gray-50 ${selectedRequestId === req.request_id ? 'bg-blue-50' : ''} ${req.has_sequence_issues ? 'border-l-4 border-l-red-400' : ''}`}
                      >
                        <td className="px-3 py-2">
                          <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(req.status)}`}>
                            {req.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-sm">
                          <span className={req.has_sequence_issues ? 'text-red-600 font-medium' : 'text-gray-900'}>
                            {req.actual_chunks}/{req.total_chunks || '?'}
                          </span>
                          {req.has_sequence_issues && (
                            <span className="ml-1 text-red-500" title="Sequence issues detected">⚠️</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-600 max-w-[200px] truncate" title={req.text}>
                          {req.text || '(no text)'}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                          {formatDate(req.requested_at)}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleDiagnose(req.request_id)}
                              className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium"
                              title="Diagnose this request"
                            >
                              Diagnose
                            </button>
                            <button
                              onClick={() => copyToClipboard(req.request_id)}
                              className="px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded text-xs"
                              title="Copy request ID"
                            >
                              Copy
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Diagnosis Panel */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Diagnosis</h2>
              <p className="text-sm text-gray-500">
                {selectedRequestId ? `Request: ${selectedRequestId.slice(0, 8)}...` : 'Select a request to diagnose'}
              </p>
            </div>

            <div className="p-4 max-h-[600px] overflow-y-auto">
              {diagnosisLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="text-gray-500">Loading diagnosis...</div>
                </div>
              ) : diagnosisError ? (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <p className="text-red-800">{diagnosisError}</p>
                </div>
              ) : diagnosisResult ? (
                <div className="space-y-6">
                  {/* Request Info */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Request Info</h3>
                    <div className="bg-gray-50 rounded-md p-3 text-sm">
                      <div className="grid grid-cols-2 gap-2">
                        <div><span className="text-gray-500">Status:</span> <span className={`font-medium ${diagnosisResult.request_info?.status === 'failed' ? 'text-red-600' : 'text-gray-900'}`}>{diagnosisResult.request_info?.status}</span></div>
                        <div><span className="text-gray-500">Campaign:</span> <span className="font-mono text-xs">{diagnosisResult.request_info?.campaign_id}</span></div>
                        <div><span className="text-gray-500">Total Chunks:</span> {diagnosisResult.request_info?.total_chunks}</div>
                        <div><span className="text-gray-500">Group:</span> {diagnosisResult.request_info?.playback_group}</div>
                      </div>
                      {diagnosisResult.request_info?.text && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          <span className="text-gray-500">Text:</span>
                          <p className="mt-1 text-gray-900">{diagnosisResult.request_info.text}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Sequence Analysis */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Sequence Analysis</h3>
                    <div className={`rounded-md p-3 text-sm ${diagnosisResult.sequence_analysis?.missing_sequences?.length > 0 || diagnosisResult.sequence_analysis?.extra_sequences?.length > 0 ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <div><span className="text-gray-500">Expected:</span> {diagnosisResult.sequence_analysis?.expected_count} chunks</div>
                        <div><span className="text-gray-500">Actual:</span> {diagnosisResult.sequence_analysis?.actual_count} chunks</div>
                      </div>
                      <div className="space-y-1 font-mono text-xs">
                        <div><span className="text-gray-500">Expected:</span> [{diagnosisResult.sequence_analysis?.expected_sequences?.join(', ')}]</div>
                        <div><span className="text-gray-500">Actual:</span> [{diagnosisResult.sequence_analysis?.actual_sequences?.join(', ')}]</div>
                        {diagnosisResult.sequence_analysis?.missing_sequences?.length > 0 && (
                          <div className="text-red-600 font-medium">Missing: [{diagnosisResult.sequence_analysis.missing_sequences.join(', ')}]</div>
                        )}
                        {diagnosisResult.sequence_analysis?.extra_sequences?.length > 0 && (
                          <div className="text-orange-600 font-medium">Extra: [{diagnosisResult.sequence_analysis.extra_sequences.join(', ')}]</div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Recommendations</h3>
                    <ul className="space-y-2">
                      {diagnosisResult.recommendations?.map((rec, idx) => (
                        <li key={idx} className="bg-blue-50 border-l-4 border-blue-400 p-3 text-sm text-blue-900">
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Chunks Table */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Chunks ({diagnosisResult.chunks?.length || 0})</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 text-xs">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-2 py-1 text-left font-medium text-gray-500">Seq</th>
                            <th className="px-2 py-1 text-left font-medium text-gray-500">Status</th>
                            <th className="px-2 py-1 text-left font-medium text-gray-500">Artifact ID</th>
                            <th className="px-2 py-1 text-left font-medium text-gray-500">Created</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {diagnosisResult.chunks?.map((chunk) => (
                            <tr key={chunk.chunk_id} className="hover:bg-gray-50">
                              <td className="px-2 py-1 font-mono">{chunk.sequence_number}</td>
                              <td className="px-2 py-1">
                                <span className={`inline-flex px-1.5 py-0.5 rounded-full text-xs ${getStatusBadge(chunk.status)}`}>
                                  {chunk.status}
                                </span>
                              </td>
                              <td className="px-2 py-1 font-mono text-gray-600 truncate max-w-[150px]" title={chunk.artifact_id}>
                                {chunk.artifact_id?.slice(0, 12)}...
                              </td>
                              <td className="px-2 py-1 text-gray-500 whitespace-nowrap">
                                {chunk.created_at ? new Date(chunk.created_at).toLocaleTimeString() : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center py-12 text-gray-500">
                  <div className="text-center">
                    <p className="text-lg mb-2">👆</p>
                    <p>Click "Diagnose" on a request to view details</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AudioDebugPage;
