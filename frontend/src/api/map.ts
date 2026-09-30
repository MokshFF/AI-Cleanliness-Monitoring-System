import { apiClient } from './client';
import { CameraMapItem, IncidentMapItem } from '../types/analytics';
import { IncidentSeverity, IncidentStatus, WasteType } from '../types/incident';

export interface MapIncidentFilters {
  camera_id?: string;
  waste_type?: WasteType;
  severity?: IncidentSeverity;
  status?: IncidentStatus;
  category?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export const getMapCameras = async (isActive?: boolean): Promise<CameraMapItem[]> => {
  const params: Record<string, any> = {};
  if (isActive !== undefined) {
    params.is_active = isActive;
  }
  const response = await apiClient.get<CameraMapItem[]>('/map/cameras', { params });
  return response.data;
};

export const getMapIncidents = async (filters: MapIncidentFilters = {}): Promise<IncidentMapItem[]> => {
  const params: Record<string, any> = {};
  if (filters.camera_id) params.camera_id = filters.camera_id;
  if (filters.waste_type) params.waste_type = filters.waste_type;
  if (filters.severity) params.severity = filters.severity;
  if (filters.status) params.status = filters.status;
  if (filters.category) params.category = filters.category;
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.limit) params.limit = filters.limit;

  const response = await apiClient.get<IncidentMapItem[]>('/map/incidents', { params });
  return response.data;
};
