/** Types matching FastAPI single-image and camera prototype detection schemas. */

export interface DetectionItem {
  class_name: string;
  waste_type: 'SOLID' | 'LIQUID';
  confidence: number;
  bbox?: [number, number, number, number];
  mask_polygon?: number[][];
  affected_area_percentage?: number;
  affected_area_pixels?: number;
}

export interface ImageDetectionResponse {
  success: boolean;
  image_id: string;
  camera_id: string;
  location_name: string;
  detections: DetectionItem[];
  incident_created: boolean;
  incident_ids: string[];
  annotated_image_url?: string;
  processing_time_ms: number;
}

export interface VideoProcessResponse {
  success: boolean;
  video_name: string;
  camera_id: string;
  frames_processed: number;
  detections_count: number;
  incident_created: boolean;
  incident_ids: string[];
  processing_fps: number;
  duration_seconds: number;
  annotated_frame_url?: string;
}

export interface CameraTestStatusResponse {
  is_running: boolean;
  camera_id: string;
  camera_name: string;
  location_name: string;
  status: string;
  fps: number;
  ai_fps: number;
  detections_count: number;
  incidents_count: number;
  latest_detection?: string;
  latest_incident_id?: string;
  latest_confidence?: number;
  latest_timestamp?: string;
  rtsp_url?: string;
}
