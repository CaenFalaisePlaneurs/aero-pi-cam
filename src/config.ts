import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { z } from 'zod';

const CameraConfigSchema = z.object({
  rtsp_url: z.string().url().startsWith('rtsp://'),
});

const LocationConfigSchema = z.object({
  name: z.string().min(1),
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  timezone: z.string().min(1),
});

const ScheduleConfigSchema = z.object({
  day_interval_minutes: z.number().int().min(1).max(1440),
  night_interval_minutes: z.number().int().min(1).max(1440),
});

const ApiConfigSchema = z.object({
  url: z.string().url(),
  key: z.string().min(1),
  timeout_seconds: z.number().int().min(1).max(300),
});

const MetarConfigSchema = z.object({
  enabled: z.boolean(),
  icao_code: z.string().length(4).toUpperCase(),
  overlay_position: z.enum(['top-left', 'top-right', 'bottom-left', 'bottom-right']),
  font_size: z.number().int().min(8).max(72),
  font_color: z.string().min(1),
  background_color: z.string().min(1),
  icon: z
    .object({
      url: z.string().url().optional(),
      path: z.string().optional(),
      svg: z.string().optional(),
      size: z.number().int().min(8).max(128).default(24),
      position: z.enum(['left', 'right']).default('left'),
    })
    .optional(),
});

const ConfigSchema = z.object({
  camera: CameraConfigSchema,
  location: LocationConfigSchema,
  schedule: ScheduleConfigSchema,
  api: ApiConfigSchema,
  metar: MetarConfigSchema,
});

export type Config = z.infer<typeof ConfigSchema>;
export type CameraConfig = z.infer<typeof CameraConfigSchema>;
export type LocationConfig = z.infer<typeof LocationConfigSchema>;
export type ScheduleConfig = z.infer<typeof ScheduleConfigSchema>;
export type ApiConfig = z.infer<typeof ApiConfigSchema>;
export type MetarConfig = z.infer<typeof MetarConfigSchema>;

export function loadConfig(configPath: string): Config {
  const fileContents = readFileSync(configPath, 'utf-8');
  const parsed: unknown = parse(fileContents);
  return ConfigSchema.parse(parsed);
}

export function validateConfig(config: unknown): Config {
  return ConfigSchema.parse(config);
}
