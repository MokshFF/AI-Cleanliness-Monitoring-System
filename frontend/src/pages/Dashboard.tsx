import React, { useEffect, useState } from 'react';
import { cameraApi } from '../api/cameras';
import { incidentApi } from '../api/incidents';
import { Camera } from '../types/camera';
import { Incident } from '../types/incident';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { Link } from 'react-router-dom';
import { useWebSocket } from '../websocket/WebSocketProvider';
import {
  Camera as CameraIcon,
  AlertTriangle,
  CheckCircle,
  Activity,
  Layers,
  Droplets,
  Flame,
  Clock,
  ArrowRight,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';

export const Dashboard: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [totalIncidentsCount, setTotalIncidentsCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const { connectionStatus, subscribeIncidentCreated, subscribeIncidentUpdated } = useWebSocket();

  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [camsData, incsData] = await Promise.all([
        cameraApi.getCameras({ limit: 100 }),
        incidentApi.getIncidents({ page: 1, page_size: 50 }),
      ]);
      setCameras(camsData);
      setIncidents(incsData.items);
      setTotalIncidentsCount(incsData.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retrieve operational metrics from backend.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Real-time WebSocket event listeners
  useEffect(() => {
    const unsubCreated = subscribeIncidentCreated((payload) => {
      const newInc = payload.incident;
      setIncidents((prev) => {
        // Prevent duplicate in local state if already present
        if (prev.some((item) => item.incident_id === newInc.incident_id)) {
          return prev;
        }
        return [newInc, ...prev];
      });
      setTotalIncidentsCount((prev) => prev + 1);
    });

    const unsubUpdated = subscribeIncidentUpdated((payload) => {
      setIncidents((prev) =>
        prev.map((item) =>
          item.incident_id === payload.incident_id
            ? { ...item, status: payload.status as any, notes: payload.notes ?? item.notes }
            : item
        )
      );
    });

    return () => {
      unsubCreated();
      unsubUpdated();
    };
  }, [subscribeIncidentCreated, subscribeIncidentUpdated]);

  if (isLoading) {
    return <LoadingSpinner message="Aggregating Command Center Telemetry..." size="lg" />;
  }

  if (error) {
    return <ErrorAlert title="Dashboard Telemetry Error" message={error} onRetry={fetchDashboardData} />;
  }

  // KPI Calculations from authentic API responses
  const totalCameras = cameras.length;
  const onlineCameras = cameras.filter((c) => c.status === 'ONLINE').length;
  const activeIncidents = incidents.filter((i) => i.status === 'NEW' || i.status === 'ACKNOWLEDGED').length;
  
  const todayDateStr = new Date().toISOString().slice(0, 10);
  const todayIncidents = incidents.filter((i) => (i.timestamp || i.created_at || '').slice(0, 10) === todayDateStr).length;
  const resolvedIncidents = incidents.filter((i) => i.status === 'RESOLVED').length;

  const solidIncidents = incidents.filter((i) => i.waste_type === 'SOLID').length;
  const liquidIncidents = incidents.filter((i) => i.waste_type === 'LIQUID').length;
  const highCriticalIncidents = incidents.filter((i) => i.severity === 'HIGH' || i.severity === 'CRITICAL').length;

  // Chart Data: Severity Breakdown
  const severityCounts: Record<string, number> = {
    CRITICAL: 0,
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
  };
  incidents.forEach((i) => {
    if (severityCounts[i.severity] !== undefined) {
      severityCounts[i.severity]++;
    }
  });

  const severityChartData = [
    { name: 'Critical', value: severityCounts.CRITICAL, color: '#EF4444' },
    { name: 'High', value: severityCounts.HIGH, color: '#F97316' },
    { name: 'Medium', value: severityCounts.MEDIUM, color: '#F59E0B' },
    { name: 'Low', value: severityCounts.LOW, color: '#3B82F6' },
  ].filter((item) => item.value > 0);

  // Chart Data: Waste Categories
  const categoryCounts: Record<string, number> = {};
  incidents.forEach((i) => {
    categoryCounts[i.category] = (categoryCounts[i.category] || 0) + 1;
  });
  const categoryChartData = Object.entries(categoryCounts).map(([cat, count]) => ({
    category: cat.replace('_', ' '),
    count,
  }));

  // Camera Status Breakdown
  const cameraStatusCounts = {
    ONLINE: cameras.filter((c) => c.status === 'ONLINE').length,
    OFFLINE: cameras.filter((c) => c.status === 'OFFLINE').length,
    CONNECTING: cameras.filter((c) => c.status === 'CONNECTING').length,
    ERROR: cameras.filter((c) => c.status === 'ERROR').length,
  };

  return (
    <div className="space-y-6">
      {/* Top Bar Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-100">National Surveillance Overview</h2>
          <p className="text-xs text-gray-400 mt-1">
            Real-time cleanliness metrics across active CCTV monitoring nodes
          </p>
        </div>
        <div className="flex items-center space-x-3 self-start">
          <div className="flex items-center space-x-2 text-xs bg-[#151F32] border border-[#24324D] px-3 py-1.5 rounded-lg">
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
              className={`font-semibold tracking-wide ${
                connectionStatus === 'CONNECTED'
                  ? 'text-emerald-400'
                  : connectionStatus === 'RECONNECTING'
                  ? 'text-amber-400'
                  : 'text-rose-400'
              }`}
            >
              Real-Time Alerts: {connectionStatus}
            </span>
          </div>

          <div className="hidden sm:flex items-center space-x-2 text-xs text-gray-400 bg-[#151F32] border border-[#24324D] px-3 py-1.5 rounded-lg">
            <Clock className="w-3.5 h-3.5 text-blue-400" />
            <span>FastAPI REST + WebSocket</span>
          </div>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="flex items-center space-x-4 border-l-4 border-l-blue-500">
          <div className="p-3 bg-blue-600/20 text-blue-400 rounded-xl">
            <CameraIcon className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Total Cameras</p>
            <h3 className="text-2xl font-bold text-gray-100 mt-0.5">{totalCameras}</h3>
            <span className="text-[11px] text-gray-400">Streams registered</span>
          </div>
        </Card>

        <Card className="flex items-center space-x-4 border-l-4 border-l-emerald-500">
          <div className="p-3 bg-emerald-600/20 text-emerald-400 rounded-xl">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Online Cameras</p>
            <h3 className="text-2xl font-bold text-gray-100 mt-0.5">{onlineCameras}</h3>
            <span className="text-[11px] text-emerald-400">
              {totalCameras ? Math.round((onlineCameras / totalCameras) * 100) : 0}% Operational
            </span>
          </div>
        </Card>

        <Card className="flex items-center space-x-4 border-l-4 border-l-amber-500">
          <div className="p-3 bg-amber-600/20 text-amber-400 rounded-xl">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Active Incidents</p>
            <h3 className="text-2xl font-bold text-gray-100 mt-0.5">{activeIncidents}</h3>
            <span className="text-[11px] text-amber-400">Needs intervention</span>
          </div>
        </Card>

        <Card className="flex items-center space-x-4 border-l-4 border-l-purple-500">
          <div className="p-3 bg-purple-600/20 text-purple-400 rounded-xl">
            <Flame className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Today's Incidents</p>
            <h3 className="text-2xl font-bold text-gray-100 mt-0.5">{todayIncidents}</h3>
            <span className="text-[11px] text-gray-400">{totalIncidentsCount} total logged</span>
          </div>
        </Card>
      </div>

      {/* Secondary KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#151F32]/80 border border-[#24324D] rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-400 block font-medium">Solid Waste</span>
            <span className="text-lg font-bold text-indigo-400">{solidIncidents}</span>
          </div>
          <Layers className="w-4 h-4 text-indigo-400" />
        </div>

        <div className="bg-[#151F32]/80 border border-[#24324D] rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-400 block font-medium">Liquid Waste</span>
            <span className="text-lg font-bold text-cyan-400">{liquidIncidents}</span>
          </div>
          <Droplets className="w-4 h-4 text-cyan-400" />
        </div>

        <div className="bg-[#151F32]/80 border border-[#24324D] rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-400 block font-medium">High / Critical</span>
            <span className="text-lg font-bold text-red-400">{highCriticalIncidents}</span>
          </div>
          <Flame className="w-4 h-4 text-red-400" />
        </div>

        <div className="bg-[#151F32]/80 border border-[#24324D] rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-400 block font-medium">Resolved</span>
            <span className="text-lg font-bold text-emerald-400">{resolvedIncidents}</span>
          </div>
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        </div>
      </div>

      {/* Visual Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution */}
        <Card title="Violation Severity Distribution" subtitle="Active and historical severity classification">
          {severityChartData.length > 0 ? (
            <div className="h-60 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {severityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0E1626', borderColor: '#24324D', borderRadius: '8px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-xs text-gray-500 text-center py-16">No incident severity data recorded yet.</p>
          )}
        </Card>

        {/* Violations by Category */}
        <Card title="Detected Waste Categories" subtitle="Distribution across solid and liquid taxonomies">
          {categoryChartData.length > 0 ? (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="category" stroke="#6B7280" fontSize={10} angle={-25} textAnchor="end" />
                  <YAxis stroke="#6B7280" fontSize={11} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0E1626', borderColor: '#24324D', borderRadius: '8px' }}
                  />
                  <Bar dataKey="count" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-xs text-gray-500 text-center py-16">No category frequency data recorded yet.</p>
          )}
        </Card>
      </div>

      {/* Two-Column Lower Section: Camera Health & Recent Incidents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera Health Status */}
        <Card title="Camera Fleet Health" subtitle="Live stream operational status" className="lg:col-span-1">
          <div className="space-y-3 mt-2">
            <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
              <div className="flex items-center space-x-2 text-xs text-gray-300">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span>Online & Streaming</span>
              </div>
              <span className="text-xs font-bold text-gray-100">{cameraStatusCounts.ONLINE}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
              <div className="flex items-center space-x-2 text-xs text-gray-300">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span>Connecting / Ingestion</span>
              </div>
              <span className="text-xs font-bold text-gray-100">{cameraStatusCounts.CONNECTING}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
              <div className="flex items-center space-x-2 text-xs text-gray-300">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span>Offline / Unreachable</span>
              </div>
              <span className="text-xs font-bold text-gray-100">{cameraStatusCounts.OFFLINE}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
              <div className="flex items-center space-x-2 text-xs text-gray-300">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600"></span>
                <span>Stream Error</span>
              </div>
              <span className="text-xs font-bold text-gray-100">{cameraStatusCounts.ERROR}</span>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-[#24324D]">
            <Link
              to="/cameras"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center justify-between font-medium"
            >
              <span>Manage Camera Fleet</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </Card>

        {/* Recent Incidents Feed */}
        <Card
          title="Recent Cleanliness Incidents"
          subtitle="Most recent violations recorded from AI validation engine"
          action={
            <Link to="/incidents" className="text-xs text-blue-400 hover:text-blue-300 font-medium">
              View All
            </Link>
          }
          className="lg:col-span-2"
        >
          {incidents.length > 0 ? (
            <div className="divide-y divide-[#24324D] overflow-hidden">
              {incidents.slice(0, 5).map((inc) => (
                <div key={inc.incident_id} className="py-3 flex items-center justify-between hover:bg-[#1E2D48]/30 px-2 rounded-lg transition">
                  <div className="flex items-center space-x-3">
                    <Badge type="waste" value={inc.waste_type} size="sm" />
                    <div>
                      <div className="flex items-center space-x-2">
                        <Link
                          to={`/incidents/${inc.incident_id}`}
                          className="text-xs font-semibold text-gray-200 hover:text-blue-400"
                        >
                          {inc.category.replace('_', ' ')}
                        </Link>
                        <span className="text-[10px] text-gray-400">({inc.camera_id})</span>
                      </div>
                      <span className="text-[10px] text-gray-400">
                        {new Date(inc.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Badge type="severity" value={inc.severity} size="sm" />
                    <Badge type="status" value={inc.status} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-500 text-center py-8">No incident events recorded yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
};
