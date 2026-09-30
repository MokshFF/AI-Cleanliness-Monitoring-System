import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Link } from 'react-router-dom';
import { getMapCameras, getMapIncidents } from '../api/map';
import { CameraMapItem, IncidentMapItem } from '../types/analytics';
import { IncidentSeverity, IncidentStatus, WasteType } from '../types/incident';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import {
  MapPin,
  RefreshCw,
  Filter,
  SlidersHorizontal,
} from 'lucide-react';

// Create custom SVG Leaflet div icons
const createCameraDivIcon = (status: string) => {
  let color = '#10B981'; // ONLINE
  if (status === 'OFFLINE') color = '#F43F5E';
  if (status === 'CONNECTING') color = '#F59E0B';
  if (status === 'ERROR') color = '#EF4444';

  const html = `
    <div style="
      background-color: ${color};
      width: 32px;
      height: 32px;
      border-radius: 50%;
      border: 3px solid #0F172A;
      box-shadow: 0 0 10px ${color}88;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ffffff;
      font-size: 14px;
    ">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
        <circle cx="12" cy="13" r="4"></circle>
      </svg>
    </div>
  `;

  return L.divIcon({
    className: 'custom-camera-marker',
    html,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
};

const createIncidentDivIcon = (severity: string, wasteType: string) => {
  let color = '#2563EB'; // LOW
  let pulse = false;
  if (severity === 'CRITICAL') {
    color = '#DC2626';
    pulse = true;
  } else if (severity === 'HIGH') {
    color = '#EA580C';
  } else if (severity === 'MEDIUM') {
    color = '#D97706';
  }

  const glyph = wasteType === 'LIQUID' ? 'L' : 'S';

  const html = `
    <div style="
      position: relative;
      background-color: ${color};
      width: 28px;
      height: 28px;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      border: 2px solid #0F172A;
      box-shadow: 0 0 12px ${color};
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ffffff;
      font-weight: bold;
      font-size: 11px;
    ">
      <span style="transform: rotate(45deg); font-family: monospace;">${glyph}</span>
      ${pulse ? `<div style="
        position: absolute;
        top: -4px; left: -4px; right: -4px; bottom: -4px;
        border-radius: 50% 50% 50% 0;
        border: 2px solid ${color};
        animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
      "></div>` : ''}
    </div>
  `;

  return L.divIcon({
    className: 'custom-incident-marker',
    html,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -28],
  });
};

// Component to dynamically fit bounds of map to visible markers
const AutoFitBounds: React.FC<{
  cameras: CameraMapItem[];
  incidents: IncidentMapItem[];
  showCameras: boolean;
  showIncidents: boolean;
}> = ({ cameras, incidents, showCameras, showIncidents }) => {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];
    if (showCameras) {
      cameras.forEach((c) => points.push([c.latitude, c.longitude]));
    }
    if (showIncidents) {
      incidents.forEach((i) => points.push([i.latitude, i.longitude]));
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
    }
  }, [cameras, incidents, showCameras, showIncidents, map]);

  return null;
};

export const MapPage: React.FC = () => {
  const [cameras, setCameras] = useState<CameraMapItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentMapItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [selectedWasteType, setSelectedWasteType] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');

  // Layer Toggles
  const [showCameras, setShowCameras] = useState<boolean>(true);
  const [showIncidents, setShowIncidents] = useState<boolean>(true);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [cams, incs] = await Promise.all([
        getMapCameras(),
        getMapIncidents({
          camera_id: selectedCameraId || undefined,
          waste_type: (selectedWasteType as WasteType) || undefined,
          severity: (selectedSeverity as IncidentSeverity) || undefined,
          status: (selectedStatus as IncidentStatus) || undefined,
        }),
      ]);
      setCameras(cams);
      setIncidents(incs);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load geospatial data from server.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedCameraId, selectedWasteType, selectedSeverity, selectedStatus]);

  // High/Critical count for summary
  const highSevCount = useMemo(() => {
    return incidents.filter((i) => i.severity === 'HIGH' || i.severity === 'CRITICAL').length;
  }, [incidents]);

  return (
    <div className="space-y-4">
      {/* Top Header & Metrics Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center space-x-2">
            <MapPin className="w-6 h-6 text-blue-500" />
            <span>GIS Cleanliness Surveillance Map</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Real-time geospatial visualization of monitored camera nodes and verified cleanliness violations.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchData()}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-[#1E293B] hover:bg-[#334155] border border-gray-700 rounded-lg text-xs font-medium text-gray-200 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Map</span>
          </button>
        </div>
      </div>

      {/* Metrics Badges Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3 bg-[#111827] border-gray-800">
          <div className="text-xs text-gray-400">Active Camera Nodes</div>
          <div className="text-xl font-bold text-emerald-400 mt-0.5">{cameras.length}</div>
        </Card>
        <Card className="p-3 bg-[#111827] border-gray-800">
          <div className="text-xs text-gray-400">Mapped Incidents</div>
          <div className="text-xl font-bold text-blue-400 mt-0.5">{incidents.length}</div>
        </Card>
        <Card className="p-3 bg-[#111827] border-gray-800">
          <div className="text-xs text-gray-400">High / Critical Alerts</div>
          <div className="text-xl font-bold text-red-400 mt-0.5">{highSevCount}</div>
        </Card>
        <Card className="p-3 bg-[#111827] border-gray-800">
          <div className="text-xs text-gray-400">Layers Monitored</div>
          <div className="text-xl font-bold text-purple-400 mt-0.5">Solid & Liquid</div>
        </Card>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* Filter and Layer Bar */}
      <Card className="p-4 bg-[#111827] border-gray-800">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-gray-300">
              <Filter className="w-3.5 h-3.5 text-blue-400" />
              <span>Filters:</span>
            </div>

            {/* Camera Select */}
            <select
              value={selectedCameraId}
              onChange={(e) => setSelectedCameraId(e.target.value)}
              className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none"
            >
              <option value="">All Cameras</option>
              {cameras.map((c) => (
                <option key={c.camera_id} value={c.camera_id}>
                  {c.name} ({c.camera_id})
                </option>
              ))}
            </select>

            {/* Waste Type */}
            <select
              value={selectedWasteType}
              onChange={(e) => setSelectedWasteType(e.target.value)}
              className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none"
            >
              <option value="">All Waste Types</option>
              <option value="SOLID">Solid Waste</option>
              <option value="LIQUID">Liquid Waste</option>
            </select>

            {/* Severity */}
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>

            {/* Status */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none"
            >
              <option value="">All Statuses</option>
              <option value="NEW">New</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="RESOLVED">Resolved</option>
              <option value="DISMISSED">Dismissed</option>
            </select>

            {(selectedCameraId || selectedWasteType || selectedSeverity || selectedStatus) && (
              <button
                onClick={() => {
                  setSelectedCameraId('');
                  setSelectedWasteType('');
                  setSelectedSeverity('');
                  setSelectedStatus('');
                }}
                className="text-xs text-blue-400 hover:text-blue-300 underline"
              >
                Reset Filters
              </button>
            )}
          </div>

          {/* Layer Visibility Toggles */}
          <div className="flex items-center space-x-4 border-l border-gray-700 pl-4">
            <label className="flex items-center space-x-1.5 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showCameras}
                onChange={(e) => setShowCameras(e.target.checked)}
                className="rounded bg-gray-800 border-gray-700 text-emerald-500 focus:ring-0"
              />
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
                <span>Cameras ({cameras.length})</span>
              </span>
            </label>

            <label className="flex items-center space-x-1.5 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showIncidents}
                onChange={(e) => setShowIncidents(e.target.checked)}
                className="rounded bg-gray-800 border-gray-700 text-red-500 focus:ring-0"
              />
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
                <span>Incidents ({incidents.length})</span>
              </span>
            </label>
          </div>
        </div>
      </Card>

      {/* Main Map Canvas and Legend */}
      <div className="relative rounded-xl overflow-hidden border border-gray-800 shadow-2xl h-[620px] bg-[#0B1120]">
        {isLoading && (
          <div className="absolute inset-0 z-50 bg-[#0F172A]/70 flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        )}

        <MapContainer
          center={[28.6139, 77.209]}
          zoom={12}
          style={{ height: '100%', width: '100%', background: '#0B1120' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <AutoFitBounds
            cameras={cameras}
            incidents={incidents}
            showCameras={showCameras}
            showIncidents={showIncidents}
          />

          {/* Camera Markers */}
          {showCameras &&
            cameras.map((cam) => (
              <Marker
                key={cam.camera_id}
                position={[cam.latitude, cam.longitude]}
                icon={createCameraDivIcon(cam.status)}
              >
                <Popup className="custom-map-popup">
                  <div className="p-2 space-y-2 text-gray-900 min-w-[200px]">
                    <div className="font-bold text-sm flex items-center justify-between border-b pb-1">
                      <span>{cam.name}</span>
                      <span className="text-xs font-mono text-gray-500">{cam.camera_id}</span>
                    </div>

                    <div className="text-xs text-gray-600">
                      <div><b>Location:</b> {cam.location_name}</div>
                      <div><b>Coords:</b> {cam.latitude.toFixed(5)}, {cam.longitude.toFixed(5)}</div>
                    </div>

                    <div className="flex items-center gap-1.5 pt-1">
                      <Badge type="camera_status" value={cam.status} size="sm" />
                      <Badge type="detection_mode" value={cam.detection_mode} size="sm" />
                    </div>

                    <div className="pt-2">
                      <Link
                        to={`/cameras/${cam.camera_id}`}
                        className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
                      >
                        <span>View Camera Feeds &rarr;</span>
                      </Link>
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))}

          {/* Incident Markers */}
          {showIncidents &&
            incidents.map((inc) => (
              <Marker
                key={inc.incident_id}
                position={[inc.latitude, inc.longitude]}
                icon={createIncidentDivIcon(inc.severity, inc.waste_type)}
              >
                <Popup className="custom-map-popup">
                  <div className="p-2 space-y-2 text-gray-900 min-w-[220px]">
                    <div className="font-bold text-sm flex items-center justify-between border-b pb-1">
                      <span className="text-red-700 font-mono text-xs">{inc.incident_id}</span>
                      <span className="text-xs font-medium text-gray-500">
                        {inc.timestamp ? new Date(inc.timestamp).toLocaleTimeString() : ''}
                      </span>
                    </div>

                    <div className="text-xs space-y-0.5 text-gray-600">
                      <div><b>Category:</b> {inc.category.replace(/_/g, ' ')}</div>
                      <div><b>Location:</b> {inc.location_name}</div>
                      <div><b>Camera:</b> {inc.camera_name || inc.camera_id}</div>
                      <div><b>Confidence:</b> {(inc.confidence * 100).toFixed(1)}%</div>
                    </div>

                    <div className="flex flex-wrap gap-1 pt-1">
                      <Badge type="severity" value={inc.severity} size="sm" />
                      <Badge type="waste" value={inc.waste_type} size="sm" />
                      <Badge type="status" value={inc.status} size="sm" />
                    </div>

                    <div className="pt-2">
                      <Link
                        to={`/incidents/${inc.incident_id}`}
                        className="text-xs text-blue-600 hover:text-blue-800 font-bold flex items-center space-x-1"
                      >
                        <span>Inspect Evidence &rarr;</span>
                      </Link>
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))}
        </MapContainer>

        {/* Legend Overlay Panel */}
        <div className="absolute bottom-4 right-4 z-[1000] bg-[#0F172A]/90 backdrop-blur border border-gray-800 rounded-lg p-3 text-xs text-gray-200 shadow-xl space-y-2 max-w-[210px]">
          <div className="font-bold text-gray-300 flex items-center space-x-1 border-b border-gray-700 pb-1">
            <SlidersHorizontal className="w-3.5 h-3.5 text-blue-400" />
            <span>Map Legend</span>
          </div>

          <div>
            <div className="text-[10px] uppercase font-semibold text-gray-400 mb-1">Camera Nodes</div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span className="text-gray-300">Online</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span className="text-gray-300">Offline / Error</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase font-semibold text-gray-400 mb-1">Incidents (Severity)</div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse"></span>
                <span className="text-gray-300">Critical</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
                <span className="text-gray-300">High</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span className="text-gray-300">Medium</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                <span className="text-gray-300">Low</span>
              </div>
            </div>
            <div className="text-[9px] text-gray-400 mt-1 italic">
              Marker 'S' = Solid, 'L' = Liquid
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapPage;
