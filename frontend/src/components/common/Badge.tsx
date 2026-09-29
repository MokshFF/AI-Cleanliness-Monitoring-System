import React from 'react';
import { IncidentSeverity, IncidentStatus, WasteType } from '../../types/incident';
import { CameraStatus, DetectionMode } from '../../types/camera';

interface BadgeProps {
  type?: 'severity' | 'status' | 'waste' | 'camera_status' | 'detection_mode' | 'role';
  value: string;
  size?: 'sm' | 'md' | 'lg';
}

export const Badge: React.FC<BadgeProps> = ({ type, value, size = 'sm' }) => {
  const sizeClasses = {
    sm: 'px-2.5 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-3.5 py-1.5 text-base',
  }[size];

  let colorClasses = 'bg-gray-800 text-gray-300 border-gray-700';

  if (type === 'severity') {
    switch (value as IncidentSeverity) {
      case 'CRITICAL':
        colorClasses = 'bg-red-950/70 text-red-400 border-red-800';
        break;
      case 'HIGH':
        colorClasses = 'bg-orange-950/70 text-orange-400 border-orange-800';
        break;
      case 'MEDIUM':
        colorClasses = 'bg-amber-950/70 text-amber-400 border-amber-800';
        break;
      case 'LOW':
        colorClasses = 'bg-blue-950/70 text-blue-400 border-blue-800';
        break;
    }
  } else if (type === 'status') {
    switch (value as IncidentStatus) {
      case 'NEW':
        colorClasses = 'bg-sky-950/70 text-sky-400 border-sky-800 animate-pulse';
        break;
      case 'ACKNOWLEDGED':
        colorClasses = 'bg-amber-950/70 text-amber-400 border-amber-800';
        break;
      case 'RESOLVED':
        colorClasses = 'bg-emerald-950/70 text-emerald-400 border-emerald-800';
        break;
      case 'DISMISSED':
        colorClasses = 'bg-gray-800 text-gray-400 border-gray-700';
        break;
    }
  } else if (type === 'waste') {
    switch (value as WasteType) {
      case 'SOLID':
        colorClasses = 'bg-indigo-950/70 text-indigo-400 border-indigo-800';
        break;
      case 'LIQUID':
        colorClasses = 'bg-cyan-950/70 text-cyan-400 border-cyan-800';
        break;
    }
  } else if (type === 'camera_status') {
    switch (value as CameraStatus) {
      case 'ONLINE':
        colorClasses = 'bg-emerald-950/70 text-emerald-400 border-emerald-800';
        break;
      case 'OFFLINE':
        colorClasses = 'bg-rose-950/70 text-rose-400 border-rose-800';
        break;
      case 'CONNECTING':
        colorClasses = 'bg-amber-950/70 text-amber-400 border-amber-800';
        break;
      case 'ERROR':
        colorClasses = 'bg-red-950/70 text-red-400 border-red-800';
        break;
    }
  } else if (type === 'detection_mode') {
    switch (value as DetectionMode) {
      case 'BOTH':
        colorClasses = 'bg-purple-950/70 text-purple-400 border-purple-800';
        break;
      case 'SOLID':
        colorClasses = 'bg-indigo-950/70 text-indigo-400 border-indigo-800';
        break;
      case 'LIQUID':
        colorClasses = 'bg-cyan-950/70 text-cyan-400 border-cyan-800';
        break;
    }
  } else if (type === 'role') {
    switch (value) {
      case 'ADMIN':
        colorClasses = 'bg-violet-950/70 text-violet-400 border-violet-800';
        break;
      case 'OPERATOR':
        colorClasses = 'bg-blue-950/70 text-blue-400 border-blue-800';
        break;
      case 'SUPERVISOR':
        colorClasses = 'bg-teal-950/70 text-teal-400 border-teal-800';
        break;
    }
  }

  return (
    <span
      className={`inline-flex items-center font-medium rounded-md border tracking-wide uppercase ${sizeClasses} ${colorClasses}`}
    >
      {value}
    </span>
  );
};
