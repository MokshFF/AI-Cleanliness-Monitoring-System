import { apiClient } from './client';
import { AnalyticsFilterParams } from '../types/analytics';

const triggerFileDownload = (blobData: Blob, defaultFilename: string) => {
  const url = window.URL.createObjectURL(blobData);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', defaultFilename);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
};

export const downloadCsvReport = async (filters: AnalyticsFilterParams = {}): Promise<void> => {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id) params.camera_id = filters.camera_id;
  if (filters.waste_type) params.waste_type = filters.waste_type;
  if (filters.category) params.category = filters.category;
  if (filters.severity) params.severity = filters.severity;
  if (filters.status) params.status = filters.status;

  const response = await apiClient.get('/reports/incidents.csv', {
    params,
    responseType: 'blob',
  });

  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  triggerFileDownload(new Blob([response.data], { type: 'text/csv' }), `incidents_export_${today}.csv`);
};

export const downloadPdfReport = async (filters: AnalyticsFilterParams = {}): Promise<void> => {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id) params.camera_id = filters.camera_id;
  if (filters.waste_type) params.waste_type = filters.waste_type;
  if (filters.category) params.category = filters.category;
  if (filters.severity) params.severity = filters.severity;
  if (filters.status) params.status = filters.status;

  const response = await apiClient.get('/reports/incidents.pdf', {
    params,
    responseType: 'blob',
  });

  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  triggerFileDownload(
    new Blob([response.data], { type: 'application/pdf' }),
    `municipal_cleanliness_report_${today}.pdf`
  );
};
