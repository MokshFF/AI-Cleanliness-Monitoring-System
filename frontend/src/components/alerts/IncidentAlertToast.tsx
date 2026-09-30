import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, X, ExternalLink, Camera, MapPin, Activity } from 'lucide-react';
import { ActiveAlert } from '../../websocket/alerts';
import { Badge } from '../common/Badge';

interface IncidentAlertToastProps {
  alerts: ActiveAlert[];
  onDismiss: (id: string) => void;
}

export const IncidentAlertToast: React.FC<IncidentAlertToastProps> = ({ alerts, onDismiss }) => {
  const navigate = useNavigate();

  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col space-y-3 max-w-sm w-full pointer-events-none">
      {alerts.map(({ id, incident }) => {
        const isLiquid = incident.waste_type === 'LIQUID';
        const isHighSeverity = incident.severity === 'HIGH' || incident.severity === 'CRITICAL';

        return (
          <div
            key={id}
            className={`pointer-events-auto bg-[#151F32] border rounded-xl shadow-2xl p-4 transition-all transform animate-in slide-in-from-bottom-5 duration-300 ${
              isHighSeverity
                ? 'border-red-500/80 shadow-red-950/40 bg-gradient-to-br from-[#1C1624] to-[#151F32]'
                : 'border-blue-500/50 shadow-blue-950/30'
            }`}
          >
            {/* Header / Severity Banner */}
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#24324D]">
              <div className="flex items-center space-x-2">
                <span className="flex h-2.5 w-2.5 relative">
                  <span
                    className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                      isHighSeverity ? 'bg-red-400' : 'bg-amber-400'
                    }`}
                  ></span>
                  <span
                    className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                      isHighSeverity ? 'bg-red-500' : 'bg-amber-500'
                    }`}
                  ></span>
                </span>
                <span className="text-xs font-bold text-gray-100 tracking-wider uppercase flex items-center gap-1.5">
                  <AlertTriangle className={`w-3.5 h-3.5 ${isHighSeverity ? 'text-red-400' : 'text-amber-400'}`} />
                  New Incident Detected
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <Badge type="severity" value={incident.severity} size="sm" />
                <button
                  onClick={() => onDismiss(id)}
                  title="Dismiss notification"
                  className="text-gray-400 hover:text-gray-200 p-0.5 rounded transition"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Incident Details Body */}
            <div className="space-y-1.5 text-xs text-gray-300">
              <div className="flex items-center justify-between text-gray-400">
                <div className="flex items-center space-x-1">
                  <Camera className="w-3.5 h-3.5 text-gray-500" />
                  <span className="font-mono text-gray-200">{incident.camera_id}</span>
                </div>
                {incident.location && (
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-3.5 h-3.5 text-gray-500" />
                    <span className="truncate max-w-[120px]">{incident.location}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center space-x-1.5">
                  <Badge type="waste" value={incident.waste_type} size="sm" />
                  <span className="font-medium text-gray-200">{incident.category}</span>
                </div>
                <div className="text-[11px] text-gray-400 font-mono flex items-center gap-1">
                  <Activity className="w-3 h-3 text-blue-400" />
                  {isLiquid && incident.affected_area_percentage !== undefined ? (
                    <span>Area: {incident.affected_area_percentage.toFixed(1)}%</span>
                  ) : (
                    <span>Conf: {(incident.confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
              </div>
            </div>

            {/* Action Footer */}
            <div className="mt-3 pt-2 border-t border-[#24324D]/80 flex justify-end">
              <button
                onClick={() => {
                  onDismiss(id);
                  navigate(`/incidents/${incident.incident_id}`);
                }}
                className="w-full py-1.5 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium flex items-center justify-center space-x-1.5 transition shadow"
              >
                <span>View Incident</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
