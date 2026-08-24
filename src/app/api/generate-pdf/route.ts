import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';

const SCRAPER_DIR = path.join(process.cwd(), 'scraper');

export async function POST() {
  return new Promise<NextResponse>((resolve) => {
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const cmd = `${pythonCmd} scraper.py`;

    exec(
      cmd,
      {
        cwd: SCRAPER_DIR,
        maxBuffer: 10 * 1024 * 1024,
        timeout: 120000,
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8',
          PYTHONUTF8: '1',
        },
      },
      (error, stdout, stderr) => {
        const output = stdout + (stderr ? '\n' + stderr : '');

        if (error) {
          resolve(
            NextResponse.json({
              success: false,
              error: error.message,
              output,
            })
          );
          return;
        }

        resolve(
          NextResponse.json({
            success: true,
            output,
            outputFile: 'compiled_output.pdf',
          })
        );
      }
    );
  });
}
