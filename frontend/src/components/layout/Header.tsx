import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { useWebSocket } from '../../websocket/WebSocketProvider';
import { Shield, LogOut, User as UserIcon, Bell, Volume2, VolumeX } from 'lucide-react';
import { Badge } from '../common/Badge';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const { connectionStatus, activeAlerts, audioEnabled, toggleAudio } = useWebSocket();

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

      {/* User Actions, Live Status & Profile */}
      <div className="flex items-center space-x-3">
        {/* Real-Time Alert Status Indicator */}
        <div className="flex items-center space-x-2 px-2.5 py-1 rounded-full text-xs font-medium border bg-[#151F32] border-[#24324D]">
          <span className="flex h-2 w-2 relative">
            {connectionStatus === 'CONNECTED' && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                connectionStatus === 'CONNECTED'
                  ? 'bg-emerald-500'
                  : connectionStatus === 'RECONNECTING'
                  ? 'bg-amber-500 animate-pulse'
                  : 'bg-rose-500'
              }`}
            ></span>
          </span>
          <span
            className={`text-[11px] font-semibold tracking-wide ${
              connectionStatus === 'CONNECTED'
                ? 'text-emerald-400'
                : connectionStatus === 'RECONNECTING'
                ? 'text-amber-400'
                : 'text-rose-400'
            }`}
          >
            {connectionStatus === 'CONNECTED'
              ? 'LIVE'
              : connectionStatus === 'RECONNECTING'
              ? 'RECONNECTING'
              : 'OFFLINE'}
          </span>
        </div>

        {/* Audio Alert Toggle */}
        <button
          onClick={toggleAudio}
          title={audioEnabled ? 'Audio Alerts: Enabled' : 'Audio Alerts: Muted'}
          className={`p-2 rounded-lg transition border ${
            audioEnabled
              ? 'text-blue-400 bg-blue-950/40 border-blue-900/60 hover:bg-blue-900/50'
              : 'text-gray-500 bg-[#151F32] border-[#24324D] hover:text-gray-300'
          }`}
        >
          {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Notification Bell with Active Alert Count */}
        <div className="relative">
          <div
            title={`Real-Time Alert Stream (${connectionStatus})`}
            className="p-2 text-gray-400 bg-[#151F32] border border-[#24324D] rounded-lg relative"
          >
            <Bell className="w-4 h-4" />
            {activeAlerts.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
                {activeAlerts.length}
              </span>
            )}
          </div>
        </div>

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
