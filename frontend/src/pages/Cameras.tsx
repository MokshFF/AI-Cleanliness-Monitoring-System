import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { cameraApi } from '../api/cameras';
import { Camera, DetectionMode, CameraCreateInput } from '../types/camera';
import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { Modal } from '../components/common/Modal';
import {
  Plus,
  Search,
  Settings,
  CheckCircle,
  XCircle,
} from 'lucide-react';

export const Cameras: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedMode, setSelectedMode] = useState<string>('');

  // Register Camera Modal
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState<boolean>(false);
  const [newCamera, setNewCamera] = useState<CameraCreateInput>({
    camera_id: '',
    name: '',
    location_name: '',
    rtsp_url: '',
    detection_mode: 'BOTH',
    target_fps: 5,
    latitude: 28.6139,
    longitude: 77.2090,
  });
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { isAdmin } = useAuth();

  const fetchCameras = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await cameraApi.getCameras({ limit: 100 });
      setCameras(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retrieve camera fleet from database.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
  }, []);

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamera.camera_id.trim() || !newCamera.name.trim() || !newCamera.rtsp_url.trim()) {
      setFormError('Please fill in Camera ID, Name, and RTSP Stream URL.');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);
    try {
      await cameraApi.createCamera(newCamera);
      setIsRegisterModalOpen(false);
      setNewCamera({
        camera_id: '',
        name: '',
        location_name: '',
        rtsp_url: '',
        detection_mode: 'BOTH',
        target_fps: 5,
        latitude: 28.6139,
        longitude: 77.2090,
      });
      fetchCameras();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to register camera stream.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered cameras
  const filteredCameras = cameras.filter((cam) => {
    const matchesSearch =
      cam.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cam.camera_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cam.location_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = !selectedStatus || cam.status === selectedStatus;
    const matchesMode = !selectedMode || cam.detection_mode === selectedMode;
    return matchesSearch && matchesStatus && matchesMode;
  });

  return (
    <div className="space-y-6">
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-100">Camera Stream Registry</h2>
          <p className="text-xs text-gray-400 mt-1">
            Registered CCTV/IP video surveillance streams with dual-stream AI routing ({cameras.length} active nodes)
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={() => {
              setFormError(null);
              setIsRegisterModalOpen(true);
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow"
          >
            <Plus className="w-4 h-4" />
            <span>Register Camera Stream</span>
          </button>
        )}
      </div>

      {/* Filter and Search Card */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1">Search Cameras</label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-500" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by ID, name, location..."
                className="w-full pl-8 pr-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1">Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="ONLINE">ONLINE</option>
              <option value="OFFLINE">OFFLINE</option>
              <option value="CONNECTING">CONNECTING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1">AI Detection Mode</label>
            <select
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value)}
              className="w-full px-3 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Modes (Solid & Liquid)</option>
              <option value="BOTH">BOTH (Solid + Liquid)</option>
              <option value="SOLID">SOLID Only</option>
              <option value="LIQUID">LIQUID Only</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Error state */}
      {error && <ErrorAlert title="Camera Fleet Error" message={error} onRetry={fetchCameras} />}

      {/* Camera Grid Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="p-12">
            <LoadingSpinner message="Loading camera registry from MongoDB repository..." />
          </div>
        ) : filteredCameras.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-[#0E1626] border-b border-[#24324D] text-gray-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Camera ID</th>
                  <th className="py-3 px-4 font-semibold">Name & Location</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">AI Routing</th>
                  <th className="py-3 px-4 font-semibold">Target FPS</th>
                  <th className="py-3 px-4 font-semibold">Stream URI (Masked)</th>
                  <th className="py-3 px-4 font-semibold">Active</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#24324D]">
                {filteredCameras.map((cam) => (
                  <tr key={cam.camera_id} className="hover:bg-[#1E2D48]/40 transition">
                    <td className="py-3 px-4 font-mono font-medium text-gray-200">
                      <Link
                        to={`/cameras/${cam.camera_id}`}
                        className="hover:text-blue-400 hover:underline"
                      >
                        {cam.camera_id}
                      </Link>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-gray-100">{cam.name}</div>
                      <div className="text-[10px] text-gray-400">{cam.location_name}</div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="camera_status" value={cam.status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="detection_mode" value={cam.detection_mode} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-mono text-gray-300">{cam.target_fps} FPS</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-gray-400 max-w-[200px] truncate" title={cam.rtsp_url}>
                      {cam.rtsp_url || 'rtsp://***:***@stream'}
                    </td>
                    <td className="py-3 px-4">
                      {cam.is_active ? (
                        <span className="inline-flex items-center text-emerald-400 text-xs">
                          <CheckCircle className="w-3.5 h-3.5 mr-1" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-gray-500 text-xs">
                          <XCircle className="w-3.5 h-3.5 mr-1" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/cameras/${cam.camera_id}`}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white rounded border border-blue-500/40 transition font-medium text-xs"
                      >
                        <Settings className="w-3.5 h-3.5" />
                        <span>Manage</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No Cameras Found"
            description="No camera surveillance streams match your filter criteria or none have been registered yet."
            action={
              isAdmin ? (
                <button
                  onClick={() => setIsRegisterModalOpen(true)}
                  className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold"
                >
                  Register First Camera
                </button>
              ) : undefined
            }
          />
        )}
      </Card>

      {/* Camera Registration Modal */}
      <Modal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
        title="Register New CCTV / RTSP Stream"
      >
        <form onSubmit={handleRegisterSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-lg text-xs text-red-200">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Camera ID *
              </label>
              <input
                type="text"
                required
                value={newCamera.camera_id}
                onChange={(e) => setNewCamera({ ...newCamera, camera_id: e.target.value })}
                placeholder="e.g. CAM-DELHI-001"
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Camera Name *
              </label>
              <input
                type="text"
                required
                value={newCamera.name}
                onChange={(e) => setNewCamera({ ...newCamera, name: e.target.value })}
                placeholder="e.g. Connaught Place Gate 1"
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">
              Physical Location / Zone *
            </label>
            <input
              type="text"
              required
              value={newCamera.location_name}
              onChange={(e) => setNewCamera({ ...newCamera, location_name: e.target.value })}
              placeholder="e.g. Zone 4 Central Plaza"
              className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">
              RTSP Stream URL * (Credentials auto-masked in UI)
            </label>
            <input
              type="text"
              required
              value={newCamera.rtsp_url}
              onChange={(e) => setNewCamera({ ...newCamera, rtsp_url: e.target.value })}
              placeholder="rtsp://admin:pass@192.168.1.100:554/live"
              className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                AI Detection Mode
              </label>
              <select
                value={newCamera.detection_mode}
                onChange={(e) =>
                  setNewCamera({ ...newCamera, detection_mode: e.target.value as DetectionMode })
                }
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              >
                <option value="BOTH">BOTH (Solid + Liquid)</option>
                <option value="SOLID">SOLID Only (YOLO Detect)</option>
                <option value="LIQUID">LIQUID Only (YOLO Segment)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Sampling Rate (Target FPS)
              </label>
              <input
                type="number"
                min="0.5"
                max="30"
                step="0.5"
                value={newCamera.target_fps}
                onChange={(e) =>
                  setNewCamera({ ...newCamera, target_fps: Number(e.target.value) })
                }
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Latitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={newCamera.latitude}
                onChange={(e) =>
                  setNewCamera({ ...newCamera, latitude: Number(e.target.value) })
                }
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Longitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={newCamera.longitude}
                onChange={(e) =>
                  setNewCamera({ ...newCamera, longitude: Number(e.target.value) })
                }
                className="w-full p-2 bg-[#0E1626] border border-[#24324D] rounded-lg text-xs text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-[#24324D]">
            <button
              type="button"
              onClick={() => setIsRegisterModalOpen(false)}
              className="px-3.5 py-1.5 bg-[#1E2D48] text-gray-300 hover:bg-[#24324D] rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold"
            >
              <span>{isSubmitting ? 'Registering...' : 'Register Camera'}</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
