import { apiClient } from './client';
import { Camera, CameraCreateInput, CameraUpdateInput } from '../types/camera';

export const cameraApi = {
  getCameras: async (params?: { skip?: number; limit?: number; is_active?: boolean }): Promise<Camera[]> => {
    const response = await apiClient.get<Camera[]>('/cameras/', { params });
    return response.data;
  },

  getCameraById: async (cameraId: string): Promise<Camera> => {
    const response = await apiClient.get<Camera>(`/cameras/${encodeURIComponent(cameraId)}`);
    return response.data;
  },

  createCamera: async (data: CameraCreateInput): Promise<Camera> => {
    const response = await apiClient.post<Camera>('/cameras/', data);
    return response.data;
  },

  updateCamera: async (cameraId: string, data: CameraUpdateInput): Promise<Camera> => {
    const response = await apiClient.patch<Camera>(`/cameras/${encodeURIComponent(cameraId)}`, data);
    return response.data;
  },

  deleteCamera: async (cameraId: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/cameras/${encodeURIComponent(cameraId)}`);
    return response.data;
  },
};
