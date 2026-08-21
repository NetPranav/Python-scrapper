import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');
const INCOMPLETE_DIR = path.join(SCRAPER_DIR, 'IncompletePDF');

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const fileName = searchParams.get('file');

  // Serve a specific PDF file for preview
  if (fileName) {
    const safeName = path.basename(fileName); // prevent path traversal
    const filePath = path.join(INCOMPLETE_DIR, safeName);

    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'File not found' }, { status: 404 });
    }

    const fileBuffer = fs.readFileSync(filePath);
    return new NextResponse(fileBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `inline; filename="${safeName}"`,
      },
    });
  }

  // List all PDFs in IncompletePDF
  try {
    if (!fs.existsSync(INCOMPLETE_DIR)) {
      fs.mkdirSync(INCOMPLETE_DIR, { recursive: true });
    }

    const files = fs.readdirSync(INCOMPLETE_DIR)
      .filter(f => f.toLowerCase().endsWith('.pdf'))
      .sort()
      .map(name => {
        const stats = fs.statSync(path.join(INCOMPLETE_DIR, name));
        return {
          name,
          size: stats.size,
          sizeFormatted: formatSize(stats.size),
        };
      });

    return NextResponse.json({ files });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to list PDFs', details: String(error) },
      { status: 500 }
    );
  }
}
