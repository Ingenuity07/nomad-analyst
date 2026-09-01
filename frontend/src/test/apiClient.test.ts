import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiClient, ApiError } from '../lib/api/client';

describe('apiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('successfully fetches and parses JSON', async () => {
    const mockData = { symbol: 'RELIANCE', price: 1309.0 };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockData,
    });

    const result = await apiClient<{ symbol: string; price: number }>('/api/v1/stocks/RELIANCE/');
    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/stocks/RELIANCE/', expect.anything());
  });

  it('appends query parameters cleanly', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ results: [] }),
    });

    await apiClient('/api/v1/opportunities/', {
      params: { universe: 'NIFTY50', limit: 10, empty: null },
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/opportunities/?universe=NIFTY50&limit=10',
      expect.anything()
    );
  });

  it('normalizes backend canonical error envelopes', async () => {
    const errorPayload = {
      error: {
        code: 'RESOURCE_NOT_FOUND',
        message: "Stock symbol 'UNKNOWN' not found.",
        details: {},
        timestamp: '2026-09-01T12:00:00Z',
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => errorPayload,
    });

    await expect(apiClient('/api/v1/stocks/UNKNOWN/')).rejects.toThrow(ApiError);
    try {
      await apiClient('/api/v1/stocks/UNKNOWN/');
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.code).toBe('RESOURCE_NOT_FOUND');
      expect(err.message).toBe("Stock symbol 'UNKNOWN' not found.");
      expect(err.status).toBe(404);
    }
  });
});
