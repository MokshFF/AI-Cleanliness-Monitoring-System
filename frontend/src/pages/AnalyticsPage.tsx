import React, { useEffect, useState, useMemo } from 'react';
import { getAnalyticsSummary } from '../api/analytics';
import { downloadCsvReport, downloadPdfReport } from '../api/reports';
import { cameraApi } from '../api/cameras';
import { Camera } from '../types/camera';
import { AnalyticsSummaryResponse, AnalyticsFilterParams } from '../types/analytics';
import { IncidentSeverity, IncidentStatus, WasteType } from '../types/incident';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import {
  BarChart3,
  Calendar,
  Filter,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  PieChart as PieIcon,
  Layers,
  MapPin,
  RefreshCw,
  FileText,
  FileSpreadsheet,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

type DatePreset = 'today' | '7days' | '30days' | '90days' | 'custom' | 'all';

export const AnalyticsPage: React.FC = () => {
  const [data, setData] = useState<AnalyticsSummaryResponse | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isExportingCsv, setIsExportingCsv] = useState<boolean>(false);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);

  // Filter states
  const [datePreset, setDatePreset] = useState<DatePreset>('30days');
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [selectedWasteType, setSelectedWasteType] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');

  // Initial load: fetch cameras list for dropdown
  useEffect(() => {
    cameraApi.getCameras({ limit: 200 }).then(setCameras).catch(() => {});
  }, []);

  // Compute ISO start/end strings based on preset
  const computedDateRange = useMemo(() => {
    const now = new Date();
    let start: Date | null = null;
    let end: Date | null = now;

    if (datePreset === 'today') {
      start = new Date();
      start.setHours(0, 0, 0, 0);
    } else if (datePreset === '7days') {
      start = new Date();
      start.setDate(now.getDate() - 7);
    } else if (datePreset === '30days') {
      start = new Date();
      start.setDate(now.getDate() - 30);
    } else if (datePreset === '90days') {
      start = new Date();
      start.setDate(now.getDate() - 90);
    } else if (datePreset === 'custom') {
      return {
        startDate: customStartDate ? new Date(customStartDate).toISOString() : undefined,
        endDate: customEndDate ? new Date(customEndDate).toISOString() : undefined,
      };
    } else if (datePreset === 'all') {
      return { startDate: undefined, endDate: undefined };
    }

    return {
      startDate: start ? start.toISOString() : undefined,
      endDate: end ? end.toISOString() : undefined,
    };
  }, [datePreset, customStartDate, customEndDate]);

  const activeFilters = useMemo<AnalyticsFilterParams>(() => {
    return {
      start_date: computedDateRange.startDate,
      end_date: computedDateRange.endDate,
      camera_id: selectedCameraId || undefined,
      waste_type: (selectedWasteType as WasteType) || undefined,
      severity: (selectedSeverity as IncidentSeverity) || undefined,
      status: (selectedStatus as IncidentStatus) || undefined,
    };
  }, [computedDateRange, selectedCameraId, selectedWasteType, selectedSeverity, selectedStatus]);

  const fetchAnalytics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const summary = await getAnalyticsSummary(activeFilters);
      setData(summary);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to calculate analytics aggregations.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [activeFilters]);

  // Export Handlers
  const handleExportCsv = async () => {
    try {
      setIsExportingCsv(true);
      await downloadCsvReport(activeFilters);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'CSV Export failed');
    } finally {
      setIsExportingCsv(false);
    }
  };

  const handleExportPdf = async () => {
    try {
      setIsExportingPdf(true);
      await downloadPdfReport(activeFilters);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'PDF Export failed');
    } finally {
      setIsExportingPdf(false);
    }
  };

  // Severity Chart Data
  const severityChartData = useMemo(() => {
    if (!data) return [];
    const colors: Record<string, string> = {
      CRITICAL: '#DC2626',
      HIGH: '#EA580C',
      MEDIUM: '#D97706',
      LOW: '#2563EB',
    };
    return Object.entries(data.severity_breakdown).map(([name, value]) => ({
      name,
      value,
      color: colors[name] || '#64748B',
    }));
  }, [data]);


  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center space-x-2">
            <BarChart3 className="w-6 h-6 text-blue-500" />
            <span>Longitudinal Analytics & Municipal Reporting</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Historical incident metrics, violation trend analysis, and official municipal compliance reports.
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleExportCsv}
            disabled={isExportingCsv || isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-[#1E293B] hover:bg-[#334155] border border-gray-700 rounded-lg text-xs font-medium text-gray-200 transition disabled:opacity-50"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
            <span>{isExportingCsv ? 'Exporting...' : 'Export CSV'}</span>
          </button>

          <button
            onClick={handleExportPdf}
            disabled={isExportingPdf || isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-semibold text-white transition shadow-sm disabled:opacity-50"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>{isExportingPdf ? 'Generating PDF...' : 'Official PDF Report'}</span>
          </button>

          <button
            onClick={fetchAnalytics}
            disabled={isLoading}
            className="p-2 bg-[#1E293B] hover:bg-[#334155] border border-gray-700 rounded-lg text-gray-400 hover:text-gray-200 transition"
            title="Refresh Analytics"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Date Presets and Filters Bar */}
      <Card className="p-4 bg-[#111827] border-gray-800 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Preset Buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            <div className="text-xs font-semibold text-gray-400 mr-1 flex items-center space-x-1">
              <Calendar className="w-3.5 h-3.5" />
              <span>Timeframe:</span>
            </div>
            {(['today', '7days', '30days', '90days', 'all', 'custom'] as DatePreset[]).map((p) => {
              const labels: Record<DatePreset, string> = {
                today: 'Today',
                '7days': 'Last 7 Days',
                '30days': 'Last 30 Days',
                '90days': 'Last 90 Days',
                all: 'All Time',
                custom: 'Custom Range',
              };
              return (
                <button
                  key={p}
                  onClick={() => setDatePreset(p)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    datePreset === p
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-[#1E293B] text-gray-300 hover:bg-[#334155]'
                  }`}
                >
                  {labels[p]}
                </button>
              );
            })}
          </div>

          {/* Custom Date Inputs if preset is custom */}
          {datePreset === 'custom' && (
            <div className="flex items-center space-x-2 text-xs">
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="bg-[#1E293B] border border-gray-700 rounded-lg px-2.5 py-1 text-gray-200"
              />
              <span className="text-gray-400">to</span>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="bg-[#1E293B] border border-gray-700 rounded-lg px-2.5 py-1 text-gray-200"
              />
            </div>
          )}
        </div>

        {/* Secondary Filter Dropdowns */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-800">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-gray-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Segment:</span>
          </div>

          <select
            value={selectedCameraId}
            onChange={(e) => setSelectedCameraId(e.target.value)}
            className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 outline-none"
          >
            <option value="">All Cameras</option>
            {cameras.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.name} ({c.camera_id})
              </option>
            ))}
          </select>

          <select
            value={selectedWasteType}
            onChange={(e) => setSelectedWasteType(e.target.value)}
            className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 outline-none"
          >
            <option value="">All Waste Types</option>
            <option value="SOLID">Solid Waste</option>
            <option value="LIQUID">Liquid Waste</option>
          </select>

          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 outline-none"
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1.5 outline-none"
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
              Clear Filters
            </button>
          )}
        </div>
      </Card>

      {error && <ErrorAlert message={error} />}

      {/* KPI Cards Row */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card className="p-4 bg-[#111827] border-gray-800">
            <div className="flex items-center justify-between text-gray-400 text-xs">
              <span>Total Violations</span>
              <AlertTriangle className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-gray-100 mt-1">{data.total_incidents}</div>
            <div className="text-[11px] text-gray-400 mt-1">Across monitored cameras</div>
          </Card>

          <Card className="p-4 bg-[#111827] border-gray-800">
            <div className="flex items-center justify-between text-gray-400 text-xs">
              <span>Active Violations</span>
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
            </div>
            <div className="text-2xl font-bold text-red-400 mt-1">{data.active_incidents}</div>
            <div className="text-[11px] text-gray-400 mt-1">New & Acknowledged</div>
          </Card>

          <Card className="p-4 bg-[#111827] border-gray-800">
            <div className="flex items-center justify-between text-gray-400 text-xs">
              <span>Resolved Incidents</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-1">{data.resolved_incidents}</div>
            <div className="text-[11px] text-gray-400 mt-1">Cleaned & closed</div>
          </Card>

          <Card className="p-4 bg-[#111827] border-gray-800">
            <div className="flex items-center justify-between text-gray-400 text-xs">
              <span>Resolution Rate</span>
              <TrendingUp className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold text-blue-400 mt-1">{data.resolution_rate}%</div>
            <div className="text-[11px] text-gray-400 mt-1">Target: &gt;85% compliance</div>
          </Card>

          <Card className="p-4 bg-[#111827] border-gray-800 col-span-2 lg:col-span-1">
            <div className="flex items-center justify-between text-gray-400 text-xs">
              <span>Waste Split</span>
              <Layers className="w-4 h-4 text-purple-400" />
            </div>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-base font-bold text-indigo-400">
                S: {data.waste_type_breakdown.SOLID || 0}
              </span>
              <span className="text-gray-500">|</span>
              <span className="text-base font-bold text-cyan-400">
                L: {data.waste_type_breakdown.LIQUID || 0}
              </span>
            </div>
            <div className="text-[11px] text-gray-400 mt-1">Solid vs Liquid detections</div>
          </Card>
        </div>
      )}

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Area Chart (2 Columns) */}
        <Card className="lg:col-span-2 p-5 bg-[#111827] border-gray-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-gray-100 flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                <span>Incident Frequency Trend</span>
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Daily confirmed incident volume over the selected observation window.
              </p>
            </div>
          </div>

          <div className="h-[280px] w-full">
            {data && data.trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563EB" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                  <XAxis dataKey="date" stroke="#6B7280" fontSize={11} tickLine={false} />
                  <YAxis stroke="#6B7280" fontSize={11} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0F172A', borderColor: '#374151', borderRadius: '8px' }}
                    labelStyle={{ color: '#F3F4F6', fontWeight: 'bold' }}
                    itemStyle={{ color: '#60A5FA' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="Incidents"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorCount)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No longitudinal trend points recorded in this timeframe.
              </div>
            )}
          </div>
        </Card>

        {/* Severity Breakdown Donut (1 Column) */}
        <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
          <div>
            <h2 className="text-base font-bold text-gray-100 flex items-center space-x-2">
              <PieIcon className="w-4 h-4 text-purple-400" />
              <span>Severity Breakdown</span>
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">Distribution across severity levels.</p>
          </div>

          <div className="h-[210px] w-full">
            {data && data.total_incidents > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {severityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0F172A', borderColor: '#374151', borderRadius: '8px' }}
                    itemStyle={{ color: '#F3F4F6' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No incidents recorded.
              </div>
            )}
          </div>

          {/* Custom Severity Legend */}
          <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-gray-800">
            {severityChartData.map((s) => (
              <div key={s.name} className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }}></span>
                <span className="text-gray-300">
                  {s.name}: <b>{s.value}</b>
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Secondary Charts: Category Breakdown and Camera Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Waste Category Breakdown */}
        <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
          <div>
            <h2 className="text-base font-bold text-gray-100 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Violation Classes / Categories</span>
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">Top solid and liquid categories detected.</p>
          </div>

          <div className="h-[260px] w-full">
            {data && data.category_breakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.category_breakdown.slice(0, 7)}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" horizontal={false} />
                  <XAxis type="number" stroke="#6B7280" fontSize={11} tickLine={false} />
                  <YAxis
                    dataKey="category"
                    type="category"
                    stroke="#9CA3AF"
                    fontSize={11}
                    tickLine={false}
                    tickFormatter={(val) => val.replace(/_/g, ' ')}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0F172A', borderColor: '#374151', borderRadius: '8px' }}
                    labelStyle={{ color: '#F3F4F6' }}
                  />
                  <Bar dataKey="count" name="Violations" fill="#3B82F6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No category data available.
              </div>
            )}
          </div>
        </Card>

        {/* Top Cameras Hotspots */}
        <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
          <div>
            <h2 className="text-base font-bold text-gray-100 flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-emerald-400" />
              <span>Top Camera Hotspots</span>
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">Surveillance nodes logging highest incident volumes.</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#1E293B]/70 text-gray-400 border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3">Camera Node</th>
                  <th className="py-2.5 px-3 text-center">Total</th>
                  <th className="py-2.5 px-3 text-center">Active</th>
                  <th className="py-2.5 px-3 text-center">High / Critical</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {data && data.camera_breakdown.length > 0 ? (
                  data.camera_breakdown.slice(0, 6).map((cam) => (
                    <tr key={cam.camera_id} className="hover:bg-gray-800/30">
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-gray-200">{cam.camera_name}</div>
                        <div className="text-[10px] font-mono text-gray-500">{cam.camera_id}</div>
                      </td>
                      <td className="py-2.5 px-3 text-center font-bold text-gray-200">{cam.count}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="text-red-400 font-semibold">{cam.active_count}</span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="text-amber-400 font-semibold">{cam.high_severity_count}</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-gray-500">
                      No camera violation data logged for this period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Location / Zone Summary Table */}
      <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
        <div>
          <h2 className="text-base font-bold text-gray-100 flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-sky-400" />
            <span>Zone & Location Compliance Distribution</span>
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">Municipal zone breakdown of cleanliness violations.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#1E293B]/70 text-gray-400 border-b border-gray-800">
              <tr>
                <th className="py-2.5 px-4">Municipal Location / Zone</th>
                <th className="py-2.5 px-4 text-center">Total Incidents</th>
                <th className="py-2.5 px-4 text-center">Solid Waste</th>
                <th className="py-2.5 px-4 text-center">Liquid Waste</th>
                <th className="py-2.5 px-4 text-center">Unresolved Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {data && data.location_breakdown.length > 0 ? (
                data.location_breakdown.map((loc, idx) => (
                  <tr key={idx} className="hover:bg-gray-800/30">
                    <td className="py-2.5 px-4 font-semibold text-gray-200">{loc.location_name}</td>
                    <td className="py-2.5 px-4 text-center font-bold text-gray-100">{loc.count}</td>
                    <td className="py-2.5 px-4 text-center text-indigo-400 font-medium">{loc.solid_count}</td>
                    <td className="py-2.5 px-4 text-center text-cyan-400 font-medium">{loc.liquid_count}</td>
                    <td className="py-2.5 px-4 text-center">
                      <span className="px-2 py-0.5 bg-red-950/70 border border-red-800 text-red-400 rounded text-[11px] font-semibold">
                        {loc.active_count}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-gray-500">
                    No zone records found for specified filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default AnalyticsPage;
