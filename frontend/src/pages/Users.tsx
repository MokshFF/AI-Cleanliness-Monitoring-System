import React, { useEffect, useState } from 'react';
import { userApi } from '../api/users';
import { User, UserRole, UserCreateInput } from '../types/auth';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { Modal } from '../components/common/Modal';
import {
  UserPlus,
  CheckCircle,
  XCircle,
} from 'lucide-react';

export const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Create User Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [newUser, setNewUser] = useState<UserCreateInput>({
    username: '',
    email: '',
    full_name: '',
    role: 'OPERATOR',
    password: '',
  });
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await userApi.getUsers({ limit: 100 });
      setUsers(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retrieve user accounts from MongoDB.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUser.username?.trim() || !newUser.email.trim() || !newUser.password) {
      setFormError('Username, email, and password are required.');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);
    try {
      await userApi.createUser(newUser);
      setIsCreateModalOpen(false);
      setNewUser({
        username: '',
        email: '',
        full_name: '',
        role: 'OPERATOR',
        password: '',
      });
      fetchUsers();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to register new user.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleUserActive = async (user: User) => {
    try {
      await userApi.updateUser(user.id, { is_active: !user.is_active });
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user active state.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-100">User Administration</h2>
          <p className="text-xs text-gray-400 mt-1">
            Role-Based Access Control and command personnel accounts ({users.length} registered)
          </p>
        </div>

        <button
          onClick={() => {
            setFormError(null);
            setIsCreateModalOpen(true);
          }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow"
        >
          <UserPlus className="w-4 h-4" />
          <span>Register User</span>
        </button>
      </div>

      {/* Error state */}
      {error && <ErrorAlert title="User Management Error" message={error} onRetry={fetchUsers} />}

      {/* Users Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="p-12">
            <LoadingSpinner message="Querying user directory from MongoDB..." />
          </div>
        ) : users.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-[#0E1626] border-b border-[#24324D] text-gray-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">User</th>
                  <th className="py-3 px-4 font-semibold">Email</th>
                  <th className="py-3 px-4 font-semibold">Role</th>
                  <th className="py-3 px-4 font-semibold">Active</th>
                  <th className="py-3 px-4 font-semibold">Last Login</th>
                  <th className="py-3 px-4 font-semibold">Registered</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#24324D]">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-[#1E2D48]/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-gray-100">{u.username}</div>
                      <div className="text-[10px] text-gray-400">{u.full_name || '—'}</div>
                    </td>
                    <td className="py-3 px-4 text-gray-300 font-mono text-[11px]">{u.email}</td>
                    <td className="py-3 px-4">
                      <Badge type="role" value={u.role} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      {u.is_active ? (
                        <span className="inline-flex items-center text-emerald-400 text-xs">
                          <CheckCircle className="w-3.5 h-3.5 mr-1" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-gray-500 text-xs">
                          <XCircle className="w-3.5 h-3.5 mr-1" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-gray-400">
                      {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                    </td>
                    <td className="py-3 px-4 text-gray-400 whitespace-nowrap">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleToggleUserActive(u)}
                        className={`px-2.5 py-1 rounded text-xs font-medium transition border ${
                          u.is_active
                            ? 'bg-amber-950/40 text-amber-300 border-amber-800 hover:bg-amber-900'
                            : 'bg-emerald-950/40 text-emerald-300 border-emerald-800 hover:bg-emerald-900'
                        }`}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No Users Registered"
            description="No users found in database directory."
          />
        )}
      </Card>

      {/* User Registration Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Register New Command Personnel"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-lg text-xs text-red-200">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Username *
              </label>
              <input
                type="text"
                required
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                placeholder="e.g. operator_zone2"
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Full Name
              </label>
              <input
                type="text"
                value={newUser.full_name}
                onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                placeholder="e.g. Rajesh Sharma"
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">
              Email Address *
            </label>
            <input
              type="email"
              required
              value={newUser.email}
              onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              placeholder="operator@cleanliness.gov.in"
              className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                User Role *
              </label>
              <select
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value as UserRole })}
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="OPERATOR">OPERATOR (Incident Triage)</option>
                <option value="ADMIN">ADMIN (Full System Privileges)</option>
                <option value="SUPERVISOR">SUPERVISOR (Zone Oversight)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Initial Password *
              </label>
              <input
                type="password"
                required
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                placeholder="••••••••••••"
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-[#24324D]">
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
              className="px-3.5 py-1.5 bg-[#1E2D48] text-gray-300 hover:bg-[#24324D] rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold"
            >
              <span>{isSubmitting ? 'Creating...' : 'Create Account'}</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
