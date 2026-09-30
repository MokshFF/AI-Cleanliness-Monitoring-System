/** Types for GIS Map, Longitudinal Analytics, and Reporting matching Phase 9 backend schemas. */
import { CameraStatus, DetectionMode } from './camera';
import { IncidentSeverity, IncidentStatus, WasteType } from './incident';

export interface CameraMapItem {
  camera_id: string;
  name: string;
  location_name: string;
  latitude: number;
  longitude: number;
  status: CameraStatus;
  detection_mode: DetectionMode;
  is_active: boolean;
}

export interface IncidentMapItem {
  incident_id: string;
  camera_id: string;
  camera_name: string;
  location_name: string;
  latitude: number;
  longitude: number;
  waste_type: WasteType;
  category: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  confidence: number;
  timestamp: string;
}

export interface TrendDataPoint {
  date: string;
  count: number;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface CameraCount {
  camera_id: string;
  camera_name: string;
  count: number;
  active_count: number;
  high_severity_count: number;
}

export interface LocationCount {
  location_name: string;
  count: number;
  solid_count: number;
  liquid_count: number;
  active_count: number;
}

export interface AnalyticsSummaryResponse {
  total_incidents: number;
  active_incidents: number;
  resolved_incidents: number;
  dismissed_incidents: number;
  resolution_rate: number;
  waste_type_breakdown: Record<string, number>;
  category_breakdown: CategoryCount[];
  severity_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  camera_breakdown: CameraCount[];
  location_breakdown: LocationCount[];
  trend: TrendDataPoint[];
}

export interface AnalyticsFilterParams {
  start_date?: string;
  end_date?: string;
  camera_id?: string;
  waste_type?: WasteType;
  category?: string;
  severity?: IncidentSeverity;
  status?: IncidentStatus;
}
