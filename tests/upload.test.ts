import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { uploadImage, type UploadMetadata } from '../src/upload.js';
import type { ApiConfig } from '../src/config.js';

// Mock global fetch
const mockFetch = jest.fn<typeof fetch>();
global.fetch = mockFetch;

describe('upload', () => {
  const apiConfig: ApiConfig = {
    url: 'https://api.example.com/api/webcam/image',
    key: 'test-api-key',
    timeout_seconds: 30,
  };

  const metadata: UploadMetadata = {
    captureTimestamp: new Date('2026-01-02T15:30:00Z'),
    locationName: 'LFAS',
    isDay: true,
  };

  const imageBuffer = Buffer.from('fake-jpeg-data');

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should return success on 201 response', async () => {
    const responseBody = {
      id: 'test-uuid',
      received_at: '2026-01-02T15:30:05Z',
      size_bytes: 245000,
    };

    mockFetch.mockResolvedValueOnce({
      status: 201,
      ok: true,
      json: async () => responseBody,
      text: async () => JSON.stringify(responseBody),
    } as Response);

    const result = await uploadImage(imageBuffer, metadata, apiConfig);

    expect(result.success).toBe(true);
    expect(result.statusCode).toBe(201);
    expect(result.responseBody).toEqual(responseBody);
  });

  it('should send correct headers', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 201,
      ok: true,
      json: async () => ({ id: 'test', received_at: '', size_bytes: 0 }),
    } as Response);

    await uploadImage(imageBuffer, metadata, apiConfig);

    expect(mockFetch).toHaveBeenCalledWith(
      apiConfig.url,
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({
          Authorization: 'Bearer test-api-key',
          'Content-Type': 'image/jpeg',
          'X-Capture-Timestamp': '2026-01-02T15:30:00.000Z',
          'X-Location': 'LFAS',
          'X-Is-Day': 'true',
        }),
        body: imageBuffer,
      })
    );
  });

  it('should return error on 4xx response without retry', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 400,
      ok: false,
      text: async () => 'Bad Request',
    } as Response);

    const result = await uploadImage(imageBuffer, metadata, apiConfig);

    expect(result.success).toBe(false);
    expect(result.statusCode).toBe(400);
    expect(result.error).toContain('HTTP 400');
    // Should not retry on 4xx
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('should retry on 5xx response', async () => {
    mockFetch
      .mockResolvedValueOnce({
        status: 500,
        ok: false,
        text: async () => 'Internal Server Error',
      } as Response)
      .mockResolvedValueOnce({
        status: 201,
        ok: true,
        json: async () => ({ id: 'test', received_at: '', size_bytes: 0 }),
      } as Response);

    const result = await uploadImage(imageBuffer, metadata, apiConfig);

    expect(result.success).toBe(true);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('should retry on 429 response', async () => {
    mockFetch
      .mockResolvedValueOnce({
        status: 429,
        ok: false,
        text: async () => 'Too Many Requests',
      } as Response)
      .mockResolvedValueOnce({
        status: 201,
        ok: true,
        json: async () => ({ id: 'test', received_at: '', size_bytes: 0 }),
      } as Response);

    const result = await uploadImage(imageBuffer, metadata, apiConfig);

    expect(result.success).toBe(true);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('should fail after max retries', async () => {
    mockFetch.mockResolvedValue({
      status: 500,
      ok: false,
      text: async () => 'Internal Server Error',
    } as Response);

    const result = await uploadImage(imageBuffer, metadata, apiConfig);

    expect(result.success).toBe(false);
    expect(result.error).toContain('All 3 upload attempts failed');
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});
