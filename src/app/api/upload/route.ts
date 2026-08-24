import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');
const INCOMPLETE_DIR = path.join(SCRAPER_DIR, 'IncompletePDF');

export async function POST(request: NextRequest) {
  try {
    if (!fs.existsSync(INCOMPLETE_DIR)) {
      fs.mkdirSync(INCOMPLETE_DIR, { recursive: true });
    }

    const formData = await request.formData();
    const files = formData.getAll('files') as File[];

    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'No files uploaded' }, { status: 400 });
    }

    const savedFiles: string[] = [];

    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        continue;
      }
      const safeName = path.basename(file.name);
      const filePath = path.join(INCOMPLETE_DIR, safeName);
      const buffer = Buffer.from(await file.arrayBuffer());
      fs.writeFileSync(filePath, buffer);
      savedFiles.push(safeName);
    }

    return NextResponse.json({
      success: true,
      message: `Uploaded ${savedFiles.length} file(s)`,
      files: savedFiles,
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to upload files', details: String(error) },
      { status: 500 }
    );
  }
}
