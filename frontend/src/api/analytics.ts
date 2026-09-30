import { apiClient } from './client';
import { AnalyticsFilterParams, AnalyticsSummaryResponse } from '../types/analytics';

export const getAnalyticsSummary = async (
  filters: AnalyticsFilterParams = {}
): Promise<AnalyticsSummaryResponse> => {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id) params.camera_id = filters.camera_id;
  if (filters.waste_type) params.waste_type = filters.waste_type;
  if (filters.category) params.category = filters.category;
  if (filters.severity) params.severity = filters.severity;
  if (filters.status) params.status = filters.status;

  const response = await apiClient.get<AnalyticsSummaryResponse>('/analytics/summary', { params });
  return response.data;
};
