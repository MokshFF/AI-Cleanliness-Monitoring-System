import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Shield, LogOut, User as UserIcon, Bell } from 'lucide-react';
import { Badge } from '../common/Badge';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-[#0E1626] border-b border-[#24324D] px-6 flex items-center justify-between sticky top-0 z-30 shadow-md">
      {/* Brand & Command Center Tag */}
      <div className="flex items-center space-x-3">
        <div className="p-2 bg-blue-600/20 border border-blue-500/40 rounded-lg text-blue-400">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-wider text-gray-100 uppercase flex items-center gap-2">
            National Cleanliness Monitoring System
            <span className="text-[10px] bg-blue-900/60 border border-blue-700 text-blue-300 font-semibold px-2 py-0.5 rounded uppercase">
              Command Center
            </span>
          </h1>
          <p className="text-[11px] text-gray-400">
            Real-time Solid & Liquid Waste Surveillance Platform
          </p>
        </div>
      </div>

      {/* User Actions & Profile */}
      <div className="flex items-center space-x-4">
        {/* Placeholder Notification Bell */}
        <button
          title="Alert Notifications (Phase 8 WebSocket)"
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-[#1E2D48] rounded-lg transition relative"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full"></span>
        </button>

        {/* User Card */}
        {user && (
          <div className="flex items-center space-x-3 pl-3 border-l border-[#24324D]">
            <div className="w-8 h-8 rounded-full bg-blue-900/80 border border-blue-700 flex items-center justify-center text-blue-300 font-bold text-xs">
              <UserIcon className="w-4 h-4" />
            </div>
            <div className="text-left hidden sm:block">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-200">{user.username}</span>
                <Badge type="role" value={user.role} size="sm" />
              </div>
              <span className="text-[10px] text-gray-400 block truncate max-w-[160px]">
                {user.email}
              </span>
            </div>

            {/* Logout Button */}
            <button
              onClick={logout}
              title="Sign Out"
              className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-950/40 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
