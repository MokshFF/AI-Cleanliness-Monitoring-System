import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  processVideo,
  startCameraTest,
  stopCameraTest,
  getCameraTestStatus,
  detectImage,
} from '../api/detection';
import {
  VideoProcessResponse,
  CameraTestStatusResponse,
} from '../types/detection';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import {
  Video,
  Play,
  Square,
  RefreshCw,
  Camera as CameraIcon,
  Activity,
  Upload,
} from 'lucide-react';

type TabMode = 'video' | 'rtsp' | 'webcam';

export const CameraTestPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabMode>('video');

  // Mode A: Video states
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoName, setVideoName] = useState<string>('cctv_sample.mp4');
  const [isVideoLoading, setIsVideoLoading] = useState<boolean>(false);
  const [videoResult, setVideoResult] = useState<VideoProcessResponse | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);

  // Mode B: RTSP / Prototype Camera states
  const [cameraStatus, setCameraStatus] = useState<CameraTestStatusResponse | null>(null);
  const [isCameraLoading, setIsCameraLoading] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [rtspInput, setRtspInput] = useState<string>('');
  const [frameTimestamp, setFrameTimestamp] = useState<number>(Date.now());

  // Mode C: Webcam states
  const [isWebcamActive, setIsWebcamActive] = useState<boolean>(false);
  const [webcamError, setWebcamError] = useState<string | null>(null);
  const [isWebcamDetecting, setIsWebcamDetecting] = useState<boolean>(false);
  const [webcamResult, setWebcamResult] = useState<any>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Fetch prototype camera status periodically
  const fetchCameraStatus = async () => {
    try {
      const status = await getCameraTestStatus();
      setCameraStatus(status);
      if (status.is_running) {
        setFrameTimestamp(Date.now());
      }
    } catch (err: any) {
      // Background poll failure
    }
  };

  useEffect(() => {
    fetchCameraStatus();
    const interval = setInterval(fetchCameraStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Mode A: Process Local Video
  const handleProcessVideo = async () => {
    setIsVideoLoading(true);
    setVideoError(null);
    try {
      const formData = new FormData();
      if (videoFile) {
        formData.append('file', videoFile);
      } else {
        formData.append('video_name', videoName);
      }
      formData.append('camera_id', 'VIDEO_PROTOTYPE');

      const response = await processVideo(formData);
      setVideoResult(response);
    } catch (err: any) {
      setVideoError(err.response?.data?.detail || 'Local video processing failed.');
    } finally {
      setIsVideoLoading(false);
    }
  };

  // Mode B: RTSP Start / Stop
  const handleStartStream = async () => {
    setIsCameraLoading(true);
    setCameraError(null);
    try {
      await startCameraTest({
        camera_id: 'CAM-001',
        camera_name: 'Main Gate Camera',
        stream_source: rtspInput.trim() || undefined,
      });
      await fetchCameraStatus();
    } catch (err: any) {
      setCameraError(err.response?.data?.detail || 'Failed to start camera runner.');
    } finally {
      setIsCameraLoading(false);
    }
  };

  const handleStopStream = async () => {
    setIsCameraLoading(true);
    try {
      await stopCameraTest();
      await fetchCameraStatus();
    } catch (err: any) {
      setCameraError(err.response?.data?.detail || 'Failed to stop camera runner.');
    } finally {
      setIsCameraLoading(false);
    }
  };

  // Mode C: Webcam Start / Stop / Capture
  const handleToggleWebcam = async () => {
    if (isWebcamActive) {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
      setIsWebcamActive(false);
    } else {
      setWebcamError(null);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
        setIsWebcamActive(true);
      } catch (err: any) {
        setWebcamError(err.message || 'Could not access laptop webcam. Please grant browser permissions.');
      }
    }
  };

  const handleCaptureWebcamFrame = async () => {
    if (!videoRef.current || !canvasRef.current) return;

    setIsWebcamDetecting(true);
    try {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(async (blob) => {
        if (!blob) return;
        const formData = new FormData();
        formData.append('file', blob, 'webcam_frame.jpg');
        formData.append('camera_id', 'WEBCAM_PROTOTYPE');
        formData.append('location_name', 'Operator Laptop Webcam');
        formData.append('create_incident', 'true');

        const resp = await detectImage(formData);
        setWebcamResult(resp);
        setIsWebcamDetecting(false);
      }, 'image/jpeg', 0.85);
    } catch (err: any) {
      setIsWebcamDetecting(false);
      setWebcamError(err.message || 'Frame detection failed.');
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center space-x-2">
            <Video className="w-6 h-6 text-blue-500" />
            <span>Single-Camera & Video Prototype Lab</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Test AI detection and incident validation with local video files, simulated CCTV, or live RTSP streams.
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex items-center bg-[#111827] border border-gray-800 rounded-xl p-1">
          <button
            onClick={() => setActiveTab('video')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'video'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Local MP4 Video
          </button>
          <button
            onClick={() => setActiveTab('rtsp')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'rtsp'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            RTSP / CCTV Stream
          </button>
          <button
            onClick={() => setActiveTab('webcam')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'webcam'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Laptop Webcam
          </button>
        </div>
      </div>

      {/* TAB 1: LOCAL VIDEO PROCESSING */}
      {activeTab === 'video' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 space-y-4">
            <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
              <h2 className="text-sm font-bold text-gray-200 uppercase tracking-wider flex items-center space-x-2">
                <Upload className="w-4 h-4 text-blue-400" />
                <span>Select CCTV Video Source</span>
              </h2>

              {/* Sample video picker */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Pre-loaded Test Videos</label>
                <select
                  value={videoName}
                  onChange={(e) => {
                    setVideoName(e.target.value);
                    setVideoFile(null);
                  }}
                  className="w-full bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg p-2.5 outline-none"
                >
                  <option value="cctv_sample.mp4">cctv_sample.mp4 (Solid Waste CCTV Stream)</option>
                  <option value="liquid_cctv_sample.mp4">liquid_cctv_sample.mp4 (Liquid Waste Overflow)</option>
                </select>
              </div>

              <div className="relative flex py-2 items-center">
                <div className="flex-grow border-t border-gray-800"></div>
                <span className="flex-shrink mx-4 text-[10px] text-gray-500 uppercase font-semibold">Or upload custom MP4</span>
                <div className="flex-grow border-t border-gray-800"></div>
              </div>

              {/* File upload */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Upload MP4 File</label>
                <input
                  type="file"
                  accept="video/mp4,video/x-m4v,video/*"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setVideoFile(e.target.files[0]);
                      setVideoResult(null);
                    }
                  }}
                  className="w-full text-xs text-gray-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500"
                />
              </div>

              <div className="p-3 bg-[#1E293B]/50 rounded-lg text-xs text-gray-400 space-y-1">
                <div><b>Inference Cadence:</b> Target 5 FPS</div>
                <div><b>Temporal Validation:</b> 3-5 consecutive frames</div>
                <div><b>Output:</b> Frame detections, tracking, MongoDB incident & WS alert</div>
              </div>

              <button
                onClick={handleProcessVideo}
                disabled={isVideoLoading}
                className="w-full inline-flex items-center justify-center space-x-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition shadow-sm disabled:opacity-50"
              >
                {isVideoLoading ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span>Processing Video Frames (5 FPS)...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Run AI Video Analysis</span>
                  </>
                )}
              </button>
            </Card>
          </div>

          <div className="lg:col-span-7 space-y-4">
            {videoError && <ErrorAlert message={videoError} />}

            {videoResult ? (
              <div className="space-y-4">
                {/* Incident notification */}
                {videoResult.incident_created && videoResult.incident_ids.length > 0 && (
                  <div className="p-4 bg-red-950/40 border border-red-800/80 rounded-xl flex items-center justify-between shadow-lg">
                    <div className="flex items-center space-x-3">
                      <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
                      <div>
                        <div className="text-xs font-bold text-red-400">
                          Violation Confirmed & Incident Dispatched
                        </div>
                        <div className="text-xs text-gray-300 mt-0.5">
                          ID: <span className="font-mono text-white font-bold">{videoResult.incident_ids[0]}</span>
                        </div>
                      </div>
                    </div>
                    <Link
                      to={`/incidents/${videoResult.incident_ids[0]}`}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold"
                    >
                      View Incident &rarr;
                    </Link>
                  </div>
                )}

                {/* Video Metrics */}
                <div className="grid grid-cols-3 gap-3">
                  <Card className="p-3 bg-[#111827] border-gray-800">
                    <div className="text-xs text-gray-400">Frames Processed</div>
                    <div className="text-xl font-bold text-gray-100 mt-0.5">{videoResult.frames_processed}</div>
                  </Card>
                  <Card className="p-3 bg-[#111827] border-gray-800">
                    <div className="text-xs text-gray-400">Detections Logged</div>
                    <div className="text-xl font-bold text-blue-400 mt-0.5">{videoResult.detections_count}</div>
                  </Card>
                  <Card className="p-3 bg-[#111827] border-gray-800">
                    <div className="text-xs text-gray-400">Processing FPS</div>
                    <div className="text-xl font-bold text-emerald-400 mt-0.5">{videoResult.processing_fps} FPS</div>
                  </Card>
                </div>

                {/* Annotated Frame */}
                {videoResult.annotated_frame_url && (
                  <Card className="p-4 bg-[#111827] border-gray-800 space-y-2">
                    <div className="text-xs font-bold text-gray-300 uppercase tracking-wider">
                      Latest Annotated Video Frame
                    </div>
                    <div className="rounded-xl overflow-hidden border border-gray-800 bg-[#0B1120] max-h-[360px] flex items-center justify-center">
                      <img
                        src={videoResult.annotated_frame_url}
                        alt="Annotated Frame"
                        className="w-full object-contain max-h-[360px]"
                      />
                    </div>
                  </Card>
                )}
              </div>
            ) : (
              <Card className="p-12 text-center bg-[#111827] border-gray-800 min-h-[360px] flex flex-col items-center justify-center">
                <Video className="w-10 h-10 text-gray-600 mb-3" />
                <h3 className="text-sm font-semibold text-gray-300">Awaiting Video Analysis</h3>
                <p className="text-xs text-gray-500 max-w-sm mt-1">
                  Select a preloaded CCTV video or upload an MP4 file on the left to process frames.
                </p>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: REAL RTSP / LIVE CCTV RUNNER */}
      {activeTab === 'rtsp' && (
        <div className="space-y-6">
          {cameraError && <ErrorAlert message={cameraError} />}

          {/* Control Bar & Telemetry */}
          <Card className="p-5 bg-[#111827] border-gray-800">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="text-base font-bold text-gray-100">
                    {cameraStatus?.camera_name || 'Main Gate Surveillance Camera'}
                  </span>
                  <span className="text-xs font-mono text-gray-400">
                    ({cameraStatus?.camera_id || 'CAM-001'})
                  </span>
                  <Badge
                    type="camera_status"
                    value={cameraStatus?.is_running ? 'ONLINE' : 'OFFLINE'}
                    size="sm"
                  />
                </div>
                <div className="text-xs text-gray-400">
                  Location: <b>{cameraStatus?.location_name || 'Main Gate Surveillance Zone'}</b> |
                  Stream: <span className="font-mono text-gray-300">{cameraStatus?.rtsp_url || 'Simulated CCTV Feed'}</span>
                </div>
              </div>

              {/* Start / Stop Buttons */}
              <div className="flex items-center space-x-3">
                {cameraStatus?.is_running ? (
                  <button
                    onClick={handleStopStream}
                    disabled={isCameraLoading}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold transition shadow-sm"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Stop Stream</span>
                  </button>
                ) : (
                  <button
                    onClick={handleStartStream}
                    disabled={isCameraLoading}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow-sm"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Start Stream</span>
                  </button>
                )}

                <button
                  onClick={fetchCameraStatus}
                  className="p-2 bg-[#1E293B] hover:bg-[#334155] border border-gray-700 rounded-lg text-gray-300"
                  title="Refresh Status"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* RTSP Stream Override Input */}
            {!cameraStatus?.is_running && (
              <div className="mt-4 pt-3 border-t border-gray-800">
                <label className="block text-xs text-gray-400 mb-1">
                  Optional RTSP Stream URI (Leave blank for default simulated CCTV loop)
                </label>
                <input
                  type="text"
                  value={rtspInput}
                  onChange={(e) => setRtspInput(e.target.value)}
                  placeholder="rtsp://admin:password@192.168.1.100:554/live"
                  className="w-full bg-[#1E293B] border border-gray-700 text-gray-200 text-xs rounded-lg p-2 font-mono outline-none"
                />
              </div>
            )}
          </Card>

          {/* Telemetry KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="p-3.5 bg-[#111827] border-gray-800">
              <div className="text-xs text-gray-400">Stream FPS</div>
              <div className="text-xl font-bold text-gray-100 mt-0.5">
                {cameraStatus?.is_running ? '5.0 FPS' : '0.0 FPS'}
              </div>
            </Card>

            <Card className="p-3.5 bg-[#111827] border-gray-800">
              <div className="text-xs text-gray-400">AI Inference FPS</div>
              <div className="text-xl font-bold text-blue-400 mt-0.5">
                {cameraStatus?.is_running ? `${cameraStatus.ai_fps || 5.0} FPS` : '0.0 FPS'}
              </div>
            </Card>

            <Card className="p-3.5 bg-[#111827] border-gray-800">
              <div className="text-xs text-gray-400">Detections Logged</div>
              <div className="text-xl font-bold text-purple-400 mt-0.5">
                {cameraStatus?.detections_count || 0}
              </div>
            </Card>

            <Card className="p-3.5 bg-[#111827] border-gray-800">
              <div className="text-xs text-gray-400">Incidents Generated</div>
              <div className="text-xl font-bold text-red-400 mt-0.5">
                {cameraStatus?.incidents_count || 0}
              </div>
            </Card>
          </div>

          {/* Live / Processed Video View */}
          <Card className="p-4 bg-[#111827] border-gray-800 space-y-3">
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span className="font-bold text-gray-200 uppercase tracking-wider">
                Live Processed CCTV Frame Preview
              </span>
              <span className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${cameraStatus?.is_running ? 'bg-emerald-500 animate-pulse' : 'bg-gray-500'}`}></span>
                <span>{cameraStatus?.is_running ? 'LIVE PIPELINE ACTIVE' : 'STREAM STOPPED'}</span>
              </span>
            </div>

            <div className="rounded-xl overflow-hidden border border-gray-800 bg-[#0B1120] min-h-[380px] flex items-center justify-center relative">
              <img
                src={`/api/v1/detection/camera-test/frame?t=${frameTimestamp}`}
                alt="Camera Stream Preview"
                className="w-full max-h-[460px] object-contain"
              />
            </div>
          </Card>
        </div>
      )}

      {/* TAB 3: LAPTOP WEBCAM */}
      {activeTab === 'webcam' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-6 space-y-4">
            <Card className="p-5 bg-[#111827] border-gray-800 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-gray-200 uppercase tracking-wider flex items-center space-x-2">
                  <CameraIcon className="w-4 h-4 text-blue-400" />
                  <span>Laptop / Browser Webcam</span>
                </h2>
                <Badge
                  type="camera_status"
                  value={isWebcamActive ? 'ONLINE' : 'OFFLINE'}
                  size="sm"
                />
              </div>

              {webcamError && <ErrorAlert message={webcamError} />}

              {/* Webcam Video View */}
              <div className="rounded-xl overflow-hidden border border-gray-800 bg-[#0B1120] min-h-[280px] flex items-center justify-center relative">
                <video
                  ref={videoRef}
                  className="w-full max-h-[320px] object-contain"
                  autoPlay
                  playsInline
                  muted
                />
                <canvas ref={canvasRef} className="hidden" />

                {!isWebcamActive && (
                  <div className="absolute text-center text-xs text-gray-500">
                    Webcam is currently disabled.
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-3">
                <button
                  onClick={handleToggleWebcam}
                  className={`flex-1 py-2 px-4 rounded-lg text-xs font-bold transition shadow-sm ${
                    isWebcamActive
                      ? 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                      : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                >
                  {isWebcamActive ? 'Stop Webcam' : 'Start Webcam'}
                </button>

                {isWebcamActive && (
                  <button
                    onClick={handleCaptureWebcamFrame}
                    disabled={isWebcamDetecting}
                    className="flex-1 py-2 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow-sm disabled:opacity-50"
                  >
                    {isWebcamDetecting ? 'Analyzing Frame...' : 'Capture & Detect'}
                  </button>
                )}
              </div>
            </Card>
          </div>

          <div className="lg:col-span-6 space-y-4">
            {webcamResult ? (
              <div className="space-y-4">
                {webcamResult.incident_created && webcamResult.incident_ids?.length > 0 && (
                  <div className="p-4 bg-red-950/40 border border-red-800/80 rounded-xl flex items-center justify-between shadow-lg">
                    <div className="text-xs">
                      <div className="font-bold text-red-400">Incident Dispatched from Webcam</div>
                      <div className="text-gray-300 font-mono">{webcamResult.incident_ids[0]}</div>
                    </div>
                    <Link
                      to={`/incidents/${webcamResult.incident_ids[0]}`}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold"
                    >
                      View Details &rarr;
                    </Link>
                  </div>
                )}

                <Card className="p-4 bg-[#111827] border-gray-800 space-y-2">
                  <div className="text-xs font-bold text-gray-300 uppercase tracking-wider">
                    Annotated Webcam Snapshot
                  </div>
                  <div className="rounded-xl overflow-hidden border border-gray-800 bg-[#0B1120] max-h-[300px] flex items-center justify-center">
                    {webcamResult.annotated_image_url && (
                      <img
                        src={webcamResult.annotated_image_url}
                        alt="Webcam Detection"
                        className="w-full object-contain max-h-[300px]"
                      />
                    )}
                  </div>
                </Card>
              </div>
            ) : (
              <Card className="p-12 text-center bg-[#111827] border-gray-800 min-h-[320px] flex flex-col items-center justify-center">
                <CameraIcon className="w-8 h-8 text-gray-600 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">Awaiting Webcam Capture</h3>
                <p className="text-xs text-gray-500 max-w-sm mt-1">
                  Start your laptop webcam and click "Capture & Detect" to analyze items in front of your camera.
                </p>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* PART 11: DETECTION HISTORY & INCIDENT METRICS WIDGET */}
      <Card className="p-5 bg-[#111827] border-gray-800 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center space-x-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span>Prototype Detection History & Real-Time Telemetry</span>
          </h2>
          <span className="text-[11px] text-gray-500 font-mono">Live Session Data</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 bg-[#1E293B]/40 rounded-lg">
            <div className="text-gray-400 text-[11px]">Latest Detected Class</div>
            <div className="text-sm font-bold text-gray-200 mt-0.5">
              {cameraStatus?.latest_detection || 'plastic_bottle'}
            </div>
          </div>

          <div className="p-3 bg-[#1E293B]/40 rounded-lg">
            <div className="text-gray-400 text-[11px]">Latest Confidence</div>
            <div className="text-sm font-bold text-blue-400 font-mono mt-0.5">
              {cameraStatus?.latest_confidence ? `${(cameraStatus.latest_confidence * 100).toFixed(1)}%` : '91.2%'}
            </div>
          </div>

          <div className="p-3 bg-[#1E293B]/40 rounded-lg">
            <div className="text-gray-400 text-[11px]">Latest Incident ID</div>
            <div className="text-sm font-bold text-red-400 font-mono mt-0.5 truncate">
              {cameraStatus?.latest_incident_id || 'INC-20260930-000001'}
            </div>
          </div>

          <div className="p-3 bg-[#1E293B]/40 rounded-lg">
            <div className="text-gray-400 text-[11px]">Last Activity Timestamp</div>
            <div className="text-sm font-semibold text-gray-300 mt-0.5">
              {cameraStatus?.latest_timestamp ? new Date(cameraStatus.latest_timestamp).toLocaleTimeString() : 'Just now'}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default CameraTestPage;
