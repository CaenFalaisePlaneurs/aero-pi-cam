import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { fetchMetar, formatMetarOverlay, type MetarData } from '../src/metar.js';

// Mock global fetch
const mockFetch = jest.fn<typeof fetch>();
global.fetch = mockFetch;

describe('metar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('fetchMetar', () => {
    const sampleMetar: MetarData = {
      icaoId: 'LFRK',
      receiptTime: '2026-01-02T15:34:14.873Z',
      obsTime: 1767367800,
      reportTime: '2026-01-02T15:30:00.000Z',
      temp: 4,
      dewp: -1,
      wdir: 330,
      wspd: 9,
      visib: '6+',
      altim: 1008,
      metarType: 'METAR',
      rawOb: 'METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG',
      lat: 49.18,
      lon: -0.456,
      elev: 66,
      name: 'Caen/Carpiquet Arpt, NO, FR',
      cover: 'FEW',
      clouds: [{ cover: 'FEW', base: 4100 }],
      fltCat: 'VFR',
      rawTaf: 'TAF LFRK 021400Z 0215/0224 34010KT 9999 BKN030',
    };

    it('should return METAR data on success', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => [sampleMetar],
      } as Response);

      const result = await fetchMetar('LFRK');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(sampleMetar);
    });

    it('should call API with correct URL and headers', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => [sampleMetar],
      } as Response);

      await fetchMetar('LFRK');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://aviationweather.gov/api/data/metar?ids=LFRK&format=json&taf=true&hours=1',
        expect.objectContaining({
          headers: {
            'User-Agent': expect.stringContaining('webcam-cfp'),
          },
        })
      );
    });

    it('should handle 204 No Content', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 204,
        ok: true,
      } as Response);

      const result = await fetchMetar('XXXX');

      expect(result.success).toBe(false);
      expect(result.error).toContain('No METAR data available');
    });

    it('should handle 429 rate limiting', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 429,
        ok: false,
        headers: new Headers({ 'Retry-After': '120' }),
      } as Response);

      const result = await fetchMetar('LFRK');

      expect(result.success).toBe(false);
      expect(result.error).toContain('Rate limited');
      expect(result.retryAfterSeconds).toBe(120);
    });

    it('should handle 400 Bad Request', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 400,
        ok: false,
      } as Response);

      const result = await fetchMetar('XX');

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid METAR request');
    });

    it('should handle empty response array', async () => {
      mockFetch.mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => [],
      } as Response);

      const result = await fetchMetar('LFRK');

      expect(result.success).toBe(false);
      expect(result.error).toContain('No METAR data in response');
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await fetchMetar('LFRK');

      expect(result.success).toBe(false);
      expect(result.error).toContain('Network error');
    });
  });

  describe('formatMetarOverlay', () => {
    it('should format METAR data for overlay', () => {
      const metar: MetarData = {
        icaoId: 'LFRK',
        receiptTime: '2026-01-02T15:34:14.873Z',
        obsTime: 1767367800,
        reportTime: '2026-01-02T15:30:00.000Z',
        temp: 4,
        dewp: -1,
        wdir: 330,
        wspd: 9,
        visib: '6+',
        altim: 1008,
        metarType: 'METAR',
        rawOb: 'METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG',
        lat: 49.18,
        lon: -0.456,
        elev: 66,
        name: 'Caen/Carpiquet Arpt, NO, FR',
        clouds: [],
        fltCat: 'VFR',
      };

      const overlay = formatMetarOverlay(metar);

      expect(overlay).toContain('LFRK');
      expect(overlay).toContain('021530Z');
      expect(overlay).toContain('330/9kt');
      expect(overlay).toContain('VFR');
      expect(overlay).toContain('4°C');
    });
  });
});
