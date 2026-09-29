/** Camera types matching FastAPI camera schemas. */

export type CameraStatus = 'ONLINE' | 'OFFLINE' | 'ERROR' | 'CONNECTING';
export type DetectionMode = 'SOLID' | 'LIQUID' | 'BOTH';

export interface Camera {
  camera_id: string;
  name: string;
  location_name: string;
  latitude: number;
  longitude: number;
  status: CameraStatus;
  detection_mode: DetectionMode;
  target_fps: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  rtsp_url?: string; // Credential-masked
}

export interface CameraCreateInput {
  camera_id: string;
  name: string;
  location_name: string;
  latitude?: number;
  longitude?: number;
  rtsp_url: string;
  detection_mode: DetectionMode;
  target_fps?: number;
  is_active?: boolean;
}

export interface CameraUpdateInput {
  name?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  rtsp_url?: string;
  status?: CameraStatus;
  detection_mode?: DetectionMode;
  target_fps?: number;
  is_active?: boolean;
}
