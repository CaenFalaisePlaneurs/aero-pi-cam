import { describe, it, expect } from '@jest/globals';
import { validateConfig } from '../src/config.js';

describe('config', () => {
  const validConfig = {
    camera: {
      rtsp_url: 'rtsp://user:pass@192.168.0.60:554/stream1',
    },
    location: {
      name: 'LFAS',
      latitude: 48.9267952,
      longitude: -0.1477169,
      timezone: 'Europe/Paris',
    },
    schedule: {
      day_interval_minutes: 5,
      night_interval_minutes: 60,
    },
    api: {
      url: 'https://api.example.com/api/webcam/image',
      key: 'secret-key',
      timeout_seconds: 30,
    },
    metar: {
      enabled: true,
      icao_code: 'LFRK',
      overlay_position: 'bottom-left',
      font_size: 16,
      font_color: 'white',
      background_color: 'rgba(0,0,0,0.6)',
    },
  };

  it('should validate a correct config', () => {
    const result = validateConfig(validConfig);
    expect(result.camera.rtsp_url).toBe(validConfig.camera.rtsp_url);
    expect(result.location.name).toBe('LFAS');
    expect(result.metar.icao_code).toBe('LFRK');
  });

  it('should reject invalid RTSP URL', () => {
    const invalidConfig = {
      ...validConfig,
      camera: { rtsp_url: 'http://invalid' },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should reject invalid latitude', () => {
    const invalidConfig = {
      ...validConfig,
      location: { ...validConfig.location, latitude: 100 },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should reject invalid longitude', () => {
    const invalidConfig = {
      ...validConfig,
      location: { ...validConfig.location, longitude: 200 },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should reject invalid schedule interval', () => {
    const invalidConfig = {
      ...validConfig,
      schedule: { day_interval_minutes: 0, night_interval_minutes: 60 },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should reject invalid ICAO code length', () => {
    const invalidConfig = {
      ...validConfig,
      metar: { ...validConfig.metar, icao_code: 'LF' },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should reject invalid overlay position', () => {
    const invalidConfig = {
      ...validConfig,
      metar: { ...validConfig.metar, overlay_position: 'center' },
    };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });

  it('should uppercase ICAO code', () => {
    const configWithLowercase = {
      ...validConfig,
      metar: { ...validConfig.metar, icao_code: 'lfrk' },
    };
    const result = validateConfig(configWithLowercase);
    expect(result.metar.icao_code).toBe('LFRK');
  });
});
