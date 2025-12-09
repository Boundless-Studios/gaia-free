import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../../contexts/Auth0Context';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all, pending, active, inactive
  const [selectedUser, setSelectedUser] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showOnboardModal, setShowOnboardModal] = useState(false);
  const [onboardUser, setOnboardUser] = useState(null);
  const [sendWelcomeEmail, setSendWelcomeEmail] = useState(true);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserForm, setNewUserForm] = useState({
    email: '',
    display_name: '',
    is_admin: false,
    is_active: true,
  });
  const [addUserLoading, setAddUserLoading] = useState(false);
  const [addUserError, setAddUserError] = useState(null);
  const { getAccessTokenSilently } = useAuth();

  // Fetch users on mount
  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/allowlist/users', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch users: ${response.status}`);
      }

      const data = await response.json();
      setUsers(data);
    } catch (err) {
      console.error('Error fetching users:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Filter users based on search and status
  const filteredUsers = useMemo(() => {
    return users.filter(user => {
      // Search filter
      const searchLower = searchQuery.toLowerCase();
      const matchesSearch = !searchQuery ||
        user.email.toLowerCase().includes(searchLower) ||
        (user.username && user.username.toLowerCase().includes(searchLower)) ||
        (user.display_name && user.display_name.toLowerCase().includes(searchLower));

      // Status filter
      let matchesStatus = true;
      if (statusFilter === 'pending') {
        // Users awaiting onboarding: completed registration but not active
        matchesStatus = user.registration_status === 'completed' && !user.is_active;
      } else if (statusFilter === 'awaiting_eula') {
        // Users who haven't completed EULA yet
        matchesStatus = user.registration_status === 'pending';
      } else if (statusFilter === 'active') {
        matchesStatus = user.is_active;
      } else if (statusFilter === 'inactive') {
        matchesStatus = !user.is_active;
      }

      return matchesSearch && matchesStatus;
    });
  }, [users, searchQuery, statusFilter]);

  // Get user status for display
  const getUserStatus = (user) => {
    if (user.is_active && user.registration_status === 'completed') {
      return { label: 'Active', color: 'bg-green-100 text-green-700' };
    } else if (user.registration_status === 'completed' && !user.is_active) {
      return { label: 'Awaiting Onboarding', color: 'bg-yellow-100 text-yellow-700' };
    } else if (user.registration_status === 'pending') {
      return { label: 'Awaiting EULA', color: 'bg-gray-100 text-gray-700' };
    } else if (!user.is_active) {
      return { label: 'Disabled', color: 'bg-red-100 text-red-700' };
    }
    return { label: 'Unknown', color: 'bg-gray-100 text-gray-500' };
  };

  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Handle onboarding a user
  const handleOnboard = async () => {
    if (!onboardUser) return;

    try {
      setActionLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/allowlist/users/${onboardUser.user_id}/onboard`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ send_welcome_email: sendWelcomeEmail }),
      });

      if (!response.ok) {
        throw new Error(`Failed to onboard user: ${response.status}`);
      }

      const updatedUser = await response.json();
      setUsers(prev => prev.map(u => u.user_id === updatedUser.user_id ? updatedUser : u));
      setShowOnboardModal(false);
      setOnboardUser(null);
      setSendWelcomeEmail(true);
    } catch (err) {
      console.error('Error onboarding user:', err);
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle enabling a user
  const handleEnable = async (userId) => {
    try {
      setActionLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/allowlist/users/${userId}/enable`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to enable user: ${response.status}`);
      }

      const updatedUser = await response.json();
      setUsers(prev => prev.map(u => u.user_id === updatedUser.user_id ? updatedUser : u));
    } catch (err) {
      console.error('Error enabling user:', err);
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle disabling a user
  const handleDisable = async (userId) => {
    try {
      setActionLoading(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/admin/allowlist/users/${userId}/disable`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to disable user: ${response.status}`);
      }

      const updatedUser = await response.json();
      setUsers(prev => prev.map(u => u.user_id === updatedUser.user_id ? updatedUser : u));
    } catch (err) {
      console.error('Error disabling user:', err);
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle adding a new user
  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      setAddUserLoading(true);
      setAddUserError(null);
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/admin/allowlist/register', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newUserForm),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || `Failed to add user: ${response.status}`);
      }

      const newUser = await response.json();
      setUsers(prev => [...prev, newUser]);
      setShowAddUserModal(false);
      setNewUserForm({
        email: '',
        display_name: '',
        is_admin: false,
        is_active: true,
      });
    } catch (err) {
      console.error('Error adding user:', err);
      setAddUserError(err.message);
    } finally {
      setAddUserLoading(false);
    }
  };

  // Count users by status
  const statusCounts = useMemo(() => {
    return {
      all: users.length,
      pending: users.filter(u => u.registration_status === 'completed' && !u.is_active).length,
      awaiting_eula: users.filter(u => u.registration_status === 'pending').length,
      active: users.filter(u => u.is_active).length,
      inactive: users.filter(u => !u.is_active).length,
    };
  }, [users]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">User Management</h1>
          <button
            onClick={() => setShowAddUserModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add User
          </button>
        </div>
      </div>

      <div className="p-6">
        {/* Filters */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-6">
          <div className="p-4 border-b border-gray-200">
            <div className="flex flex-col sm:flex-row gap-4">
              {/* Search */}
              <div className="flex-1">
                <div className="relative">
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by email, username, or name..."
                    className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 pl-10 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>

              {/* Status Filter */}
              <div className="flex gap-2 flex-wrap">
                {[
                  { key: 'all', label: 'All' },
                  { key: 'pending', label: 'Awaiting Onboarding' },
                  { key: 'awaiting_eula', label: 'Awaiting EULA' },
                  { key: 'active', label: 'Active' },
                  { key: 'inactive', label: 'Inactive' },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => setStatusFilter(key)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                      statusFilter === key
                        ? 'bg-blue-100 text-blue-700 border border-blue-300'
                        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                    <span className="ml-1.5 text-xs opacity-70">({statusCounts[key]})</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="m-4 bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <p className="text-red-800 text-sm">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="text-xs text-red-600 hover:text-red-800 underline"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* User List */}
          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                {searchQuery || statusFilter !== 'all' ? 'No users match your filters.' : 'No users found.'}
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">User</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Registration</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Last Login</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredUsers.map((user) => {
                    const status = getUserStatus(user);
                    const canOnboard = user.registration_status === 'completed' && !user.is_active;
                    return (
                      <tr
                        key={user.user_id}
                        className={`hover:bg-gray-50 transition-colors ${
                          selectedUser?.user_id === user.user_id ? 'bg-blue-50' : ''
                        }`}
                        onClick={() => setSelectedUser(selectedUser?.user_id === user.user_id ? null : user)}
                      >
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-3">
                            {user.avatar_url ? (
                              <img
                                src={user.avatar_url}
                                alt={user.username || user.email}
                                className="w-10 h-10 rounded-full"
                              />
                            ) : (
                              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-medium">
                                {(user.display_name || user.email)[0].toUpperCase()}
                              </div>
                            )}
                            <div>
                              <div className="font-medium text-gray-900">
                                {user.display_name || user.username || user.email.split('@')[0]}
                                {user.is_admin && (
                                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                                    Admin
                                  </span>
                                )}
                              </div>
                              <div className="text-sm text-gray-500">{user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${status.color}`}>
                            {status.label}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <div className="text-sm">
                            {user.eula_accepted_at ? (
                              <div>
                                <div className="text-gray-900">EULA Accepted</div>
                                <div className="text-xs text-gray-500">{formatDate(user.eula_accepted_at)}</div>
                              </div>
                            ) : (
                              <span className="text-gray-500">Not accepted</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-600">
                          {formatDate(user.last_login)}
                        </td>
                        <td className="px-4 py-4 text-right">
                          <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                            {canOnboard && (
                              <button
                                onClick={() => {
                                  setOnboardUser(user);
                                  setShowOnboardModal(true);
                                }}
                                disabled={actionLoading}
                                className="px-3 py-1.5 text-xs font-medium bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors disabled:opacity-50"
                              >
                                Onboard
                              </button>
                            )}
                            {!user.is_active && !canOnboard && (
                              <button
                                onClick={() => handleEnable(user.user_id)}
                                disabled={actionLoading}
                                className="px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50"
                              >
                                Enable
                              </button>
                            )}
                            {user.is_active && (
                              <button
                                onClick={() => handleDisable(user.user_id)}
                                disabled={actionLoading}
                                className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-md transition-colors disabled:opacity-50"
                              >
                                Disable
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* User Detail Panel */}
        {selectedUser && (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">User Details</h2>
              <button
                onClick={() => setSelectedUser(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
                <div>
                  <dt className="text-sm font-medium text-gray-500">User ID</dt>
                  <dd className="mt-1 text-sm text-gray-900 font-mono">{selectedUser.user_id}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Email</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.email}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Username</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.username || '-'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Display Name</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.display_name || '-'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Registration Status</dt>
                  <dd className="mt-1 text-sm text-gray-900 capitalize">{selectedUser.registration_status}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Account Status</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.is_active ? 'Active' : 'Inactive'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">EULA Version</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.eula_version_accepted || '-'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">EULA Accepted</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedUser.eula_accepted_at)}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Registration Completed</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedUser.registration_completed_at)}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Account Created</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedUser.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Last Login</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedUser.last_login)}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Admin</dt>
                  <dd className="mt-1 text-sm text-gray-900">{selectedUser.is_admin ? 'Yes' : 'No'}</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
      </div>

      {/* Onboard Confirmation Modal */}
      {showOnboardModal && onboardUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowOnboardModal(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Onboard User</h3>
                  <p className="text-sm text-gray-600 mt-1">Grant access to the platform</p>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <div className="text-base space-y-1">
                  <p className="text-gray-700">
                    <span className="font-medium">Email:</span> {onboardUser.email}
                  </p>
                  <p className="text-gray-700">
                    <span className="font-medium">Name:</span> {onboardUser.display_name || onboardUser.username || 'N/A'}
                  </p>
                  <p className="text-gray-700">
                    <span className="font-medium">EULA Accepted:</span> {formatDate(onboardUser.eula_accepted_at)}
                  </p>
                </div>
              </div>

              <div className="mb-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={sendWelcomeEmail}
                    onChange={(e) => setSendWelcomeEmail(e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">Send welcome email</span>
                </label>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowOnboardModal(false);
                    setOnboardUser(null);
                  }}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleOnboard}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {actionLoading ? 'Onboarding...' : 'Onboard User'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {showAddUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowAddUserModal(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleAddUser}>
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Add New User</h3>
                <p className="text-sm text-gray-600 mt-1">Pre-register a user to the allowlist</p>
              </div>

              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email<span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={newUserForm.email}
                    onChange={(e) => setNewUserForm(prev => ({ ...prev, email: e.target.value }))}
                    placeholder="user@example.com"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={newUserForm.display_name}
                    onChange={(e) => setNewUserForm(prev => ({ ...prev, display_name: e.target.value }))}
                    placeholder="John Doe"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newUserForm.is_admin}
                      onChange={(e) => setNewUserForm(prev => ({ ...prev, is_admin: e.target.checked }))}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Admin</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newUserForm.is_active}
                      onChange={(e) => setNewUserForm(prev => ({ ...prev, is_active: e.target.checked }))}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Active</span>
                  </label>
                </div>

                {addUserError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {addUserError}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddUserModal(false);
                    setAddUserError(null);
                  }}
                  disabled={addUserLoading}
                  className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addUserLoading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {addUserLoading ? 'Adding...' : 'Add User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
