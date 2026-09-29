import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { incidentApi } from '../api/incidents';
import { cameraApi } from '../api/cameras';
import { Incident, IncidentStatus } from '../types/incident';
import { Camera } from '../types/camera';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { Modal } from '../components/common/Modal';
import {
  ArrowLeft,
  CheckCircle,
  Activity,
  Image as ImageIcon,
} from 'lucide-react';

export const IncidentDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [incident, setIncident] = useState<Incident | null>(null);
  const [camera, setCamera] = useState<Camera | null>(null);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSnapshotLoading, setIsSnapshotLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Status Action Modal
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [targetStatus, setTargetStatus] = useState<IncidentStatus>('ACKNOWLEDGED');
  const [statusNotes, setStatusNotes] = useState<string>('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);
  const [statusActionMessage, setStatusActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchIncidentDetails = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const inc = await incidentApi.getIncidentById(id);
      setIncident(inc);

      // Fetch camera metadata if available
      try {
        const cam = await cameraApi.getCameraById(inc.camera_id);
        setCamera(cam);
      } catch (camErr) {
        console.warn('Camera metadata lookup skipped:', camErr);
      }

      // Load snapshot image securely as a blob URL
      try {
        setIsSnapshotLoading(true);
        const blobUrl = await incidentApi.fetchSnapshotBlob(inc.incident_id);
        setSnapshotUrl(blobUrl);
      } catch (snapErr) {
        console.warn('Direct snapshot fetch failed, checking static fallback:', snapErr);
        // Fallback: If snapshot_path exists, use direct relative path if accessible
        if (inc.snapshot_path) {
          setSnapshotUrl(`/${inc.snapshot_path}`);
        }
      } finally {
        setIsSnapshotLoading(false);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retrieve incident details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidentDetails();

    return () => {
      // Cleanup object URL on unmount
      if (snapshotUrl && snapshotUrl.startsWith('blob:')) {
        URL.revokeObjectURL(snapshotUrl);
      }
    };
  }, [id]);

  const handleOpenStatusModal = (status: IncidentStatus) => {
    setTargetStatus(status);
    setStatusNotes(
      status === 'ACKNOWLEDGED'
        ? 'Field sanitization unit dispatched to location.'
        : status === 'RESOLVED'
        ? 'Debris cleared and verification inspection completed.'
        : 'False positive or transient non-violation.'
    );
    setStatusActionMessage(null);
    setIsModalOpen(true);
  };

  const handleConfirmStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incident) return;

    setIsUpdatingStatus(true);
    setStatusActionMessage(null);

    try {
      const updated = await incidentApi.updateIncidentStatus(incident.incident_id, {
        status: targetStatus,
        notes: statusNotes.trim() || undefined,
      });
      setIncident(updated);
      setIsModalOpen(false);
      setStatusActionMessage({
        type: 'success',
        text: `Incident successfully updated to ${targetStatus}.`,
      });
    } catch (err: any) {
      setStatusActionMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to update incident status in database.',
      });
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Retrieving Incident Evidence & Telemetry..." size="lg" />;
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <Link to="/incidents" className="inline-flex items-center text-xs text-blue-400 hover:text-blue-300">
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Incidents List
        </Link>
        <ErrorAlert title="Incident Retrieval Error" message={error || 'Incident record not found'} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link
            to="/incidents"
            className="inline-flex items-center text-xs text-gray-400 hover:text-gray-200 transition mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> All Incidents
          </Link>
          <div className="flex items-center space-x-3">
            <h2 className="text-xl font-bold tracking-tight text-gray-100 font-mono">
              {incident.incident_id}
            </h2>
            <Badge type="waste" value={incident.waste_type} size="md" />
            <Badge type="severity" value={incident.severity} size="md" />
            <Badge type="status" value={incident.status} size="md" />
          </div>
        </div>

        {/* Action Buttons for Triage */}
        <div className="flex items-center space-x-2">
          {incident.status === 'NEW' && (
            <button
              onClick={() => handleOpenStatusModal('ACKNOWLEDGED')}
              className="px-3.5 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Acknowledge Incident</span>
            </button>
          )}

          {incident.status !== 'RESOLVED' && (
            <button
              onClick={() => handleOpenStatusModal('RESOLVED')}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Mark Resolved</span>
            </button>
          )}

          {incident.status !== 'DISMISSED' && (
            <button
              onClick={() => handleOpenStatusModal('DISMISSED')}
              className="px-3 py-2 bg-[#1E2D48] hover:bg-[#24324D] text-gray-300 rounded-lg text-xs font-medium border border-[#24324D] transition"
            >
              <span>Dismiss</span>
            </button>
          )}
        </div>
      </div>

      {/* Success notification banner */}
      {statusActionMessage && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between ${
            statusActionMessage.type === 'success'
              ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
              : 'bg-red-950/60 border-red-800 text-red-300'
          }`}
        >
          <span>{statusActionMessage.text}</span>
          <button
            onClick={() => setStatusActionMessage(null)}
            className="text-gray-400 hover:text-gray-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* Two-Column Grid: Left Evidence & Snapshot, Right Telemetry & Metadata */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Evidence Snapshot */}
        <div className="lg:col-span-7 space-y-6">
          <Card title="Visual Evidence Snapshot" subtitle="AI Detection bounding box / polygon overlay snapshot">
            <div className="relative aspect-video bg-[#0B1120] border border-[#24324D] rounded-lg overflow-hidden flex items-center justify-center">
              {isSnapshotLoading ? (
                <LoadingSpinner message="Retrieving secure snapshot stream..." />
              ) : snapshotUrl ? (
                <img
                  src={snapshotUrl}
                  alt={`Evidence for ${incident.incident_id}`}
                  className="w-full h-full object-contain"
                  onError={() => setSnapshotUrl(null)}
                />
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-center text-gray-500">
                  <ImageIcon className="w-12 h-12 mb-2 stroke-1" />
                  <p className="text-xs font-medium">Snapshot image unavailable on server filesystem</p>
                  <span className="text-[10px] text-gray-600 mt-1 font-mono">
                    {incident.snapshot_path || 'No snapshot path stored'}
                  </span>
                </div>
              )}

              {/* Watermark / Category Stamp */}
              <div className="absolute top-2 left-2 px-2.5 py-1 bg-black/70 backdrop-blur border border-white/10 rounded text-[10px] text-gray-200 font-mono">
                {incident.category.toUpperCase()} • {(incident.confidence * 100).toFixed(1)}% CONF
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 px-1">
              <span>Path: <code className="text-gray-300 font-mono">{incident.snapshot_path}</code></span>
              <span>Captured: {new Date(incident.timestamp).toLocaleString()}</span>
            </div>
          </Card>

          {/* Operator Audit & Notes Section */}
          <Card title="Operator Triage Log" subtitle="Field dispatch and status audit history">
            <div className="space-y-3">
              <div className="p-3 bg-[#0E1626] rounded-lg border border-[#24324D] text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-gray-200">Current Lifecycle Status:</span>
                  <Badge type="status" value={incident.status} size="sm" />
                </div>
                <p className="text-gray-400 mt-1.5 leading-relaxed">
                  {incident.notes || 'No operator field notes attached to this incident yet.'}
                </p>
              </div>

              {incident.resolved_at && (
                <div className="p-3 bg-emerald-950/20 border border-emerald-900/40 rounded-lg text-xs text-emerald-400 flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <span>Resolved at: {new Date(incident.resolved_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: Incident Telemetry & Camera Node Info */}
        <div className="lg:col-span-5 space-y-6">
          {/* Metadata Card */}
          <Card title="Violation Attributes" subtitle="Validated AI detection telemetry">
            <div className="divide-y divide-[#24324D] text-xs">
              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Waste Classification:</span>
                <span className="font-semibold text-gray-200 capitalize">
                  {incident.category.replace('_', ' ')}
                </span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Detection Confidence:</span>
                <span className="font-mono font-semibold text-blue-400">
                  {(incident.confidence * 100).toFixed(2)}%
                </span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Violation Severity:</span>
                <Badge type="severity" value={incident.severity} size="sm" />
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">First Detected:</span>
                <span className="text-gray-300">
                  {new Date(incident.timestamp).toLocaleString()}
                </span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Record Created:</span>
                <span className="text-gray-400">
                  {incident.created_at ? new Date(incident.created_at).toLocaleString() : 'N/A'}
                </span>
              </div>
            </div>
          </Card>

          {/* Solid vs Liquid Specialized AI Telemetry */}
          <Card
            title={incident.waste_type === 'SOLID' ? 'Solid Waste Tracking' : 'Liquid Waste Polygon Analysis'}
            subtitle={incident.waste_type === 'SOLID' ? 'ByteTrack object persistence' : 'Area coverage and ROI analysis'}
          >
            {incident.waste_type === 'SOLID' ? (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
                  <span className="text-gray-400">ByteTrack Track ID:</span>
                  <span className="font-mono font-bold text-indigo-400">
                    {incident.track_id !== undefined ? `#${incident.track_id}` : 'Static Detection'}
                  </span>
                </div>

                <div className="p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
                  <span className="text-gray-400 block mb-1">Bounding Box Coordinates [x1, y1, x2, y2]:</span>
                  <code className="text-gray-300 font-mono block truncate">
                    {incident.bounding_box ? JSON.stringify(incident.bounding_box) : 'N/A'}
                  </code>
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
                  <span className="text-gray-400">Affected Area:</span>
                  <span className="font-mono font-bold text-cyan-400">
                    {incident.affected_area_percentage !== undefined
                      ? `${incident.affected_area_percentage.toFixed(2)}% of frame`
                      : 'Accumulation Confirmed'}
                  </span>
                </div>

                <div className="p-2.5 bg-[#0E1626] rounded-lg border border-[#24324D]">
                  <span className="text-gray-400 block mb-1">Polygon Segmentation Vertex Count:</span>
                  <code className="text-gray-300 font-mono block">
                    {incident.mask_polygon ? `${incident.mask_polygon.length} points` : 'Calculated Mask'}
                  </code>
                </div>
              </div>
            )}
          </Card>

          {/* Camera Node Information */}
          <Card title="Originating Camera Node" subtitle="Surveillance infrastructure details">
            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center py-1.5 border-b border-[#24324D]/50">
                <span className="text-gray-400">Camera ID:</span>
                <Link
                  to={`/cameras/${incident.camera_id}`}
                  className="font-mono font-semibold text-blue-400 hover:underline"
                >
                  {incident.camera_id}
                </Link>
              </div>

              {camera ? (
                <>
                  <div className="flex justify-between items-center py-1.5 border-b border-[#24324D]/50">
                    <span className="text-gray-400">Location:</span>
                    <span className="text-gray-200">{camera.location_name}</span>
                  </div>

                  <div className="flex justify-between items-center py-1.5 border-b border-[#24324D]/50">
                    <span className="text-gray-400">Coordinates:</span>
                    <span className="font-mono text-gray-300">
                      {camera.latitude.toFixed(4)}, {camera.longitude.toFixed(4)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center py-1.5">
                    <span className="text-gray-400">Camera Status:</span>
                    <Badge type="camera_status" value={camera.status} size="sm" />
                  </div>
                </>
              ) : (
                <div className="py-2 text-gray-500 italic">No additional camera metadata cached</div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Status Transition Confirmation Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={`Update Status to ${targetStatus}`}
      >
        <form onSubmit={handleConfirmStatusUpdate} className="space-y-4">
          <p className="text-xs text-gray-300 leading-relaxed">
            You are about to change the lifecycle status of incident{' '}
            <strong className="text-blue-400">{incident.incident_id}</strong> to{' '}
            <strong className="text-gray-100">{targetStatus}</strong>. This update will be recorded
            in the system audit log.
          </p>

          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">
              Field Action / Resolution Notes
            </label>
            <textarea
              rows={3}
              value={statusNotes}
              onChange={(e) => setStatusNotes(e.target.value)}
              placeholder="Enter notes on field team dispatch, debris cleaning, or reason for dismissal..."
              className="w-full p-2.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-[#24324D]">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-3 py-1.5 bg-[#1E2D48] text-gray-300 hover:bg-[#24324D] rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUpdatingStatus}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-1"
            >
              <span>{isUpdatingStatus ? 'Saving...' : `Confirm ${targetStatus}`}</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
