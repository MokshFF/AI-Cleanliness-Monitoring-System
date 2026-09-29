import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { incidentApi } from '../api/incidents';
import { cameraApi } from '../api/cameras';
import { Incident, IncidentStatus, IncidentSeverity, WasteType } from '../types/incident';
import { Camera } from '../types/camera';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Eye,
  RotateCcw,
} from 'lucide-react';

export const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  // Filter states
  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedWasteType, setSelectedWasteType] = useState<string>('');
  const [searchCategory, setSearchCategory] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const fetchIncidents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: any = {
        page,
        page_size: pageSize,
      };
      if (selectedCamera) params.camera_id = selectedCamera;
      if (selectedStatus) params.status = selectedStatus as IncidentStatus;
      if (selectedSeverity) params.severity = selectedSeverity as IncidentSeverity;
      if (selectedWasteType) params.waste_type = selectedWasteType as WasteType;
      if (searchCategory.trim()) params.category = searchCategory.trim().toLowerCase();
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const response = await incidentApi.getIncidents(params);
      setIncidents(response.items);
      setTotalPages(response.total_pages);
      setTotalCount(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retrieve incidents from repository.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Load camera list for filter dropdown
    cameraApi.getCameras().then(setCameras).catch(console.error);
  }, []);

  useEffect(() => {
    fetchIncidents();
  }, [page, pageSize, selectedCamera, selectedStatus, selectedSeverity, selectedWasteType]);

  const handleApplyFilter = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchIncidents();
  };

  const handleResetFilters = () => {
    setSelectedCamera('');
    setSelectedStatus('');
    setSelectedSeverity('');
    setSelectedWasteType('');
    setSearchCategory('');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-100">Cleanliness Incidents</h2>
          <p className="text-xs text-gray-400 mt-1">
            Confirmed solid and liquid waste violations tracked by camera nodes ({totalCount} total)
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <form onSubmit={handleApplyFilter} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Search Category */}
            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Waste Category</label>
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-500" />
                <input
                  type="text"
                  value={searchCategory}
                  onChange={(e) => setSearchCategory(e.target.value)}
                  placeholder="e.g. plastic_bottle, sewage"
                  className="w-full pl-8 pr-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Camera Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Camera Stream</label>
              <select
                value={selectedCamera}
                onChange={(e) => {
                  setSelectedCamera(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Cameras</option>
                {cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.name} ({c.camera_id})
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Status</label>
              <select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Statuses</option>
                <option value="NEW">NEW</option>
                <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                <option value="RESOLVED">RESOLVED</option>
                <option value="DISMISSED">DISMISSED</option>
              </select>
            </div>

            {/* Severity Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Severity</label>
              <select
                value={selectedSeverity}
                onChange={(e) => {
                  setSelectedSeverity(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Severities</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
          </div>

          {/* Secondary Filter Line */}
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2 border-t border-[#24324D]/60 items-end">
            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Waste Type</label>
              <select
                value={selectedWasteType}
                onChange={(e) => {
                  setSelectedWasteType(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="">Solid & Liquid</option>
                <option value="SOLID">Solid Only</option>
                <option value="LIQUID">Liquid Only</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-gray-400 mb-1">End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex space-x-2">
              <button
                type="submit"
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition shadow"
              >
                <Filter className="w-3.5 h-3.5" />
                <span>Filter</span>
              </button>
              <button
                type="button"
                onClick={handleResetFilters}
                className="px-3 py-1.5 bg-[#1E2D48] hover:bg-[#24324D] text-gray-300 rounded-lg text-xs font-medium flex items-center space-x-1 transition border border-[#24324D]"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>
            </div>
          </div>
        </form>
      </Card>

      {/* Error state */}
      {error && <ErrorAlert title="Query Error" message={error} onRetry={fetchIncidents} />}

      {/* Incidents Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="p-12">
            <LoadingSpinner message="Querying incidents from database repository..." />
          </div>
        ) : incidents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-[#0E1626] border-b border-[#24324D] text-gray-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Incident ID</th>
                  <th className="py-3 px-4 font-semibold">Camera Node</th>
                  <th className="py-3 px-4 font-semibold">Category</th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th className="py-3 px-4 font-semibold">Severity</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Confidence</th>
                  <th className="py-3 px-4 font-semibold">Timestamp</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#24324D]">
                {incidents.map((incident) => (
                  <tr key={incident.incident_id} className="hover:bg-[#1E2D48]/40 transition">
                    <td className="py-3 px-4 font-mono font-medium text-gray-200">
                      <Link
                        to={`/incidents/${incident.incident_id}`}
                        className="hover:text-blue-400 hover:underline"
                      >
                        {incident.incident_id}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-gray-300">{incident.camera_id}</td>
                    <td className="py-3 px-4 font-semibold text-gray-100 capitalize">
                      {incident.category.replace('_', ' ')}
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="waste" value={incident.waste_type} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="severity" value={incident.severity} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="status" value={incident.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-mono text-gray-300">
                      {(incident.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 text-gray-400 whitespace-nowrap">
                      {new Date(incident.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/incidents/${incident.incident_id}`}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white rounded border border-blue-500/40 transition font-medium text-xs"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No Incidents Match Search Criteria"
            description="Adjust your search parameters or date range filters to view historical cleanliness violations."
            action={
              <button
                onClick={handleResetFilters}
                className="px-3.5 py-1.5 bg-[#1E2D48] text-gray-200 rounded-lg text-xs font-medium border border-[#24324D] hover:bg-[#24324D]"
              >
                Clear All Filters
              </button>
            }
          />
        )}

        {/* Pagination Bar */}
        {!isLoading && totalCount > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-between px-4 py-3 bg-[#0E1626] border-t border-[#24324D] text-xs text-gray-400 gap-3">
            <div className="flex items-center space-x-2">
              <span>Showing Page</span>
              <strong className="text-gray-200">{page}</strong>
              <span>of</span>
              <strong className="text-gray-200">{totalPages}</strong>
              <span>({totalCount} incidents recorded)</span>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5">
                <span className="text-[11px]">Rows per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="bg-[#151F32] border border-[#24324D] rounded px-2 py-1 text-xs text-gray-200"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
              </div>

              <div className="flex space-x-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1.5 rounded border border-[#24324D] bg-[#151F32] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#1E2D48] text-gray-200 transition"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1.5 rounded border border-[#24324D] bg-[#151F32] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#1E2D48] text-gray-200 transition"
                  title="Next Page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
