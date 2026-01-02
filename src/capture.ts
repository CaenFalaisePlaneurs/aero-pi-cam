import { spawnSync, type SpawnSyncReturns } from 'node:child_process';

export interface CaptureResult {
  success: boolean;
  image?: Buffer;
  error?: string;
}

export interface SpawnSyncFn {
  (command: string, args: string[], options: object): SpawnSyncReturns<Buffer>;
}

// Dependency injection for testing
let spawnSyncImpl: SpawnSyncFn = spawnSync as SpawnSyncFn;

export function setSpawnSync(impl: SpawnSyncFn): void {
  spawnSyncImpl = impl;
}

export function resetSpawnSync(): void {
  spawnSyncImpl = spawnSync as SpawnSyncFn;
}

export function captureFrame(rtspUrl: string): CaptureResult {
  const args = [
    '-rtsp_transport',
    'tcp',
    '-i',
    rtspUrl,
    '-frames:v',
    '1',
    '-q:v',
    '2',
    '-f',
    'image2',
    'pipe:1',
  ];

  const result = spawnSyncImpl('ffmpeg', args, {
    timeout: 30000, // 30 second timeout
    maxBuffer: 10 * 1024 * 1024, // 10MB buffer for image
  });

  if (result.error) {
    return {
      success: false,
      error: `ffmpeg spawn error: ${result.error.message}`,
    };
  }

  if (result.status !== 0) {
    const stderr = result.stderr?.toString() || 'Unknown error';
    return {
      success: false,
      error: `ffmpeg exited with code ${result.status}: ${stderr}`,
    };
  }

  if (!result.stdout || result.stdout.length === 0) {
    return {
      success: false,
      error: 'ffmpeg produced no output',
    };
  }

  return {
    success: true,
    image: result.stdout,
  };
}
