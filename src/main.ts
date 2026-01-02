import cron from 'node-cron';
import { loadConfig, type Config } from './config.js';
import { captureFrame } from './capture.js';
import { uploadImage, type UploadMetadata } from './upload.js';
import { isDay } from './sun.js';
import { fetchMetar, formatMetarOverlay } from './metar.js';
import { addTextOverlay } from './overlay.js';

const CONFIG_PATH = process.env['CONFIG_PATH'] ?? 'config.yaml';

let config: Config;
let currentSchedule: cron.ScheduledTask | null = null;
let isRunning = false;

async function captureAndUpload(): Promise<void> {
  if (isRunning) {
    console.log('Previous capture still in progress, skipping...');
    return;
  }

  isRunning = true;
  const captureTime = new Date();
  const isDayTime = isDay(captureTime, config.location);

  console.log(
    `[${captureTime.toISOString()}] Starting capture (${isDayTime ? 'day' : 'night'} mode)`
  );

  try {
    // Capture frame from camera
    const captureResult = captureFrame(config.camera.rtsp_url);

    if (!captureResult.success || !captureResult.image) {
      console.error(`Capture failed: ${captureResult.error}`);
      return;
    }

    console.log(`Captured image: ${captureResult.image.length} bytes`);

    let imageBuffer = captureResult.image;

    // Add METAR overlay if enabled
    if (config.metar.enabled) {
      const metarResult = await fetchMetar(config.metar.icao_code);

      if (metarResult.success && metarResult.data) {
        const overlayText = formatMetarOverlay(metarResult.data);
        console.log(`METAR overlay: ${overlayText}`);

        try {
          imageBuffer = await addTextOverlay(imageBuffer, overlayText, config.metar);
          console.log(`Added overlay, new size: ${imageBuffer.length} bytes`);
        } catch (err) {
          console.error(`Overlay failed: ${err instanceof Error ? err.message : String(err)}`);
          // Continue with original image
        }
      } else {
        console.warn(`METAR fetch failed: ${metarResult.error}`);
        if (metarResult.retryAfterSeconds) {
          console.warn(`Retry after ${metarResult.retryAfterSeconds} seconds`);
        }
        // Continue without overlay
      }
    }

    // Upload image
    const metadata: UploadMetadata = {
      captureTimestamp: captureTime,
      locationName: config.location.name,
      isDay: isDayTime,
    };

    const uploadResult = await uploadImage(imageBuffer, metadata, config.api);

    if (uploadResult.success) {
      console.log(`Upload successful: ${uploadResult.responseBody?.id}`);
    } else {
      console.error(`Upload failed: ${uploadResult.error}`);
    }
  } catch (err) {
    console.error(`Unexpected error: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    isRunning = false;
  }
}

function scheduleNextCapture(): void {
  const now = new Date();
  const isDayTime = isDay(now, config.location);
  const intervalMinutes = isDayTime
    ? config.schedule.day_interval_minutes
    : config.schedule.night_interval_minutes;

  // Stop existing schedule
  if (currentSchedule) {
    currentSchedule.stop();
  }

  // Schedule capture every N minutes
  const cronExpression = `*/${intervalMinutes} * * * *`;
  console.log(
    `Scheduling captures every ${intervalMinutes} minutes (${isDayTime ? 'day' : 'night'} mode)`
  );

  currentSchedule = cron.schedule(cronExpression, () => {
    void captureAndUpload();
  });

  // Re-evaluate schedule at sunrise and sunset
  scheduleTransitionCheck();
}

function scheduleTransitionCheck(): void {
  // Check every 5 minutes if we need to switch between day/night schedules
  cron.schedule('*/5 * * * *', () => {
    // Re-evaluate and reschedule if needed (handles day/night transitions)
    if (currentSchedule) {
      scheduleNextCapture();
    }
  });
}

function shutdown(signal: string): void {
  console.log(`\nReceived ${signal}, shutting down gracefully...`);

  if (currentSchedule) {
    currentSchedule.stop();
  }

  process.exit(0);
}

function main(): void {
  console.log('Webcam Capture Service starting...');
  console.log(`Loading config from: ${CONFIG_PATH}`);

  try {
    config = loadConfig(CONFIG_PATH);
  } catch (err) {
    console.error(`Failed to load config: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }

  console.log(
    `Location: ${config.location.name} (${config.location.latitude}, ${config.location.longitude})`
  );
  console.log(`Camera: ${config.camera.rtsp_url.replace(/:[^:@]+@/, ':***@')}`);
  console.log(`API: ${config.api.url}`);
  console.log(
    `Schedule: ${config.schedule.day_interval_minutes}min (day) / ${config.schedule.night_interval_minutes}min (night)`
  );
  console.log(
    `METAR overlay: ${config.metar.enabled ? `enabled (${config.metar.icao_code})` : 'disabled'}`
  );

  // Register shutdown handlers
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Run initial capture
  console.log('Running initial capture...');
  void captureAndUpload();

  // Start scheduled captures
  scheduleNextCapture();

  console.log('Service running. Press Ctrl+C to stop.');
}

main();
