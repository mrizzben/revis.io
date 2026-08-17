import apiClient from '../client';
import type {
  RegisterRequest,
  TokenResponse,
  User,
  ForgotPasswordRequest,
  ResetPasswordRequest,
} from '../../types';

export async function register(data: RegisterRequest): Promise<{ id: number; message: string }> {
  const response = await apiClient.post('/auth/register', data);
  return response.data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);
  const response = await apiClient.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
}

export async function refresh(): Promise<TokenResponse> {
  const response = await apiClient.post('/auth/refresh');
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function forgotPassword(data: ForgotPasswordRequest): Promise<{ message: string }> {
  const response = await apiClient.post('/auth/forgot-password', data);
  return response.data;
}

export async function resetPassword(data: ResetPasswordRequest): Promise<{ message: string }> {
  const response = await apiClient.post('/auth/reset-password', data);
  return response.data;
}

export async function verifyEmail(token: string): Promise<{ message: string }> {
  const response = await apiClient.post(`/auth/verify-email/${token}`);
  return response.data;
}

export async function getProviders(): Promise<{ google: boolean }> {
  const response = await apiClient.get('/auth/providers');
  return response.data;
}


export async function getMe(): Promise<User> {
  const response = await apiClient.get('/users/me');
  return response.data;
}
