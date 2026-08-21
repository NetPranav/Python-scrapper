import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');
const COMPLETED_DIR = path.join(SCRAPER_DIR, 'CompletedPDF');

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const fileName = searchParams.get('file');

  if (!fileName) {
    return NextResponse.json({ error: 'Missing file parameter' }, { status: 400 });
  }

  const safeName = path.basename(fileName); // prevent path traversal
  const filePath = path.join(COMPLETED_DIR, safeName);

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: 'File not found' }, { status: 404 });
  }

  const fileBuffer = fs.readFileSync(filePath);

  const ext = path.extname(safeName).toLowerCase();
  let contentType = 'application/octet-stream';
  if (ext === '.pdf') contentType = 'application/pdf';
  else if (ext === '.docx') contentType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

  return new NextResponse(fileBuffer, {
    headers: {
      'Content-Type': contentType,
      'Content-Disposition': `attachment; filename="${safeName}"`,
    },
  });
}
