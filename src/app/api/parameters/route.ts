import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');
const CONFIG_PATH = path.join(SCRAPER_DIR, 'config.json');

const DEFAULT_PARAMS = {
  CONFERENCE_HEADER: 'International Conference on Advances in Computer Research on Science Engineering and Technology, 2026',
  FOOTER_URL: 'www.acroset.in',
  LINE_SPACING_FACTOR: 1.45,
  WORD_SPACING: 1.5,
  TITLE_FONT_SIZE: 12,
  AUTHORS_FONT_SIZE: 9.5,
  ABSTRACT_FONT_SIZE: 10,
  KEYWORDS_FONT_SIZE: 10,
  HEADER_FONT_SIZE: 8.5,
  FOOTER_URL_FONT_SIZE: 9,
  FOOTER_PAGE_FONT_SIZE: 10,
};

export async function GET() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
      const params = JSON.parse(raw);
      return NextResponse.json({ params });
    }
    return NextResponse.json({ params: DEFAULT_PARAMS });
  } catch {
    return NextResponse.json({ params: DEFAULT_PARAMS });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate — ensure all expected keys are present
    const params = { ...DEFAULT_PARAMS };
    for (const key of Object.keys(DEFAULT_PARAMS) as (keyof typeof DEFAULT_PARAMS)[]) {
      if (body[key] !== undefined) {
        (params as Record<string, unknown>)[key] = body[key];
      }
    }

    fs.writeFileSync(CONFIG_PATH, JSON.stringify(params, null, 2));

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
