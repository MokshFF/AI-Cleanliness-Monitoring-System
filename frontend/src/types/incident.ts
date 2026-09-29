/** Incident types matching FastAPI incident schemas. */

export type IncidentStatus = 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';
export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type WasteType = 'SOLID' | 'LIQUID';

export interface Incident {
  incident_id: string;
  camera_id: string;
  waste_type: WasteType;
  category: string;
  confidence: number;
  snapshot_path: string;
  timestamp: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  bounding_box?: [number, number, number, number];
  mask_polygon?: number[][];
  affected_area_percentage?: number;
  track_id?: number;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  resolved_at?: string;
}

export interface IncidentFilterParams {
  camera_id?: string;
  status?: IncidentStatus;
  severity?: IncidentSeverity;
  waste_type?: WasteType;
  category?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export interface IncidentPaginationResponse {
  items: Incident[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface IncidentStatusUpdate {
  status: IncidentStatus;
  notes?: string;
}
