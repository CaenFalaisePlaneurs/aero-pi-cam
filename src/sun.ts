import SunCalc from 'suncalc';
import type { LocationConfig } from './config.js';

export interface SunTimes {
  sunrise: Date;
  sunset: Date;
}

export function getSunTimes(date: Date, location: LocationConfig): SunTimes {
  const times = SunCalc.getTimes(date, location.latitude, location.longitude);
  return {
    sunrise: times.sunrise,
    sunset: times.sunset,
  };
}

export function isDay(date: Date, location: LocationConfig): boolean {
  const times = getSunTimes(date, location);
  return date >= times.sunrise && date < times.sunset;
}

export function getNextCaptureInterval(
  date: Date,
  location: LocationConfig,
  dayIntervalMinutes: number,
  nightIntervalMinutes: number
): number {
  return isDay(date, location) ? dayIntervalMinutes : nightIntervalMinutes;
}
