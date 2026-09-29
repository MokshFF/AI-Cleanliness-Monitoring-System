/** Authentication and User types matching FastAPI schemas. */

export type UserRole = 'ADMIN' | 'OPERATOR' | 'SUPERVISOR';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  last_login?: string;
}

export interface LoginCredentials {
  username?: string;
  email?: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UserCreateInput {
  email: string;
  username?: string;
  full_name?: string;
  role?: UserRole;
  password: string;
  is_active?: boolean;
}

export interface UserUpdateInput {
  email?: string;
  full_name?: string;
  role?: UserRole;
  password?: string;
  is_active?: boolean;
}
