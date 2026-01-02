import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import type { SpawnSyncReturns } from 'node:child_process';
import { captureFrame, setSpawnSync, resetSpawnSync, type SpawnSyncFn } from '../src/capture.js';

describe('capture', () => {
  let mockSpawnSync: SpawnSyncFn;
  let lastCall: { command: string; args: string[]; options: object } | null = null;

  beforeEach(() => {
    lastCall = null;
  });

  afterEach(() => {
    resetSpawnSync();
  });

  function createMock(returnValue: SpawnSyncReturns<Buffer>): void {
    mockSpawnSync = (command: string, args: string[], options: object): SpawnSyncReturns<Buffer> => {
      lastCall = { command, args, options };
      return returnValue;
    };
    setSpawnSync(mockSpawnSync);
  }

  it('should return success with image buffer on successful capture', () => {
    const fakeImage = Buffer.from('fake-jpeg-data');
    createMock({
      status: 0,
      stdout: fakeImage,
      stderr: Buffer.from(''),
      pid: 1234,
      signal: null,
      output: [null, fakeImage, Buffer.from('')],
    });

    const result = captureFrame('rtsp://test:test@localhost:554/stream');

    expect(result.success).toBe(true);
    expect(result.image).toEqual(fakeImage);
    expect(result.error).toBeUndefined();
  });

  it('should return error on ffmpeg spawn failure', () => {
    createMock({
      status: null,
      stdout: Buffer.from(''),
      stderr: Buffer.from(''),
      error: new Error('spawn ffmpeg ENOENT'),
      pid: 0,
      signal: null,
      output: [null, Buffer.from(''), Buffer.from('')],
    });

    const result = captureFrame('rtsp://test:test@localhost:554/stream');

    expect(result.success).toBe(false);
    expect(result.error).toContain('spawn error');
    expect(result.image).toBeUndefined();
  });

  it('should return error on non-zero exit code', () => {
    createMock({
      status: 1,
      stdout: Buffer.from(''),
      stderr: Buffer.from('Connection refused'),
      pid: 1234,
      signal: null,
      output: [null, Buffer.from(''), Buffer.from('Connection refused')],
    });

    const result = captureFrame('rtsp://test:test@localhost:554/stream');

    expect(result.success).toBe(false);
    expect(result.error).toContain('exited with code 1');
    expect(result.error).toContain('Connection refused');
  });

  it('should return error when no output produced', () => {
    createMock({
      status: 0,
      stdout: Buffer.from(''),
      stderr: Buffer.from(''),
      pid: 1234,
      signal: null,
      output: [null, Buffer.from(''), Buffer.from('')],
    });

    const result = captureFrame('rtsp://test:test@localhost:554/stream');

    expect(result.success).toBe(false);
    expect(result.error).toContain('no output');
  });

  it('should call ffmpeg with correct arguments', () => {
    createMock({
      status: 0,
      stdout: Buffer.from('fake-data'),
      stderr: Buffer.from(''),
      pid: 1234,
      signal: null,
      output: [null, Buffer.from('fake-data'), Buffer.from('')],
    });

    const rtspUrl = 'rtsp://user:pass@192.168.0.60:554/stream1';
    captureFrame(rtspUrl);

    expect(lastCall).not.toBeNull();
    expect(lastCall?.command).toBe('ffmpeg');
    expect(lastCall?.args).toEqual([
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
    ]);
    expect(lastCall?.options).toMatchObject({
      timeout: 30000,
      maxBuffer: 10 * 1024 * 1024,
    });
  });
});
