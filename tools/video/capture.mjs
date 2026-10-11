import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchBrowser, pause } from './browser.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const assets = path.join(directory, 'assets');
const origin = process.env.WILDMON_ORIGIN || 'http://localhost:3000';
await mkdir(assets, { recursive: true });
if (!process.env.WILDMON_VIDEO_LOGIN_FILE)
  throw new Error('Set WILDMON_VIDEO_LOGIN_FILE to a private temporary JSON file.');
const login = JSON.parse(await readFile(process.env.WILDMON_VIDEO_LOGIN_FILE, 'utf8'));
const browser = await launchBrowser(1440, 900);
async function api(route) {
  return browser.evaluate(
    `fetch('/api/v1${route}', {credentials:'include'}).then(async r => {if(!r.ok)throw new Error('API '+r.status);return r.json()})`,
  );
}
async function screenshot(name, route) {
  if (route) await browser.navigate(origin + route);
  const expected = {
    landing: 'Step out.',
    dashboard: 'Hello,',
    collection: 'Your collection',
    capture: 'Quick capture',
    'capture-preview': 'Submit discovery',
    'hunt-setup': 'Start hunt',
    'hunt-active': 'Your hunt is on',
    'hunt-summary': 'Hunt summary',
    challenges: 'Friend challenges',
    'challenge-builder': 'Create a challenge',
    ecosystems: 'Ecosystem packs',
    'ecosystem-detail': 'Explore over time',
    badges: 'Badges',
    leaderboard: 'Leaderboard',
    'leaderboard-alltime': 'Leaderboard',
  }[name];
  if (expected) {
    let loaded = false;
    for (let attempt = 0; attempt < 180; attempt++) {
      loaded = await browser.evaluate(
        `document.body.innerText.toLowerCase().includes(${JSON.stringify(expected.toLowerCase())})`,
      );
      if (loaded) break;
      await pause(500);
    }
    if (!loaded) throw new Error(`App screen did not load: ${name}`);
  }
  await pause(2200);
  // Hide development tooling, never any product states or data.
  await browser.evaluate(
    `(() => {const s=document.createElement('style');s.textContent='nextjs-portal{display:none!important}';document.head.append(s);return true})()`,
  );
  await browser.evaluate(
    `Promise.all([...document.images].map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r}))).then(()=>true)`,
  );
  const shot = await browser.call('Page.captureScreenshot', { format: 'png' });
  await writeFile(path.join(assets, `${name}.png`), Buffer.from(shot.data, 'base64'));
  console.log(`Captured ${name}`);
}
try {
  await screenshot('landing', '/');
  const status = await browser.evaluate(
    `fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(${JSON.stringify(login)})}).then(r=>r.status)`,
  );
  if (status !== 200) throw new Error(`Login failed (${status}); credentials were not logged.`);
  const profile = await api('/me');
  const collection = await api('/collection');
  const packs = await api('/ecosystems');
  const challenges = await api('/challenges');
  const metadata = {
    captured_at: new Date().toISOString(),
    xp: profile.xp,
    discoveries: collection.map(
      ({ common_name, scientific_name, category, status, xp_awarded }) => ({
        common_name,
        scientific_name,
        category,
        status,
        xp_awarded,
      }),
    ),
    challenge_count: challenges.length,
    packs: packs.map(({ slug, name }) => ({ slug, name })),
  };
  await writeFile(path.join(assets, 'capture-metadata.json'), JSON.stringify(metadata, null, 2));
  console.log(
    `Real collection: ${collection.length} verified records; ${challenges.length} existing challenges.`,
  );
  await screenshot('dashboard', '/dashboard');
  await screenshot('collection', '/collection');
  await screenshot('capture', '/capture');
  const usable = collection.find((item) => item.image_url);
  if (usable) {
    const image = await browser.evaluate(
      `fetch(${JSON.stringify(usable.image_url)},{credentials:'include'}).then(r=>r.blob()).then(b=>new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.readAsDataURL(b)}))`,
    );
    await writeFile(path.join(assets, 'discovery.jpg'), Buffer.from(image.split(',')[1], 'base64'));
    // Only load a preview. The image is not resubmitted and no identification is fabricated.
    await browser.evaluate(
      `fetch(${JSON.stringify(image)}).then(r=>r.blob()).then(blob=>{const d=new DataTransfer();d.items.add(new File([blob],'nature-photo.jpg',{type:blob.type}));const input=document.querySelector('input[type=file]');input.files=d.files;input.dispatchEvent(new Event('change',{bubbles:true}));return true})`,
    );
    await screenshot('capture-preview');
  }
  await screenshot('hunt-setup', '/hunts');
  // An actual short demonstration session, finished immediately without invented rewards.
  await browser.evaluate(
    `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Start hunt').click()`,
  );
  await pause(3000);
  if (!(await browser.evaluate('location.pathname')).match(/^\/hunts\/[^/]+$/))
    throw new Error('Hunt did not start');
  await screenshot('hunt-active');
  await browser.evaluate(
    `[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Finish hunt')).click()`,
  );
  await pause(2500);
  await screenshot('hunt-summary');
  await screenshot('challenges', '/challenges');
  await screenshot('challenge-builder', '/challenges/new');
  if (challenges.length) await screenshot('challenge-detail', `/challenges/${challenges[0].id}`);
  await screenshot('ecosystems', '/ecosystems');
  if (packs.length) await screenshot('ecosystem-detail', `/ecosystems/${packs[0].slug}`);
  await screenshot('badges', '/badges');
  await screenshot('leaderboard', '/leaderboard');
  await browser.evaluate(
    `const button=[...document.querySelectorAll('button')].find(b=>b.textContent.includes('All time'));if(button)button.click();true`,
  );
  await screenshot('leaderboard-alltime');
  await copyFile(
    path.join(
      directory,
      '../../apps/web/node_modules/geist/dist/fonts/geist-sans/Geist-Regular.woff2',
    ),
    path.join(assets, 'geist.woff2'),
  );
  await copyFile(
    path.join(directory, '../../apps/web/public/wildmon-hero.jpg'),
    path.join(assets, 'hero.jpg'),
  );
} finally {
  await browser.close();
}
