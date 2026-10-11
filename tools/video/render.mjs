import { spawn, execFileSync } from 'node:child_process';
import { readFile, writeFile, mkdir, stat } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { launchBrowser } from './browser.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const artifacts = path.resolve(directory, '../../artifacts');
await mkdir(artifacts, { recursive: true });
const scenes = JSON.parse(await readFile(path.join(directory, 'scenes.json'), 'utf8'));
const probe = (file) =>
  JSON.parse(
    execFileSync(
      'ffprobe',
      ['-v', 'error', '-show_entries', 'format=duration', '-of', 'json', file],
      { encoding: 'utf8' },
    ),
  ).format.duration * 1;
// Keep the narration uncut. A small uniform tempo adjustment can fit a two-minute film.
const durations = scenes.map((s) => probe(path.join(directory, 'audio', `${s.id}.wav`)));
const rawTotal = scenes.reduce((total, s, i) => total + Math.max(s.minimum, durations[i] + 1.1), 0);
const tempo = rawTotal > 118 ? Math.min(1.22, rawTotal / 116) : 1;
const timeline = {
  duration: 0,
  fps: 30,
  width: 1920,
  height: 1080,
  tempo,
  scenes: [],
  captions: [],
};
let srt = '';
let number = 0;
function timestamp(seconds) {
  const ms = Math.round(seconds * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
}
scenes.forEach((scene, i) => {
  const audioDuration = durations[i] / tempo;
  const length = Math.max(scene.minimum / tempo, audioDuration + 1.05);
  const start = timeline.duration,
    end = start + length;
  timeline.scenes.push({ ...scene, start, end, audioDuration });
  timeline.duration = end;
  const words = scene.text.split(/\s+/);
  const phrases = [];
  // Keep sentence boundaries intact so a short tail never joins the next sentence.
  for (const sentence of scene.text.match(/[^.!?]+[.!?]*/g) || []) {
    let phrase = [];
    for (const word of sentence.trim().split(/\s+/)) {
      if ([...phrase, word].join(' ').length > 84 && phrase.length) {
        phrases.push(phrase);
        phrase = [];
      }
      phrase.push(word);
    }
    if (phrase.length) phrases.push(phrase);
  }
  let consumed = 0;
  for (const phrase of phrases) {
    const a = start + 0.3 + (audioDuration * consumed) / words.length;
    consumed += phrase.length;
    const b = start + 0.3 + (audioDuration * consumed) / words.length;
    const text = phrase.join(' ');
    timeline.captions.push({ start: a, end: b, text });
    srt += `${++number}\n${timestamp(a)} --> ${timestamp(b)}\n${text}\n\n`;
  }
});
await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2));
await writeFile(path.join(artifacts, 'wildmon-walkthrough.srt'), srt);
await writeFile(
  path.join(artifacts, 'wildmon-narration.md'),
  '# Wildmon walkthrough narration\n\n' +
    scenes
      .map(
        (s, i) => `## ${timestamp(timeline.scenes[i].start).slice(0, 8)} — ${s.label}\n\n${s.text}`,
      )
      .join('\n\n') +
    '\n',
);
execFileSync('python3', [path.join(directory, 'assemble_audio.py')], { stdio: 'inherit' });
const movie = path.join(artifacts, 'wildmon-walkthrough.mp4');
const repair = process.argv.includes('--repair-tail');
const master = path.join(directory, 'audio', 'video-master.mp4');
const prefix = path.join(directory, 'audio', 'video-prefix.mp4');
const tail = path.join(directory, 'audio', 'video-tail.mp4');
const frames = Math.ceil(timeline.duration * timeline.fps);
let startFrame = 0;
if (repair) {
  startFrame = Number(
    JSON.parse(
      execFileSync(
        'ffprobe',
        [
          '-v',
          'error',
          '-select_streams',
          'v:0',
          '-show_entries',
          'stream=nb_frames',
          '-of',
          'json',
          movie,
        ],
        { encoding: 'utf8' },
      ),
    ).streams[0].nb_frames,
  );
  if (!Number.isInteger(startFrame) || startFrame >= frames)
    throw new Error('No missing tail frames to repair');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', movie, '-an', '-c:v', 'copy', prefix]);
}
const mime = {
  '.html': 'text/html',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
};
const server = http.createServer(async (req, res) => {
  try {
    const file = path.resolve(
      directory,
      `.${decodeURIComponent(new URL(req.url, 'http://localhost').pathname)}`,
    );
    if (!file.startsWith(directory + path.sep)) throw new Error('Invalid path');
    const content = await readFile(file);
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream' });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end();
  }
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const browser = await launchBrowser(1920, 1080);
try {
  await browser.navigate(`http://127.0.0.1:${server.address().port}/film.html`);
  await browser.evaluate('window.ready');
  if (process.argv.includes('--preview')) {
    for (const scene of timeline.scenes) {
      await browser.evaluate(`window.renderAt(${scene.start + (scene.end - scene.start) * 0.6})`);
      const image = await browser.call('Page.captureScreenshot', { format: 'png' });
      await writeFile(
        path.join(artifacts, `preview-${scene.id}.png`),
        Buffer.from(image.data, 'base64'),
      );
    }
    console.log(
      `Preview ready: ${timeline.duration.toFixed(1)} seconds, tempo ${tempo.toFixed(3)}.`,
    );
  } else {
    const ffmpeg = spawn(
      'ffmpeg',
      [
        '-y',
        '-loglevel',
        'error',
        '-f',
        'image2pipe',
        '-framerate',
        '30',
        '-vcodec',
        'mjpeg',
        '-i',
        'pipe:0',
        '-c:v',
        'libx264',
        '-preset',
        'fast',
        '-crf',
        '18',
        '-pix_fmt',
        'yuv420p',
        '-movflags',
        '+faststart',
        repair ? tail : master,
      ],
      { stdio: ['pipe', 'ignore', 'pipe'] },
    );
    let ffmpegError = '';
    ffmpeg.stderr.on('data', (data) => (ffmpegError += data));
    const complete = new Promise((resolve, reject) => {
      ffmpeg.once('error', reject);
      ffmpeg.once('close', (code) => (code === 0 ? resolve() : reject(new Error(ffmpegError))));
    });
    for (let frame = startFrame; frame < frames; frame++) {
      await browser.evaluate(`window.renderAt(${frame / timeline.fps})`);
      const image = await browser.call('Page.captureScreenshot', {
        format: 'jpeg',
        quality: 94,
        optimizeForSpeed: true,
      });
      if (!ffmpeg.stdin.write(Buffer.from(image.data, 'base64'))) await once(ffmpeg.stdin, 'drain');
      if (frame % 300 === 0)
        console.log(
          `Rendered ${((frame / frames) * 100).toFixed(0)}% (${Math.floor(frame / 30)} / ${Math.ceil(timeline.duration)}s)`,
        );
    }
    ffmpeg.stdin.end();
    await complete;
    if (repair) {
      const list = path.join(directory, 'audio', 'video-parts.txt');
      await writeFile(
        list,
        [prefix, tail].map((file) => `file '${file.replaceAll("'", "'\\''")}'`).join('\n') + '\n',
      );
      execFileSync('ffmpeg', [
        '-y',
        '-loglevel',
        'error',
        '-f',
        'concat',
        '-safe',
        '0',
        '-i',
        list,
        '-c:v',
        'copy',
        master,
      ]);
    }
    execFileSync('ffmpeg', [
      '-y',
      '-loglevel',
      'error',
      '-i',
      master,
      '-i',
      path.join(directory, 'audio', 'narration.wav'),
      '-map',
      '0:v',
      '-map',
      '1:a',
      '-c:v',
      'copy',
      '-c:a',
      'aac',
      '-ar',
      '48000',
      '-b:a',
      '192k',
      '-movflags',
      '+faststart',
      '-shortest',
      movie,
    ]);
    const actual = probe(movie);
    if (Math.abs(actual - timeline.duration) > 0.08)
      throw new Error(`Video duration mismatch: ${actual} vs ${timeline.duration}`);
    const size = await stat(movie);
    console.log(
      `Finished ${timeline.duration.toFixed(1)}s, ${(size.size / 1024 / 1024).toFixed(1)} MB`,
    );
  }
} finally {
  await browser.close();
  server.close();
}
