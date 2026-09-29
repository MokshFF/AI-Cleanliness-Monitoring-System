import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { cameraApi } from '../api/cameras';
import { Camera, CameraUpdateInput, DetectionMode } from '../types/camera';
import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { Modal } from '../components/common/Modal';
import {
  ArrowLeft,
  Video,
  Settings,
  Trash2,
  Power,
  AlertTriangle,
} from 'lucide-react';

export const CameraDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [camera, setCamera] = useState<Camera | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [editData, setEditData] = useState<CameraUpdateInput>({});
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Decommission Modal State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const fetchCamera = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await cameraApi.getCameraById(id);
      setCamera(data);
      setEditData({
        name: data.name,
        location_name: data.location_name,
        detection_mode: data.detection_mode,
        target_fps: data.target_fps,
        status: data.status,
        is_active: data.is_active,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load camera stream configuration.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCamera();
  }, [id]);

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;

    setIsUpdating(true);
    setModalError(null);
    try {
      const updated = await cameraApi.updateCamera(id, editData);
      setCamera(updated);
      setIsEditModalOpen(false);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to update camera parameters.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleToggleActive = async () => {
    if (!id || !camera) return;
    try {
      const updated = await cameraApi.updateCamera(id, {
        is_active: !camera.is_active,
        status: !camera.is_active ? 'ONLINE' : 'OFFLINE',
      });
      setCamera(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to toggle camera active status.');
    }
  };

  const handleDeleteCamera = async () => {
    if (!id) return;
    setIsDeleting(true);
    try {
      await cameraApi.deleteCamera(id);
      navigate('/cameras', { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to decommission camera stream.');
      setIsDeleteModalOpen(false);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Retrieving Camera Configuration & Telemetry..." size="lg" />;
  }

  if (error || !camera) {
    return (
      <div className="space-y-4">
        <Link to="/cameras" className="inline-flex items-center text-xs text-blue-400 hover:text-blue-300">
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Cameras
        </Link>
        <ErrorAlert title="Camera Configuration Error" message={error || 'Camera not found'} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link
            to="/cameras"
            className="inline-flex items-center text-xs text-gray-400 hover:text-gray-200 transition mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> All Cameras
          </Link>
          <div className="flex items-center space-x-3">
            <h2 className="text-xl font-bold tracking-tight text-gray-100 font-mono">
              {camera.camera_id}
            </h2>
            <Badge type="camera_status" value={camera.status} size="md" />
            <Badge type="detection_mode" value={camera.detection_mode} size="md" />
          </div>
        </div>

        {/* Admin Management Actions */}
        {isAdmin && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleToggleActive}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition border ${
                camera.is_active
                  ? 'bg-amber-950/60 border-amber-800 text-amber-300 hover:bg-amber-900'
                  : 'bg-emerald-950/60 border-emerald-800 text-emerald-300 hover:bg-emerald-900'
              }`}
            >
              <Power className="w-3.5 h-3.5" />
              <span>{camera.is_active ? 'Deactivate Stream' : 'Activate Stream'}</span>
            </button>

            <button
              onClick={() => {
                setModalError(null);
                setIsEditModalOpen(true);
              }}
              className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Edit Configuration</span>
            </button>

            <button
              onClick={() => setIsDeleteModalOpen(true)}
              className="px-3 py-2 bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 rounded-lg text-xs font-medium transition"
              title="Decommission stream"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Grid: Left Stream Ingestion Architecture, Right Parameters */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Stream Status & Phase 8/9 Notice */}
        <div className="lg:col-span-7 space-y-6">
          <Card title="Stream Ingestion Architecture" subtitle="RTSP capture with thread-isolated ring buffer">
            <div className="aspect-video bg-[#0E1626] border border-[#24324D] rounded-xl flex flex-col items-center justify-center p-6 text-center relative overflow-hidden">
              <div className="p-4 bg-blue-600/10 border border-blue-500/20 rounded-full text-blue-400 mb-3">
                <Video className="w-10 h-10" />
              </div>
              <h4 className="text-sm font-semibold text-gray-200">
                Phase 4 RTSP Ingestion Pipeline Active
              </h4>
              <p className="text-xs text-gray-400 max-w-md mt-1 leading-relaxed">
                Raw RTSP packets are continuously consumed by worker threads with bounded FIFO buffers
                and sampled at <strong className="text-blue-400">{camera.target_fps} FPS</strong>.
              </p>
              <div className="mt-4 p-3 bg-[#151F32] border border-[#24324D] rounded-lg text-[11px] text-gray-400 max-w-sm">
                <p className="font-semibold text-gray-300 mb-0.5">Live Browser Streaming:</p>
                <span>
                  Direct browser HLS/WebRTC streaming belongs to Phase 8/10. Real-time incident snapshots
                  and detection telemetry are fully accessible below.
                </span>
              </div>
            </div>

            <div className="mt-4 p-3.5 bg-[#0E1626] border border-[#24324D] rounded-xl">
              <span className="text-[11px] font-semibold text-gray-400 block mb-1">
                Active Ingestion URI (Credential Protected):
              </span>
              <code className="text-xs text-blue-300 font-mono block break-all">
                {camera.rtsp_url || 'rtsp://***:***@stream'}
              </code>
            </div>
          </Card>
        </div>

        {/* Right Column: Parameters and Node Telemetry */}
        <div className="lg:col-span-5 space-y-6">
          <Card title="Camera Properties" subtitle="Technical stream configuration">
            <div className="divide-y divide-[#24324D] text-xs">
              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Stream Name:</span>
                <span className="font-semibold text-gray-200">{camera.name}</span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Physical Location:</span>
                <span className="text-gray-200">{camera.location_name}</span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">AI Routing Mode:</span>
                <Badge type="detection_mode" value={camera.detection_mode} size="sm" />
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Target Sampling Rate:</span>
                <span className="font-mono text-gray-200">{camera.target_fps} FPS</span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Monitoring Active:</span>
                <span className={camera.is_active ? 'text-emerald-400 font-medium' : 'text-gray-500'}>
                  {camera.is_active ? 'YES (Active Ingestion)' : 'NO (Disabled)'}
                </span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">GIS Coordinates:</span>
                <span className="font-mono text-gray-300">
                  {camera.latitude.toFixed(4)}, {camera.longitude.toFixed(4)}
                </span>
              </div>

              <div className="py-2.5 flex justify-between items-center">
                <span className="text-gray-400">Registered On:</span>
                <span className="text-gray-400">
                  {new Date(camera.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Edit Camera Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title={`Edit Camera: ${camera.camera_id}`}
      >
        <form onSubmit={handleEditSubmit} className="space-y-4">
          {modalError && (
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-lg text-xs text-red-200">
              {modalError}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Camera Name</label>
            <input
              type="text"
              value={editData.name || ''}
              onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Location Name</label>
            <input
              type="text"
              value={editData.location_name || ''}
              onChange={(e) => setEditData({ ...editData, location_name: e.target.value })}
              className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Detection Mode</label>
              <select
                value={editData.detection_mode || 'BOTH'}
                onChange={(e) =>
                  setEditData({ ...editData, detection_mode: e.target.value as DetectionMode })
                }
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="BOTH">BOTH (Solid + Liquid)</option>
                <option value="SOLID">SOLID Only</option>
                <option value="LIQUID">LIQUID Only</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Target FPS</label>
              <input
                type="number"
                min="0.5"
                max="30"
                step="0.5"
                value={editData.target_fps || 5}
                onChange={(e) => setEditData({ ...editData, target_fps: Number(e.target.value) })}
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-[#24324D]">
            <button
              type="button"
              onClick={() => setIsEditModalOpen(false)}
              className="px-3.5 py-1.5 bg-[#1E2D48] text-gray-300 hover:bg-[#24324D] rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUpdating}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold"
            >
              <span>{isUpdating ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete / Decommission Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Confirm Decommission"
      >
        <div className="space-y-4">
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-200 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span>
              Are you sure you want to permanently decommission camera{' '}
              <strong className="text-white font-mono">{camera.camera_id}</strong>? Video ingestion
              for this stream will terminate immediately.
            </span>
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-[#24324D]">
            <button
              onClick={() => setIsDeleteModalOpen(false)}
              className="px-3.5 py-1.5 bg-[#1E2D48] text-gray-300 hover:bg-[#24324D] rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteCamera}
              disabled={isDeleting}
              className="px-4 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-1"
            >
              <span>{isDeleting ? 'Decommissioning...' : 'Confirm Decommission'}</span>
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
