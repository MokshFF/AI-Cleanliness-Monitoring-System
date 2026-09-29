import { apiClient } from './client';
import { User, UserCreateInput, UserUpdateInput } from '../types/auth';

export const userApi = {
  getUsers: async (params?: { skip?: number; limit?: number }): Promise<User[]> => {
    const response = await apiClient.get<User[]>('/users/', { params });
    return response.data;
  },

  getUserById: async (userId: string): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${encodeURIComponent(userId)}`);
    return response.data;
  },

  createUser: async (data: UserCreateInput): Promise<User> => {
    const response = await apiClient.post<User>('/users/', data);
    return response.data;
  },

  updateUser: async (userId: string, data: UserUpdateInput): Promise<User> => {
    const response = await apiClient.patch<User>(`/users/${encodeURIComponent(userId)}`, data);
    return response.data;
  },
};
