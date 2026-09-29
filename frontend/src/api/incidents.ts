import { apiClient } from './client';
import {
  Incident,
  IncidentFilterParams,
  IncidentPaginationResponse,
  IncidentStatusUpdate,
} from '../types/incident';

export const incidentApi = {
  getIncidents: async (params?: IncidentFilterParams): Promise<IncidentPaginationResponse> => {
    const response = await apiClient.get<IncidentPaginationResponse>('/incidents/', { params });
    return response.data;
  },

  getIncidentById: async (incidentId: string): Promise<Incident> => {
    const response = await apiClient.get<Incident>(`/incidents/${encodeURIComponent(incidentId)}`);
    return response.data;
  },

  updateIncidentStatus: async (
    incidentId: string,
    update: IncidentStatusUpdate
  ): Promise<Incident> => {
    const response = await apiClient.patch<Incident>(
      `/incidents/${encodeURIComponent(incidentId)}/status`,
      update
    );
    return response.data;
  },

  fetchSnapshotBlob: async (incidentId: string): Promise<string> => {
    const response = await apiClient.get(
      `/incidents/${encodeURIComponent(incidentId)}/snapshot`,
      { responseType: 'blob' }
    );
    return URL.createObjectURL(response.data);
  },
};
