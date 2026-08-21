import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');

export async function POST() {
  return new Promise<NextResponse>((resolve) => {
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const cmd = `cd "${SCRAPER_DIR}" && ${pythonCmd} scraper.py`;

    exec(cmd, { maxBuffer: 10 * 1024 * 1024, timeout: 120000 }, (error, stdout, stderr) => {
      const output = stdout + (stderr ? '\n' + stderr : '');

      if (error) {
        resolve(NextResponse.json({
          success: false,
          error: error.message,
          output,
        }));
        return;
      }

      resolve(NextResponse.json({
        success: true,
        output,
        outputFile: 'compiled_output.pdf',
      }));
    });
  });
}
