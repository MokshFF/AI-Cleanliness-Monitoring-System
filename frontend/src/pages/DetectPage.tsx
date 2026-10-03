import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { detectImage } from '../api/detection';
import { cameraApi } from '../api/cameras';
import { Camera } from '../types/camera';
import { ImageDetectionResponse } from '../types/detection';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import {
  UploadCloud,
  FileImage,
  Sparkles,
  Trash2,
  ScanLine,
  SlidersHorizontal,
  ArrowRight,
} from 'lucide-react';

export const DetectPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [detectionMode, setDetectionMode] = useState<string>('both');
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [locationName, setLocationName] = useState<string>('');
  const [createIncident, setCreateIncident] = useState<boolean>(true);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.25);

  const [cameras, setCameras] = useState<Camera[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImageDetectionResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    cameraApi.getCameras({ limit: 100 }).then(setCameras).catch(() => {});
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResult(null);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResult(null);
      setError(null);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (selectedCameraId) formData.append('camera_id', selectedCameraId);
      if (locationName) formData.append('location_name', locationName);
      formData.append('detection_mode', detectionMode);
      formData.append('create_incident', String(createIncident));
      formData.append('confidence_threshold', String(confidenceThreshold));

      const response = await detectImage(formData);
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'AI detection processing failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center space-x-2">
          <ScanLine className="w-6 h-6 text-blue-500" />
          <span>Single-Image AI Detection Prototype</span>
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Upload an image to run solid waste detection and liquid waste segmentation with automatic incident creation.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* Main Grid: Upload & Controls on Left, Results on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Upload & Settings (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
            <h2 className="text-sm font-bold text-gray-200 uppercase tracking-wider flex items-center space-x-2">
              <UploadCloud className="w-4 h-4 text-blue-400" />
              <span>Upload Surveillance Image</span>
            </h2>

            {/* Dropzone */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[180px] ${
                previewUrl
                  ? 'border-blue-500/50 bg-[#1E293B]/40'
                  : 'border-gray-700 hover:border-blue-500 bg-[#0F172A]'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.bmp"
                onChange={handleFileChange}
                className="hidden"
              />

              {previewUrl ? (
                <div className="space-y-2">
                  <img
                    src={previewUrl}
                    alt="Upload Preview"
                    className="max-h-40 rounded-lg object-contain mx-auto shadow-md"
                  />
                  <div className="text-xs text-gray-400 font-mono truncate max-w-[240px]">
                    {selectedFile?.name} ({(selectedFile?.size || 0) / 1024 > 1024 ? `${((selectedFile?.size || 0) / 1048576).toFixed(1)} MB` : `${((selectedFile?.size || 0) / 1024).toFixed(0)} KB`})
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="p-3 bg-blue-600/10 rounded-full inline-block text-blue-400">
                    <FileImage className="w-8 h-8" />
                  </div>
                  <div className="text-xs font-semibold text-gray-200">
                    Click to browse or drag & drop image
                  </div>
                  <div className="text-[11px] text-gray-500">
                    Supports JPG, PNG, WebP (Max 10 MB)
                  </div>
                </div>
              )}
            </div>

            {/* Config Controls */}
            <div className="space-y-3 pt-2 border-t border-gray-800">
              <div className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>Detection Options</span>
              </div>

              {/* Detection Mode */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">AI Pipeline Mode</label>
                <select
                  value={detectionMode}
                  onChange={(e) => setDetectionMode(e.target.value)}
                  className="w-full bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg p-2 outline-none"
                >
                  <option value="both">Both (Solid Detection + Liquid Segmentation)</option>
                  <option value="solid">Solid Waste Only (YOLOv8 Detection)</option>
                  <option value="liquid">Liquid Waste Only (YOLOv8-Seg)</option>
                </select>
              </div>

              {/* Source Camera Association */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Source Camera (Optional)</label>
                <select
                  value={selectedCameraId}
                  onChange={(e) => {
                    setSelectedCameraId(e.target.value);
                    const cam = cameras.find((c) => c.camera_id === e.target.value);
                    if (cam) setLocationName(cam.location_name);
                  }}
                  className="w-full bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg p-2 outline-none"
                >
                  <option value="">Default: IMAGE_UPLOAD (No Camera)</option>
                  {cameras.map((c) => (
                    <option key={c.camera_id} value={c.camera_id}>
                      {c.name} ({c.camera_id})
                    </option>
                  ))}
                </select>
              </div>

              {/* Location Name */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Location / Zone Tag</label>
                <input
                  type="text"
                  value={locationName}
                  onChange={(e) => setLocationName(e.target.value)}
                  placeholder="e.g. Terminal 1 Gate A, Food Court"
                  className="w-full bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg p-2 outline-none"
                />
              </div>

              {/* Confidence Threshold Slider */}
              <div>
                <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                  <label>Confidence Threshold</label>
                  <span className="font-mono text-blue-400 font-bold">
                    {(confidenceThreshold * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.01"
                  max="0.90"
                  step="0.01"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                  <span>1% (High Sensitivity)</span>
                  <span>45% (Standard)</span>
                  <span>90% (Strict)</span>
                </div>
              </div>

              {/* Auto Create Incident Checkbox */}
              <div className="pt-1">
                <label className="flex items-center space-x-2 text-xs text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createIncident}
                    onChange={(e) => setCreateIncident(e.target.checked)}
                    className="rounded bg-gray-800 border-gray-700 text-blue-500 focus:ring-0"
                  />
                  <span>Create Incident & Trigger Real-Time Dashboard Alert</span>
                </label>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-2 pt-2">
              <button
                onClick={handleAnalyze}
                disabled={!selectedFile || isLoading}
                className="flex-1 inline-flex items-center justify-center space-x-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition shadow-sm disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span>Analyzing Image...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Analyze Image</span>
                  </>
                )}
              </button>

              {selectedFile && (
                <button
                  onClick={handleClear}
                  disabled={isLoading}
                  className="p-2.5 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded-lg transition"
                  title="Clear Selection"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: AI Detection Results (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {result ? (
            <div className="space-y-4">
              {/* Incident Alert Banner */}
              {result.incident_created && result.incident_ids.length > 0 && (
                <div className="p-4 bg-red-950/40 border border-red-800/80 rounded-xl flex items-center justify-between shadow-lg">
                  <div className="flex items-center space-x-3">
                    <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
                    <div>
                      <div className="text-xs font-bold text-red-400 flex items-center space-x-2">
                        <span>Cleanliness Violation Confirmed</span>
                        <Badge type="severity" value="MEDIUM" size="sm" />
                      </div>
                      <div className="text-xs text-gray-300 mt-0.5">
                        Incident ID: <span className="font-mono text-white font-bold">{result.incident_ids[0]}</span> | Source: <span className="font-semibold">{result.camera_id}</span>
                      </div>
                    </div>
                  </div>

                  <Link
                    to={`/incidents/${result.incident_ids[0]}`}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold transition"
                  >
                    <span>Inspect Incident</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              )}

              {/* Annotated Image Card */}
              <Card className="p-4 bg-[#111827] border-gray-800 space-y-3">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span className="font-bold text-gray-200 uppercase tracking-wider">
                    AI Annotated Output ({result.detections.length} Detected)
                  </span>
                  <span>Latency: {result.processing_time_ms} ms</span>
                </div>

                <div className="rounded-xl overflow-hidden border border-gray-800 bg-[#0B1120] flex items-center justify-center min-h-[300px]">
                  {result.annotated_image_url ? (
                    <img
                      src={result.annotated_image_url}
                      alt="AI Annotated Detections"
                      className="max-h-[420px] w-full object-contain"
                      onError={(e) => {
                        if (previewUrl) {
                          (e.currentTarget as HTMLImageElement).src = previewUrl;
                        }
                      }}
                    />
                  ) : previewUrl ? (
                    <img
                      src={previewUrl}
                      alt="Original Image"
                      className="max-h-[420px] w-full object-contain"
                    />
                  ) : null}
                </div>
              </Card>

              {/* Detected Items Breakdown Table */}
              <Card className="p-4 bg-[#111827] border-gray-800 space-y-3">
                <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                  Detection Breakdown
                </h3>

                {result.detections.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#1E293B] text-gray-400 border-b border-gray-800">
                        <tr>
                          <th className="py-2 px-3">Class Name</th>
                          <th className="py-2 px-3">Waste Type</th>
                          <th className="py-2 px-3 text-center">Confidence</th>
                          <th className="py-2 px-3">Bounding Box [x1, y1, x2, y2]</th>
                          <th className="py-2 px-3 text-center">Area %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-800/60">
                        {result.detections.map((det, idx) => (
                          <tr key={idx} className="hover:bg-gray-800/30">
                            <td className="py-2.5 px-3 font-semibold text-gray-200">
                              {det.class_name.replace(/_/g, ' ')}
                            </td>
                            <td className="py-2.5 px-3">
                              <Badge type="waste" value={det.waste_type} size="sm" />
                            </td>
                            <td className="py-2.5 px-3 text-center font-mono font-bold text-blue-400">
                              {(det.confidence * 100).toFixed(1)}%
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-gray-400">
                              {det.bbox ? det.bbox.map((v) => Math.round(v)).join(', ') : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3 text-center text-cyan-400 font-mono">
                              {det.affected_area_percentage != null
                                ? `${det.affected_area_percentage.toFixed(1)}%`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="py-8 px-4 text-center space-y-2">
                    <div className="text-gray-400 text-xs font-semibold">
                      No cleanliness violations detected above {Math.round(confidenceThreshold * 100)}% confidence threshold.
                    </div>
                    <p className="text-[11px] text-gray-500 max-w-md mx-auto">
                      Current weights are smoke-test models trained for pipeline validation. For real-world images, slide the <span className="text-blue-400 font-semibold">Confidence Threshold</span> down (e.g. to 1% – 5%) and click <span className="text-blue-400 font-semibold">Analyze Image</span> again to visualize lower-confidence detections.
                    </p>
                  </div>
                )}
              </Card>
            </div>
          ) : (
            /* Placeholder before analysis */
            <Card className="p-12 text-center bg-[#111827] border-gray-800 min-h-[460px] flex flex-col items-center justify-center">
              <div className="p-4 bg-gray-800/40 rounded-full text-gray-500 mb-3">
                <Sparkles className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-semibold text-gray-300">
                Awaiting Image Analysis
              </h3>
              <p className="text-xs text-gray-500 max-w-sm mt-1">
                Upload a CCTV frame or photo on the left and click "Analyze Image" to run real-time YOLO inference.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default DetectPage;
