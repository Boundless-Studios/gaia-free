import React from 'react';
import { Link } from 'react-router-dom';

const AdminIndex = () => {
  const apiEndpoints = [
    {
      method: 'GET',
      path: '/api/campaigns/{id}/state',
      description: 'Get campaign state (current turn, active turn, version)',
    },
    {
      method: 'GET',
      path: '/api/campaigns/{id}/turn_events',
      description: 'Get turn events for chat history (supports limit, offset, turn_number filters)',
    },
  ];

  const adminPages = [
    {
      path: '/admin/users',
      title: 'User Management',
      description: 'Manage registered users, allowlist, and onboarding',
      icon: 'users',
    },
    {
      path: '/admin/campaigns',
      title: 'Campaign Inspector',
      description: 'View campaigns, turn state, and event history',
      icon: 'database',
    },
    {
      path: '/admin/scenes',
      title: 'Scene Inspector',
      description: 'Inspect scene data, entities, and combat state',
      icon: 'layers',
    },
    {
      path: '/admin/prompts',
      title: 'Prompt Manager',
      description: 'Manage and version AI prompts',
      icon: 'edit',
    },
    {
      path: '/admin/debug-audio',
      title: 'Audio Debug',
      description: 'Debug audio streaming and TTS',
      icon: 'volume',
    },
  ];

  const getIcon = (icon) => {
    switch (icon) {
      case 'users':
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        );
      case 'database':
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
        );
      case 'layers':
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        );
      case 'edit':
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        );
      case 'volume':
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          </svg>
        );
      default:
        return (
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-6 py-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Manage and inspect system data</p>
      </div>

      <div className="max-w-4xl mx-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {adminPages.map((page) => (
            <Link
              key={page.path}
              to={page.path}
              className="bg-white border border-gray-200 rounded-lg p-5 hover:border-blue-300 hover:shadow-md transition-all group"
            >
              <div className="flex items-start gap-4">
                <div className="text-gray-400 group-hover:text-blue-500 transition-colors">
                  {getIcon(page.icon)}
                </div>
                <div>
                  <h2 className="text-lg font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
                    {page.title}
                  </h2>
                  <p className="mt-1 text-sm text-gray-500">{page.description}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Campaign API Endpoints Reference */}
        <div className="mt-8 bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Campaign State API Endpoints</h2>
          <p className="text-sm text-gray-500 mb-4">
            Non-admin endpoints for campaign turn persistence (used by frontend for state sync):
          </p>
          <div className="space-y-3">
            {apiEndpoints.map((endpoint, idx) => (
              <div key={idx} className="flex items-start gap-3 text-sm">
                <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-xs font-medium ${
                  endpoint.method === 'GET' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                }`}>
                  {endpoint.method}
                </span>
                <div>
                  <code className="text-gray-800 font-mono text-xs">{endpoint.path}</code>
                  <p className="text-gray-500 mt-0.5">{endpoint.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminIndex;
