/* This module is the untyped boundary with the external backend API. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { API } from '../constants'

/**
 * Thin typed fetch wrapper for the backend API.
 *
 * - Base URL and timeout come from src/constants (env-overridable).
 * - Throws on network errors / non-2xx / timeout; callers decide how to
 *   handle failure (typically by falling back to mock data).
 */
export interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers?: Record<string, string>
  body?: any
  timeoutMs?: number
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', headers = {}, body, timeoutMs = API.timeoutMs } = options
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...headers,
  }

  let requestBody: string | undefined = undefined
  if (body !== undefined) {
    requestHeaders['Content-Type'] = 'application/json'
    requestBody = JSON.stringify(body)
  }

  try {
    const response = await fetch(`${API.baseUrl}${path}`, {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`)
    }

    return (await response.json()) as T
  } finally {
    window.clearTimeout(timer)
  }
}
