import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Camera,
  AlertTriangle,
  MapPin,
  BarChart3,
  Users,
  Settings,
  Cpu,
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { isAdmin } = useAuth();

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
    { to: '/cameras', label: 'Cameras', icon: Camera },
    { to: '/map', label: 'GIS Map (Phase 9)', icon: MapPin, isUpcoming: true },
    { to: '/analytics', label: 'Analytics (Phase 9)', icon: BarChart3, isUpcoming: true },
  ];

  if (isAdmin) {
    navItems.push({ to: '/users', label: 'User Management', icon: Users, isUpcoming: false });
  }

  navItems.push({ to: '/settings', label: 'System Settings', icon: Settings, isUpcoming: false });

  return (
    <aside className="w-64 bg-[#0E1626] border-r border-[#24324D] flex flex-col justify-between flex-shrink-0">
      <div className="py-6 px-4">
        {/* Navigation list */}
        <div className="space-y-1">
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
            Operations Command
          </p>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition ${
                    isActive
                      ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40 shadow-sm'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-[#151F32]'
                  }`
                }
              >
                <div className="flex items-center space-x-3">
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </div>
                {item.isUpcoming && (
                  <span className="text-[9px] bg-[#1E2D48] text-gray-400 px-1.5 py-0.5 rounded border border-[#24324D]">
                    SOON
                  </span>
                )}
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Footer System Telemetry Card */}
      <div className="p-4 border-t border-[#24324D] bg-[#0B1120]/50 m-3 rounded-xl border">
        <div className="flex items-center space-x-2 text-xs text-gray-300 font-semibold mb-1">
          <Cpu className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span>Dual AI Engines Active</span>
        </div>
        <p className="text-[10px] text-gray-400 leading-tight">
          YOLO Detection (Solid) + YOLO Polygon Seg (Liquid)
        </p>
        <div className="mt-2.5 flex items-center justify-between text-[10px] text-gray-400 border-t border-[#24324D]/50 pt-2">
          <span>Backend v0.1.0</span>
          <span className="text-emerald-400 font-mono">REST: ONLINE</span>
        </div>
      </div>
    </aside>
  );
};
