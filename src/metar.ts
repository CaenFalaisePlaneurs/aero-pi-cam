const USER_AGENT = 'webcam-cfp/1.0 (Raspberry Pi webcam capture)';
const API_BASE_URL = 'https://aviationweather.gov/api/data/metar';

export interface MetarData {
  icaoId: string;
  receiptTime: string;
  obsTime: number;
  reportTime: string;
  temp: number;
  dewp: number;
  wdir: number;
  wspd: number;
  visib: string;
  altim: number;
  metarType: string;
  rawOb: string;
  lat: number;
  lon: number;
  elev: number;
  name: string;
  cover?: string;
  clouds: Array<{ cover: string; base: number }>;
  fltCat: string;
  rawTaf?: string;
  wxString?: string;
}

export interface MetarResult {
  success: boolean;
  data?: MetarData;
  error?: string;
  retryAfterSeconds?: number;
}

export async function fetchMetar(icaoCode: string): Promise<MetarResult> {
  const url = `${API_BASE_URL}?ids=${icaoCode}&format=json&taf=true&hours=1`;

  try {
    const response = await fetch(url, {
      headers: {
        'User-Agent': USER_AGENT,
      },
    });

    // Handle 204 No Content
    if (response.status === 204) {
      return {
        success: false,
        error: 'No METAR data available',
      };
    }

    // Handle 429 Too Many Requests
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      const waitSeconds = retryAfter ? parseInt(retryAfter, 10) : 60;
      return {
        success: false,
        error: 'Rate limited by Aviation Weather API',
        retryAfterSeconds: waitSeconds,
      };
    }

    // Handle 400 Bad Request
    if (response.status === 400) {
      return {
        success: false,
        error: 'Invalid METAR request',
      };
    }

    // Handle other non-success responses
    if (!response.ok) {
      return {
        success: false,
        error: `METAR API error: HTTP ${response.status}`,
      };
    }

    const data = (await response.json()) as MetarData[];

    if (!data || data.length === 0) {
      return {
        success: false,
        error: 'No METAR data in response',
      };
    }

    // Return the most recent METAR (first in array)
    return {
      success: true,
      data: data[0],
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export function formatMetarOverlay(metar: MetarData): string {
  // Format: "LFRK 021530Z 33009KT VFR 4°C"
  const parts: string[] = [];

  // Extract time from rawOb (e.g., "021530Z")
  const timeMatch = metar.rawOb.match(/\d{6}Z/);
  if (timeMatch) {
    parts.push(`${metar.icaoId} ${timeMatch[0]}`);
  } else {
    parts.push(metar.icaoId);
  }

  // Wind
  if (metar.wdir !== undefined && metar.wspd !== undefined) {
    parts.push(`${String(metar.wdir).padStart(3, '0')}/${metar.wspd}kt`);
  }

  // Flight category
  parts.push(metar.fltCat);

  // Temperature
  if (metar.temp !== undefined) {
    parts.push(`${metar.temp}°C`);
  }

  return parts.join(' | ');
}
