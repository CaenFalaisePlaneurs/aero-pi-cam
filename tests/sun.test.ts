import { describe, it, expect } from '@jest/globals';
import { isDay, getSunTimes, getNextCaptureInterval } from '../src/sun.js';
import type { LocationConfig } from '../src/config.js';

describe('sun', () => {
  const location: LocationConfig = {
    name: 'LFAS',
    latitude: 48.9267952,
    longitude: -0.1477169,
    timezone: 'Europe/Paris',
  };

  describe('getSunTimes', () => {
    it('should return sunrise and sunset times', () => {
      const date = new Date('2026-06-21T12:00:00Z'); // Summer solstice
      const times = getSunTimes(date, location);

      expect(times.sunrise).toBeInstanceOf(Date);
      expect(times.sunset).toBeInstanceOf(Date);
      expect(times.sunset.getTime()).toBeGreaterThan(times.sunrise.getTime());
    });
  });

  describe('isDay', () => {
    it('should return true during daytime in summer', () => {
      // June 21, 2026 at noon UTC - definitely daytime in France
      const noonInSummer = new Date('2026-06-21T12:00:00Z');
      expect(isDay(noonInSummer, location)).toBe(true);
    });

    it('should return false during nighttime', () => {
      // January 2, 2026 at 3 AM UTC - definitely night in France
      const nightTime = new Date('2026-01-02T03:00:00Z');
      expect(isDay(nightTime, location)).toBe(false);
    });

    it('should return false at midnight', () => {
      const midnight = new Date('2026-06-21T00:00:00Z');
      expect(isDay(midnight, location)).toBe(false);
    });
  });

  describe('getNextCaptureInterval', () => {
    const dayInterval = 5;
    const nightInterval = 60;

    it('should return day interval during daytime', () => {
      const daytime = new Date('2026-06-21T12:00:00Z');
      const interval = getNextCaptureInterval(daytime, location, dayInterval, nightInterval);
      expect(interval).toBe(dayInterval);
    });

    it('should return night interval during nighttime', () => {
      const nighttime = new Date('2026-01-02T03:00:00Z');
      const interval = getNextCaptureInterval(nighttime, location, dayInterval, nightInterval);
      expect(interval).toBe(nightInterval);
    });
  });
});
