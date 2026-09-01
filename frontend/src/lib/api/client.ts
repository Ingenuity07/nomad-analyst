/**
 * Nomad Analyst Central REST API Client
 * Features:
 * - Base URL configuration via import.meta.env
 * - Canonical Error Envelope normalization
 * - Request timeout & abort controller support
 * - Strict type-safety
 */

import { ApiErrorResponse } from './types';

export class ApiError extends Error {
  public code: string;
  public details: Record<string, any>;
  public timestamp: string;
  public status: number;

  constructor(code: string, message: string, details: Record<string, any> = {}, timestamp: string = '', status: number = 500) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
    this.timestamp = timestamp || new Date().toISOString();
    this.status = status;
  }
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined | null>;
}

const DEFAULT_TIMEOUT_MS = 15000;
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, params, headers = {}, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const mergedHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...headers,
  };

  try {
    const response = await fetch(url, {
      ...customConfig,
      headers: mergedHeaders,
      signal: customConfig.signal || controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      if (isJson && data && typeof data === 'object' && 'error' in data) {
        const errObj = (data as ApiErrorResponse).error;
        throw new ApiError(
          errObj.code || 'API_ERROR',
          errObj.message || response.statusText,
          errObj.details || {},
          errObj.timestamp,
          response.status
        );
      }
      throw new ApiError(
        'HTTP_ERROR',
        typeof data === 'string' ? data : response.statusText,
        {},
        new Date().toISOString(),
        response.status
      );
    }

    return data as T;
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new ApiError('REQUEST_TIMEOUT', `Request timed out after ${timeoutMs}ms`, {}, new Date().toISOString(), 408);
    }
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError('NETWORK_ERROR', error.message || 'Network communication error', {}, new Date().toISOString(), 0);
  }
}
