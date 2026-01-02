import type { ApiConfig } from './config.js';

export interface UploadResult {
  success: boolean;
  statusCode?: number;
  responseBody?: UploadResponse;
  error?: string;
}

export interface UploadResponse {
  id: string;
  received_at: string;
  size_bytes: number;
}

export interface UploadMetadata {
  captureTimestamp: Date;
  locationName: string;
  isDay: boolean;
}

const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 1000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function uploadImage(
  imageBuffer: Buffer,
  metadata: UploadMetadata,
  apiConfig: ApiConfig
): Promise<UploadResult> {
  let lastError: string | undefined;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const result = await attemptUpload(imageBuffer, metadata, apiConfig);

      if (result.success) {
        return result;
      }

      // Don't retry on client errors (4xx except 429)
      if (
        result.statusCode &&
        result.statusCode >= 400 &&
        result.statusCode < 500 &&
        result.statusCode !== 429
      ) {
        return result;
      }

      lastError = result.error;
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
    }

    if (attempt < MAX_RETRIES) {
      const backoffMs = INITIAL_BACKOFF_MS * Math.pow(2, attempt - 1);
      console.log(`Upload attempt ${attempt} failed, retrying in ${backoffMs}ms...`);
      await sleep(backoffMs);
    }
  }

  return {
    success: false,
    error: `All ${MAX_RETRIES} upload attempts failed. Last error: ${lastError}`,
  };
}

async function attemptUpload(
  imageBuffer: Buffer,
  metadata: UploadMetadata,
  apiConfig: ApiConfig
): Promise<UploadResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), apiConfig.timeout_seconds * 1000);

  try {
    const response = await fetch(apiConfig.url, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${apiConfig.key}`,
        'Content-Type': 'image/jpeg',
        'X-Capture-Timestamp': metadata.captureTimestamp.toISOString(),
        'X-Location': metadata.locationName,
        'X-Is-Day': String(metadata.isDay),
      },
      body: imageBuffer,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.status === 201) {
      const body = (await response.json()) as UploadResponse;
      return {
        success: true,
        statusCode: response.status,
        responseBody: body,
      };
    }

    const errorText = await response.text();
    return {
      success: false,
      statusCode: response.status,
      error: `HTTP ${response.status}: ${errorText}`,
    };
  } catch (err) {
    clearTimeout(timeoutId);

    if (err instanceof Error && err.name === 'AbortError') {
      return {
        success: false,
        error: `Request timeout after ${apiConfig.timeout_seconds}s`,
      };
    }

    throw err;
  }
}
