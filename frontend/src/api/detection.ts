import { apiClient } from './client';
import {
  ImageDetectionResponse,
  VideoProcessResponse,
  CameraTestStatusResponse,
} from '../types/detection';

export const detectImage = async (formData: FormData): Promise<ImageDetectionResponse> => {
  const response = await apiClient.post<ImageDetectionResponse>('/detection/image', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 30000,
  });
  return response.data;
};

export const processVideo = async (formData: FormData): Promise<VideoProcessResponse> => {
  const response = await apiClient.post<VideoProcessResponse>('/detection/video', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 60000,
  });
  return response.data;
};

export const startCameraTest = async (data: {
  camera_id?: string;
  camera_name?: string;
  stream_source?: string;
}): Promise<any> => {
  const formData = new FormData();
  if (data.camera_id) formData.append('camera_id', data.camera_id);
  if (data.camera_name) formData.append('camera_name', data.camera_name);
  if (data.stream_source) formData.append('stream_source', data.stream_source);

  const response = await apiClient.post('/detection/camera-test/start', formData);
  return response.data;
};

export const stopCameraTest = async (): Promise<any> => {
  const response = await apiClient.post('/detection/camera-test/stop');
  return response.data;
};

export const getCameraTestStatus = async (): Promise<CameraTestStatusResponse> => {
  const response = await apiClient.get<CameraTestStatusResponse>('/detection/camera-test/status');
  return response.data;
};
