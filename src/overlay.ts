import sharp from 'sharp';
import { readFileSync } from 'node:fs';
import type { MetarConfig } from './config.js';

type Gravity = 'northwest' | 'northeast' | 'southwest' | 'southeast';

function positionToGravity(position: MetarConfig['overlay_position']): Gravity {
  const mapping: Record<MetarConfig['overlay_position'], Gravity> = {
    'top-left': 'northwest',
    'top-right': 'northeast',
    'bottom-left': 'southwest',
    'bottom-right': 'southeast',
  };
  return mapping[position];
}

async function loadIcon(config: MetarConfig['icon']): Promise<Buffer | null> {
  if (!config) {
    return null;
  }

  let svgContent: string;

  if (config.svg) {
    // Inline SVG provided
    svgContent = config.svg;
  } else if (config.path) {
    // Local file path
    svgContent = readFileSync(config.path, 'utf-8');
  } else if (config.url) {
    // Fetch from URL
    const response = await fetch(config.url);
    if (!response.ok) {
      console.warn(`Failed to fetch icon from ${config.url}: ${response.status}`);
      return null;
    }
    svgContent = await response.text();
  } else {
    return null;
  }

  // Resize SVG to specified size
  const size = config.size ?? 24;
  const resizedSvg = wrapSvgWithSize(svgContent, size, size);

  return Buffer.from(resizedSvg);
}

function wrapSvgWithSize(svgContent: string, width: number, height: number): string {
  // Extract viewBox or create one
  const viewBoxMatch = svgContent.match(/viewBox=["']([^"']+)["']/);
  const viewBox = viewBoxMatch ? viewBoxMatch[1] : `0 0 ${width} ${height}`;

  // Remove existing width/height attributes and wrap
  const cleaned = svgContent
    .replace(/width=["'][^"']*["']/gi, '')
    .replace(/height=["'][^"']*["']/gi, '')
    .replace(/viewBox=["'][^"']*["']/gi, '')
    .replace(/<svg[^>]*>/gi, '')
    .replace(/<\/svg>/gi, '');

  return `<svg width="${width}" height="${height}" viewBox="${viewBox}" xmlns="http://www.w3.org/2000/svg">${cleaned}</svg>`;
}

export async function addTextOverlay(
  imageBuffer: Buffer,
  text: string,
  config: MetarConfig
): Promise<Buffer> {
  const image = sharp(imageBuffer);
  const metadata = await image.metadata();

  const width = metadata.width ?? 1920;
  const padding = 10;
  const lineHeight = config.font_size + 4;
  const iconSize = config.icon?.size ?? 24;
  const iconSpacing = config.icon ? iconSize + 8 : 0;
  const estimatedTextWidth = text.length * (config.font_size * 0.6);
  const boxWidth = Math.min(estimatedTextWidth + padding * 2 + iconSpacing, width - 20);
  const boxHeight = Math.max(lineHeight + padding * 2, iconSize + padding * 2);

  // Load icon if configured
  const iconBuffer = await loadIcon(config.icon);
  const iconX = config.icon?.position === 'right' ? boxWidth - iconSize - padding : padding;
  const iconY = (boxHeight - iconSize) / 2;
  const textX = config.icon?.position === 'left' ? iconSize + padding + 4 : padding;

  // Extract icon SVG content and prepare for embedding
  let iconSvgContent = '';
  if (iconBuffer) {
    const iconSvg = iconBuffer.toString('utf-8');
    // Extract viewBox for proper scaling
    const viewBoxMatch = iconSvg.match(/viewBox=["']([^"']+)["']/);
    const viewBox = viewBoxMatch ? viewBoxMatch[1] : '0 0 24 24';
    
    // Remove outer svg tags and extract inner content
    const innerMatch = iconSvg.match(/<svg[^>]*>(.*?)<\/svg>/s);
    if (innerMatch && innerMatch[1]) {
      iconSvgContent = innerMatch[1];
    } else {
      iconSvgContent = iconSvg;
    }

    // Wrap icon in a group with proper viewBox
    iconSvgContent = `<svg viewBox="${viewBox}" width="${iconSize}" height="${iconSize}" xmlns="http://www.w3.org/2000/svg">${iconSvgContent}</svg>`;
  }

  // Create SVG text overlay with background and embedded icon
  const svg = `
    <svg width="${boxWidth}" height="${boxHeight}" xmlns="http://www.w3.org/2000/svg">
      <rect 
        x="0" 
        y="0" 
        width="${boxWidth}" 
        height="${boxHeight}" 
        fill="${config.background_color}"
        rx="4"
        ry="4"
      />
      ${iconSvgContent ? `<foreignObject x="${iconX}" y="${iconY}" width="${iconSize}" height="${iconSize}">${iconSvgContent}</foreignObject>` : ''}
      <text 
        x="${textX}" 
        y="${boxHeight - padding - 2}" 
        font-family="monospace" 
        font-size="${config.font_size}" 
        fill="${config.font_color}"
      >${escapeXml(text)}</text>
    </svg>
  `;

  const overlayBuffer = Buffer.from(svg);
  const gravity = positionToGravity(config.overlay_position);

  return image
    .composite([
      {
        input: overlayBuffer,
        gravity,
      },
    ])
    .jpeg({ quality: 90 })
    .toBuffer();
}

function escapeXml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
