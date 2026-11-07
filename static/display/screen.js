/* FrontDesk - the reception TV screen.
   Everything it shows comes from the server: settings (in the page), weather,
   prayer times and news (/api/...), and what to play (/api/screens/<slug>/state/,
   asked every few seconds). If the server is briefly unreachable the screen
   keeps showing and playing what it has. */
(() => {
'use strict';

const CONFIG = JSON.parse(document.getElementById('tv-config').textContent);
const TV = window.TV;
const ICON = window.TV_ICONS;
const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, '0');
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// ?motion=low calms the screen; ?motion=full keeps the motion even when the
// device asks for less (some TV boxes have "remove animations" switched on).
const MOTION = new URLSearchParams(location.search).get('motion');
const CALM = MOTION === 'low' || (MOTION !== 'full' && matchMedia('(prefers-reduced-motion: reduce)').matches);

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

/* ============ FIT ANY TV: designed at 1920x1080, scaled to the window ============ */
let scale = 1;
function fit() {
  scale = Math.min(innerWidth / 1920, innerHeight / 1080);
  const dash = $('dash');
  dash.style.transform = `scale(${scale})`;
  dash.style.left = `${(innerWidth - 1920 * scale) / 2}px`;
  dash.style.top = `${(innerHeight - 1080 * scale) / 2}px`;
  sizeParticles();
}
addEventListener('resize', fit);

/* ============ CLOCK (digits roll when they change) ============ */
let clockShown = '';
function drawClock(now) {
  const s = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const el = $('clock');
  if (!el.children.length) el.innerHTML = [...s].map(c => `<span${c === ':' ? ' class="sep"' : ''}>${c}</span>`).join('');
  [...s].forEach((c, i) => {
    if (c === clockShown[i] || c === ':') return;
    const span = el.children[i];
    span.textContent = c;
    if (!CALM) { span.classList.remove('roll'); void span.offsetWidth; span.classList.add('roll'); }
  });
  clockShown = s;
  const bar = $('sec-bar'), sec = now.getSeconds();
  bar.style.transition = sec === 0 ? 'none' : 'width 1s linear';
  bar.style.width = `${sec / 59 * 100}%`;
}

function tick() {
  const now = new Date();
  drawClock(now);
  $('date').textContent = now.toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  countdown(now);
  if ($('prayer-list')) prayerBanner(now);
  if (now.getSeconds() === 0) { refreshPrayerHighlights(now); applyAudio(); }
  if (now.getHours() === 0 && now.getMinutes() === 0 && now.getSeconds() === 5) { calHijri ? renderHijriCalendar() : renderCalendar(); fetchPrayer(); }
}

/* ============ PRAYER TIMES ============ */
const PRAYERS = [
  { key: 'Fajr', ar: 'الفجر', icon: 'dawn' }, { key: 'Dhuhr', ar: 'الظهر', icon: 'sun' },
  { key: 'Asr', ar: 'العصر', icon: 'sunlow' }, { key: 'Maghrib', ar: 'المغرب', icon: 'dusk' },
  { key: 'Isha', ar: 'العشاء', icon: 'night' },
];
let prayerData = {}, nextPrayer = null, nextPrayerAr = '', nextTime = null, prevTime = null;

function timeToDate(str) {
  const [h, m] = str.split(' ')[0].split(':').map(Number);
  const d = new Date(); d.setHours(h, m, 0, 0); return d;
}
function fmt12(str, html = false) {
  const [hh, mm] = str.split(' ')[0].split(':'); const h = parseInt(hh, 10);
  const ap = h >= 12 ? 'PM' : 'AM';
  return `${h % 12 || 12}:${mm}${html ? `<small>${ap}</small>` : ' ' + ap}`;
}

async function fetchPrayer() {
  try {
    const d = await getJSON(TV.prayerUrl);
    if (!d.timings) throw new Error('no data');
    prayerData = d.timings;
    const h = d.date?.hijri;
    if (h) {
      $('hijri-date').textContent = `${h.day} ${h.month.en} ${h.year} AH`;
      if ($('cal-hijri')) $('cal-hijri').textContent = `${h.month.ar} ${h.year}`;
    }
    refreshPrayerHighlights(new Date());
  } catch (e) {
    if ($('prayer-list') && !Object.keys(prayerData).length)
      $('prayer-list').innerHTML = '<div class="err">أوقات الصلاة غير متوفرة · Prayer times unavailable</div>';
  }
}

function refreshPrayerHighlights(now) {
  if (!$('prayer-list') || !Object.keys(prayerData).length) return;
  const items = PRAYERS.map(p => ({ ...p, dt: timeToDate(prayerData[p.key]) }));
  let cur = -1, next = -1;
  for (let i = 0; i < items.length; i++) if (now < items[i].dt) { next = i; cur = i - 1; break; }
  if (next === -1) {
    // After Isha: count down to tomorrow's Fajr (today's time is close enough).
    cur = items.length - 1;
    nextPrayer = 'Fajr · tomorrow'; nextPrayerAr = 'الفجر';
    nextTime = new Date(items[0].dt.getTime() + 86400000); prevTime = items[cur].dt;
  } else {
    nextPrayer = items[next].key; nextPrayerAr = items[next].ar;
    nextTime = items[next].dt;
    prevTime = next > 0 ? items[next - 1].dt : new Date(items[items.length - 1].dt.getTime() - 86400000);
  }

  $('prayer-list').innerHTML = items.map((p, i) => {
    let cls = 'prayer-item';
    if (i === cur) cls += ' active'; else if (i === next) cls += ' upcoming'; else if (now > p.dt) cls += ' passed';
    return `<div class="${cls}" style="--i:${i}">${ICON.icon(p.icon)}
      <div><div class="pname-ar">${p.ar}</div><div class="pname-en">${p.key}</div></div>
      <div class="ptime">${fmt12(prayerData[p.key], true)}</div></div>`;
  }).join('');
}

function countdown(now) {
  if (!nextTime || !$('cd-time')) return;
  const diff = nextTime - now;
  if (diff <= 0) { refreshPrayerHighlights(now); return; }
  $('cd-time').textContent = `${pad(Math.floor(diff / 3600000))}:${pad(Math.floor(diff % 3600000 / 60000))}:${pad(Math.floor(diff % 60000 / 1000))}`;
  $('cd-name').textContent = nextPrayer;
  $('cd-name-ar').textContent = nextPrayerAr;
  const f = clamp((now - prevTime) / (nextTime - prevTime), 0, 1);
  $('cd-prog').style.strokeDasharray = `${f * 100} 100`;
  $('cd-head').setAttribute('cx', 80 + 70 * Math.cos(2 * Math.PI * f));
  $('cd-head').setAttribute('cy', 80 + 70 * Math.sin(2 * Math.PI * f));
  $('countdown').classList.toggle('soon', diff < 10 * 60000);
}

function prayerBanner(now) {
  const el = $('prayer-now');
  const mins = CONFIG.pauseForPrayerMin;
  const p = mins && Object.keys(prayerData).length && PRAYERS.find(p => {
    const t = timeToDate(prayerData[p.key]); return now >= t && now - t < mins * 60000; });
  el.classList.toggle('on', !!p);
  if (p) { $('prayer-now-ar').textContent = `حان وقت صلاة ${p.ar}`; $('prayer-now-en').textContent = `Time for ${p.key} prayer`; }
  adhanMoment(now);
}

/* The first minute of each prayer gets the whole screen (once per prayer). */
const ADHAN_SECONDS = 60;
let adhanShown = '', adhanTimer = null;
function adhanMoment(now) {
  if (!Object.keys(prayerData).length) return;
  const p = PRAYERS.find(p => { const t = timeToDate(prayerData[p.key]); return now >= t && now - t < ADHAN_SECONDS * 1000; });
  const key = p ? p.key + now.toDateString() : '';
  if (!p || key === adhanShown) return;
  adhanShown = key;
  unspot();
  $('adhan-ar').textContent = `حان الآن موعد أذان ${p.ar}`;
  $('adhan-en').textContent = `Time for ${p.key} prayer`;
  $('adhan-time').textContent = fmt12(prayerData[p.key]);
  $('adhan').classList.add('on');
  clearTimeout(adhanTimer);
  adhanTimer = setTimeout(closeAdhan, ADHAN_SECONDS * 1000);
}
function closeAdhan() { $('adhan').classList.remove('on'); }

/* Music and video sound stop for N minutes from each prayer time (0 = never). */
function inPrayerPause(now = new Date()) {
  const mins = CONFIG.pauseForPrayerMin;
  if (!mins || !Object.keys(prayerData).length) return false;
  return PRAYERS.some(p => { const t = timeToDate(prayerData[p.key]); return now >= t && now - t < mins * 60000; });
}

/* ============ CALENDAR ============ */
const AR_MONTHS = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
function renderCalendar() {
  if (!$('cal-grid')) return;                // no calendar panel on this layout
  const now = new Date(), y = now.getFullYear(), m = now.getMonth(), today = now.getDate();
  $('cal-month-ar').textContent = AR_MONTHS[m];
  $('cal-month-en').textContent = now.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const first = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate(), prev = new Date(y, m, 0).getDate();
  let cells = '';
  for (let i = first - 1; i >= 0; i--) cells += `<div class="cal-cell other-month">${prev - i}</div>`;
  for (let d = 1; d <= days; d++) {
    const dow = new Date(y, m, d).getDay();
    const cls = d === today ? ' today' : (dow === 5 ? ' friday' : '') + (d < today ? ' past' : '');
    cells += `<div class="cal-cell${cls}">${d}</div>`;
  }
  const trail = (first + days) % 7 ? 7 - (first + days) % 7 : 0;
  for (let d = 1; d <= trail; d++) cells += `<div class="cal-cell other-month">${d}</div>`;
  $('cal-grid').innerHTML = cells;
}

/* The calendar turns over every few seconds: this month in English, then the Hijri month. */
const CAL_SECONDS = 12;
let calHijri = false;
const HIJRI = { day: new Intl.DateTimeFormat('en-u-ca-islamic-umalqura-nu-latn', { day: 'numeric' }),
                monAr: new Intl.DateTimeFormat('ar-u-ca-islamic-umalqura-nu-latn', { month: 'long', year: 'numeric' }),
                monEn: new Intl.DateTimeFormat('en-u-ca-islamic-umalqura-nu-latn', { month: 'long', year: 'numeric' }) };
const hDay = d => parseInt(HIJRI.day.format(d), 10);
function renderHijriCalendar() {
  const now = new Date(), start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  while (hDay(start) !== 1) start.setDate(start.getDate() - 1);
  $('cal-month-en').textContent = HIJRI.monEn.format(now);
  $('cal-month-ar').textContent = HIJRI.monAr.format(now);
  $('cal-hijri').textContent = 'التقويم الهجري · Hijri';
  let cells = '';
  for (let i = 0; i < start.getDay(); i++) cells += '<div class="cal-cell other-month"></div>';
  const d = new Date(start), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let n = 0;
  do {
    const isToday = d.getTime() === today.getTime();
    const cls = isToday ? ' today' : (d.getDay() === 5 ? ' friday' : '') + (d < today ? ' past' : '');
    cells += `<div class="cal-cell${cls}">${hDay(d)}</div>`;
    d.setDate(d.getDate() + 1); n++;
  } while (hDay(d) !== 1 && n < 31);
  $('cal-grid').innerHTML = cells;
}
function flipCalendar() {
  const box = $('cal-flip');
  box.classList.remove('flip-in');
  box.classList.add('flip-out');
  setTimeout(() => {
    calHijri = !calHijri;
    calHijri ? renderHijriCalendar() : renderCalendar();
    box.classList.remove('flip-out'); void box.offsetWidth; box.classList.add('flip-in');
  }, CALM ? 0 : 450);
}

/* The prayer panel and the Arabic headlines under it line up with the About us panel beside them. */
function matchPrayerHeight() {
  const pr = document.querySelector('.prayer-bottom'), news = document.querySelector('.news-card'),
        pk = document.querySelector('.picker-card');
  if (!pr || !news || document.querySelector('.grid-layout')) return;   // the designer's grid sizes panels itself
  const gap = parseFloat(getComputedStyle(pr.parentElement).rowGap) || 0;
  pr.style.height = (news.offsetHeight - (pk && pk.style.display !== 'none' ? pk.offsetHeight + gap : 0)) + 'px';
}

/* Arabic headlines as an iPhone-style picker wheel: the chosen line sits in the band,
   its neighbours curve away above and below, and the wheel turns one line at a time. */
const PICK_SECONDS = 5, PICK_ROW = 32;
let picks = [], pickIdx = 0, pickTimer = null;
async function fetchArabicNews() {
  try {
    const d = await getJSON(TV.newsArUrl);
    if (d.items?.length) { picks = d.items.map(i => i.title); $('picker-src').textContent = d.label || ''; }
  } catch (e) { /* keep last good */ }
  const card = document.querySelector('.picker-card');
  card.style.display = picks.length ? '' : 'none';
  matchPrayerHeight();
  if (!picks.length) return;
  $('picker-track').innerHTML = picks.map(t => `<div class="pick">${esc(t)}</div>`).join('');
  if (pickIdx >= picks.length) pickIdx = 0;
  turnPicker();
  if (!pickTimer) pickTimer = setInterval(() => { pickIdx = (pickIdx + 1) % picks.length; turnPicker(); }, PICK_SECONDS * 1000);
}
function turnPicker() {
  const box = $('picker'), mid = box.clientHeight / 2 - PICK_ROW / 2;
  $('picker-track').style.transform = `translateY(${mid - pickIdx * PICK_ROW}px)`;
  [...$('picker-track').children].forEach((el, i) => {
    const d = i - pickIdx, a = Math.max(-3, Math.min(3, d));
    el.style.transform = `translateZ(-40px) rotateX(${-a * 20}deg) translateZ(40px)`;
    el.style.opacity = Math.abs(d) > 3 ? 0 : 1 - Math.abs(d) * 0.25;
    el.classList.toggle('on', d === 0);
  });
}

/* Analogue clock in the top-left panel, with the day in both languages. */
function drawAnalog() {
  const n = new Date(), s = n.getSeconds(), m = n.getMinutes() + s / 60, h = n.getHours() % 12 + m / 60;
  $('an-h').setAttribute('transform', `rotate(${h * 30} 60 60)`);
  $('an-m').setAttribute('transform', `rotate(${m * 6} 60 60)`);
  $('an-s').setAttribute('transform', `rotate(${s * 6} 60 60)`);
  $('ck-wd-ar').textContent = n.toLocaleDateString('ar-AE', { weekday: 'long' });
  $('ck-date-ar').textContent = n.toLocaleDateString('ar-AE-u-nu-arab', { day: 'numeric', month: 'long', year: 'numeric' });
  $('ck-wd-en').textContent = n.toLocaleDateString('en-GB', { weekday: 'long' });
  $('ck-date-en').textContent = n.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

/* ============ SEA & WEATHER ============ */
const SKY = {
  0:['صافٍ','Clear','clear'], 1:['صافٍ غالباً','Mostly clear','partly'], 2:['غائم جزئياً','Partly cloudy','partly'],
  3:['غائم','Cloudy','cloudy'], 45:['ضباب','Fog','fog'], 48:['ضباب','Fog','fog'],
  drizzle:['رذاذ','Drizzle','drizzle'], rain:['أمطار','Rain','rain'], showers:['زخات','Showers','showers'], storm:['عواصف رعدية','Thunderstorm','storm'],
};
function sky(code) {
  if (code == null) return ['', '', 'partly'];
  const k = [0,1,2,3,45,48].includes(code) ? code
    : code >= 51 && code <= 57 ? 'drizzle' : code >= 61 && code <= 67 ? 'rain'
    : code >= 80 && code <= 86 ? 'showers' : code >= 95 ? 'storm' : 2;
  return SKY[k];
}
const DIRS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
const compass = deg => deg == null ? '--' : DIRS[Math.round((deg % 360) / 22.5) % 16];
const r0 = (v, d = 0) => v == null ? '--' : Number(v).toFixed(d);
const hhmm = iso => iso ? iso.slice(11, 16) : '--:--';

/* Numbers count up to their new value instead of just appearing. */
const shownNums = {};
const num = (key, v, d = 0) => v == null ? '--' : `<span class="num" data-k="${key}" data-v="${v}" data-d="${d}">${r0(shownNums[key] ?? v, d)}</span>`;
function animateNums(root) {
  root.querySelectorAll('.num').forEach(el => {
    const k = el.dataset.k, to = Number(el.dataset.v), d = Number(el.dataset.d);
    const from = shownNums[k] ?? (CALM ? to : 0);
    shownNums[k] = to;
    if (CALM || from === to) { el.textContent = to.toFixed(d); return; }
    const t0 = performance.now(), T = 1400;
    const step = t => {
      const p = Math.min(1, (t - t0) / T), e = 1 - Math.pow(1 - p, 3);
      el.textContent = (from + (to - from) * e).toFixed(d);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

const SEA_STATUS = {
  good:    { ar: 'أحوال بحرية ملائمة',             en: 'Favourable sea conditions',   cls: '' },
  caution: { ar: 'أحوال متوسطة - يُنصح بالحذر',     en: 'Moderate - exercise caution', cls: 'warn' },
  danger:  { ar: 'أحوال خطرة - يُنصح بعدم الإبحار', en: 'Hazardous - avoid sailing',   cls: 'danger' },
};
function seaStatus(wind, wave) {
  const m = CONFIG.marine;
  if (wind == null && wave == null) return null;
  if ((wind != null && wind >= m.dangerWindKn) || (wave != null && wave >= m.dangerWaveM)) return 'danger';
  if ((wind != null && wind >= m.cautionWindKn) || (wave != null && wave >= m.cautionWaveM)) return 'caution';
  return 'good';
}

/* Moon - calculated locally, mean synodic month from a known new moon. */
const SYN = 29.530588853;
function moonInfo(now = new Date()) {
  const KNOWN_NEW = Date.UTC(2000, 0, 6, 18, 14);
  const mod = (x, n) => ((x % n) + n) % n;
  const age = mod((now - KNOWN_NEW) / 86400000, SYN);
  const i = Math.floor(age / SYN * 8 + 0.5) % 8;
  return {
    age,
    illum: Math.round((1 - Math.cos(2 * Math.PI * age / SYN)) / 2 * 100),
    ar: ['محاق','هلال متزايد','تربيع أول','أحدب متزايد','بدر','أحدب متناقص','تربيع ثانٍ','هلال متناقص'][i],
    en: ['New moon','Waxing crescent','First quarter','Waxing gibbous','Full moon','Waning gibbous','Last quarter','Waning crescent'][i],
    toFull: Math.round(mod(SYN / 2 - age, SYN)), toNew: Math.round(mod(SYN - age, SYN)),
  };
}

/* Where the sun is today: 'dawn' | 'day' | 'dusk' | 'night', and the 0..1 position while up. */
function sunPhase(now = new Date()) {
  const d = lastWx?.daily || {};
  const rise = d.sunrise?.[0] ? timeToDate(hhmm(d.sunrise[0])) : (() => { const t = new Date(); t.setHours(6, 0, 0, 0); return t; })();
  const set = d.sunset?.[0] ? timeToDate(hhmm(d.sunset[0])) : (() => { const t = new Date(); t.setHours(18, 0, 0, 0); return t; })();
  const H = 3600000, f = (now - rise) / (set - rise);
  const phase = Math.abs(now - rise) < H ? 'dawn' : Math.abs(now - set) < H ? 'dusk' : (f > 0 && f < 1) ? 'day' : 'night';
  return { phase, f, rise, set, up: f >= 0 && f <= 1 };
}

/* The whole screen's colour mood follows the sun. */
const PALETTES = {           // [main, warm, highlight] - never one colour alone
  dawn:  ['#ff9e7a', '#f5b942', '#c084fc'],
  day:   ['#2dd4bf', '#f5b942', '#ff8a5b'],
  dusk:  ['#ff7a59', '#e0559e', '#f5b942'],
  night: ['#8b7cff', '#2dd4bf', '#e0559e'],
};
let phaseNow = null;
function applyPhase() {
  const { phase } = sunPhase();
  if (phase === phaseNow) return;
  phaseNow = phase;
  const [a1, a2, a3] = PALETTES[phase];
  const root = document.documentElement.style;
  root.setProperty('--a1', a1); root.setProperty('--a2', a2); root.setProperty('--a3', a3);
  particleColors = [a1, a2, a3];
}

let lastWx = null, lastSea = null, wxFetchedAt = null;
async function fetchWeather() {
  try {
    const d = await getJSON(TV.weatherUrl);
    if (d.weather) lastWx = d.weather;
    if (d.marine) lastSea = d.marine;
    if (d.weather || d.marine) wxFetchedAt = new Date();
  } catch (e) { /* keep last good */ }
  renderSky();
}

const STATUS_COLOR = { good: 'var(--green)', caution: 'var(--gold)', danger: 'var(--red)' };

/* ============ UAE FLAG: waves on its pole, light rolling across the cloth ============ */
const FLAG_COLORS = ['#00732f', '#ffffff', '#000000'], FLAG_RED = '#ff0000';
let flagT = 0;
function drawFlag() {
  // Like close-up flag footage: the cloth fills the whole frame and ripples, folds catching the light.
  const c = $('flag'), g = c.getContext('2d'), W = c.width, H = c.height;
  const amp = H * 0.06, red = W * 0.27, step = 2;
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  for (let x = 0; x < W; x += step) {
    const ph = x / W * 3 * Math.PI - flagT, ph2 = x / W * 7.3 * Math.PI - flagT * 1.7;
    const dy = Math.sin(ph) * amp + Math.sin(ph2) * amp * 0.3;
    const slope = Math.cos(ph) + Math.cos(ph2) * 0.6;           // fold facing the light or away
    const top = -amp * 1.5 + dy, fh = H + amp * 3;
    if (x < red + Math.sin(x / 40 - flagT) * 2) { g.fillStyle = FLAG_RED; g.fillRect(x, top, step + .5, fh); }
    else FLAG_COLORS.forEach((col, k) => { g.fillStyle = col; g.fillRect(x, top + k * fh / 3, step + .5, fh / 3 + .5); });
    g.fillStyle = slope > 0 ? `rgba(255,255,255,${slope * .13})` : `rgba(0,0,0,${-slope * .32})`;
    g.fillRect(x, 0, step + .5, H);
  }
  flagT += 0.08;
}
/* A real flag video (media/display/flag.mp4) wins; the drawn flag is the fallback. */
function startFlag() {
  const v = $('flag-video');
  v.addEventListener('canplay', () => { v.hidden = false; $('flag').hidden = true; clearInterval(flagTimer); v.play().catch(() => {}); }, { once: true });
  drawnFlag();
}
let flagTimer = null;
function drawnFlag() {
  const c = $('flag'), r = c.getBoundingClientRect();
  if (!r.width) return;
  c.width = c.clientWidth; c.height = c.clientHeight;
  drawFlag();
  if (!CALM) flagTimer = setInterval(drawFlag, 33);
}

/* Sun arc (sunrise → sunset, the dot is where the sun is now) and the real moon shape. */
function renderGreeting() {
  const h = new Date().getHours();
  const g = h >= 4 && h < 12 ? ['dawn', 'صباح الخير', 'Good morning']
          : h >= 12 && h < 17 ? ['sun', 'مساء الخير', 'Good afternoon'] : ['night', 'مساء الخير', 'Good evening'];
  $('w-greet').innerHTML = `${ICON.icon(g[0])} ${g[1]} · ${g[2]}`;
}

function renderSky() {
  if (!$('sun-dot')) return;                 // the Sun & Moon panel isn't on this layout
  applyPhase();
  renderGreeting();
  const d = lastWx?.daily || {}, now = new Date();
  $('sunrise').textContent = hhmm(d.sunrise?.[0]); $('sunset').textContent = hhmm(d.sunset?.[0]);
  const { f, set, up } = sunPhase(now);
  if (d.sunrise?.[0] && d.sunset?.[0]) {
    if (up) {
      const left = set - now;
      $('daylight').textContent = `${Math.floor(left / 3600000)}h ${pad(Math.floor(left % 3600000 / 60000))}m`;
      $('daylight-lbl').textContent = 'ضوء النهار · Daylight left';
    } else {
      $('daylight').textContent = 'Night';
      $('daylight-lbl').textContent = 'الليل · Night';
    }
  }
  const p = up ? f : 0;
  for (const id of ['sun-dot', 'sun-halo']) {
    $(id).setAttribute('cx', 160 - 140 * Math.cos(Math.PI * p));
    $(id).setAttribute('cy', 84 - 72 * Math.sin(Math.PI * p));
    $(id).classList.toggle('down', !up);
  }
  $('sun-done').style.strokeDasharray = `${up ? f * 100 : 0} 100`;
  document.querySelector('.sky-card').classList.toggle('night', !up);

  const moon = moonInfo(now);
  $('moon-row').innerHTML = `${ICON.moon(moon.age, SYN, 52)}<div style="flex:1">
    <b>${moon.ar} · ${moon.en}<small>${moon.illum}%</small></b>
    <div class="moon-bar"><i style="width:${moon.illum}%"></i></div>
    <small>${moon.toFull <= moon.toNew
      ? `البدر بعد ${moon.toFull} يوم · Full moon in ${moon.toFull} d`
      : `المحاق بعد ${moon.toNew} يوم · New moon in ${moon.toNew} d`}</small></div>`;
}

/* ============ NEWS: one big headline at a time, the next ones queued beside it ============ */
const NEWS_SECONDS = 9;
let headlines = [], outsideNews = [], newsIdx = 0, newsTimer = null;
async function fetchNews() {
  if (CONFIG.showNews) {
    try {
      const d = await getJSON(TV.newsUrl);
      if (d.items?.length) outsideNews = d.items.map(i => ({ t: i.title, src: d.label || '' }));
    } catch (e) { /* keep last good */ }
  }
  mergeNews();
}
/* Our own news (from the website feed) first, then the outside feeds. */
function mergeNews() {
  const ours = (site.news || []).map(n => ({ t: n.en || n.ar, sub: n.en && n.ar ? n.ar : '', src: site.newsLabel, ours: true }));
  headlines = [...ours, ...outsideNews];
  if (headlines.length) {
    if (newsIdx >= headlines.length) newsIdx = 0;
    if (!newsTimer) { showHeadline(); newsTimer = setInterval(() => { newsIdx = (newsIdx + 1) % headlines.length; showHeadline(); }, NEWS_SECONDS * 1000); }
  } else if (CONFIG.showNews) {
    $('news-list').innerHTML = '<div class="err">الأخبار غير متوفرة · News unavailable</div>';
  }
  buildTicker();
}
function showHeadline() {
  if (!headlines.length) return;
  const queue = [1, 2, 3].map(k => (newsIdx + k) % headlines.length).filter(i => i !== newsIdx);
  $('news-list').innerHTML = `
    <div class="news-hero swap${headlines[newsIdx].ours ? ' ours' : ''}">
      <div class="news-src">${esc(headlines[newsIdx].src)}</div>
      <div class="news-title">${esc(headlines[newsIdx].t)}</div>
      ${headlines[newsIdx].sub ? `<div class="news-sub">${esc(headlines[newsIdx].sub)}</div>` : ''}
      <div class="news-prog"><i class="run" style="--t:${NEWS_SECONDS}s"></i></div>
    </div>
    <div class="news-queue">${[...new Set(queue)].map(i => `<div class="nq"><b>${pad(i + 1)}</b><span>${esc(headlines[i].t)}</span></div>`).join('')}</div>`;
  if (!aboutSlides.length) $('news-count').textContent = `${pad(newsIdx + 1)} / ${pad(headlines.length)}`;
}
function buildTicker() {
  const all = [...(CONFIG.ticker || []), ...headlines.map(h => h.t)];
  const track = $('ticker-track');
  if (!all.length) { track.innerHTML = ''; return; }
  const html = all.map(h => `<span class="tick-item">${esc(h)}</span><span class="tick-sep"></span>`).join('');
  track.innerHTML = html + html;
}

/* ============ YOUR WEBSITE: closed notice, services with QR codes, photos ============ */
const SERVICE_SECONDS = 10, PHOTO_SECONDS = 9;
let site = {}, svcIdx = -1, svcTimer = null, photoIdx = 0, photoTimer = null, photoKey = '';
async function fetchSite() {
  if (TV.siteUrl) try { site = await getJSON(TV.siteUrl); } catch (e) { /* keep last good */ }
  try {                             // this server's own About us copy wins over a website's
    const ab = await getJSON(TV.aboutUrl);
    if (ab.about) Object.assign(site, { about: ab.about, aboutProducts: ab.products, productsQr: ab.productsQr });
  } catch (e) { /* keep last good */ }
  const c = site.closed;
  $('closed-ribbon').classList.toggle('on', !!c);
  if (c) { $('closed-ar').textContent = c.ar; $('closed-en').textContent = c.en; }
  mergeNews();
  startAbout();
  startServices();
  startPhotos();
}

/* About us: the news panel becomes the organisation's own story, from its About page.
   Outside news then lives only in the ticker along the bottom. */
let aboutSlides = [], aboutIdx = 0, aboutTimer = null, aboutKey = '';
// English on the left, Arabic on the right, side by side like the website's two languages
const pair = (en, ar) => `<div class="ab-pair"><div class="ab-col ab-en">${en}</div><div class="ab-col ab-ar">${ar}</div></div>`;
const bi = (ar, en, cls = '') => pair(`<div class="${cls}">${esc(en)}</div>`, `<div class="${cls}">${esc(ar)}</div>`);
function aboutDeck(a) {
  const kick = (icon, ar, en) => `<div class="ab-kick"><i data-icon="${icon}"></i><span class="ab-kick-t"><b dir="rtl">${esc(ar)}</b><span>${esc(en)}</span></span></div>`;
  const deck = [{ s: 10, cls: 'ab-welcome', html: `
      <div class="ab-ar ab-huge">مرحباً بكم في ${esc(CONFIG.orgNameAr)}</div>
      <div class="ab-en ab-huge">Welcome to ${esc(CONFIG.orgNameEn)}</div>` }];
  if (a.vision?.en) deck.push({ s: 12, html: kick('eye', 'رؤيتنا', 'Our vision') + bi(a.vision.ar, a.vision.en, 'ab-big') });
  if (a.mission?.en) deck.push({ s: 14, html: kick('globe', 'رسالتنا', 'Our mission') + bi(a.mission.ar, a.mission.en, 'ab-mid') });
  if (a.values?.length) deck.push({ s: 16, html: kick('chat', 'قيمنا', 'Our values') +
      `<div class="ab-values">${a.values.map((v, i) => `<div class="ab-val" style="animation-delay:${0.3 + i * 0.7}s">
        <b>${pad(i + 1)}</b><span class="ab-ar">${esc(v.ar)}</span><span class="ab-en">${esc(v.en)}</span></div>`).join('')}</div>` });
  (a.objectives || []).forEach((o, i, all) => deck.push({ s: 12, html:
      kick('timer', 'أهدافنا الاستراتيجية', 'Strategic objectives') +
      `<div class="ab-obj"><div class="ab-num">${pad(i + 1)}<small>/${pad(all.length)}</small></div><div>
        ${pair(`<div class="ab-otitle">${esc(o.title_en)}</div><div class="ab-otext">${esc(o.text_en)}</div>`,
               `<div class="ab-otitle">${esc(o.title_ar)}</div><div class="ab-otext">${esc(o.text_ar)}</div>`)}</div></div>` }));
  const prods = site.aboutProducts?.length ? site.aboutProducts : site.services || [];
  if (prods.length) deck.push({ s: 16, html: kick('pin', 'منتجاتنا وخدماتنا', 'Our products & services') +
      `<div class="ab-prod-row"><div class="ab-prods">${prods.map((p, i) => `<div class="ab-prod" style="animation-delay:${0.2 + i * 0.25}s">
        <div class="ab-emo">${p.iconUrl ? `<img src="${p.iconUrl}" alt="">` : esc(p.icon || '')}</div><div class="ab-ar">${esc(p.nameAr)}</div><div class="ab-en">${esc(p.nameEn)}</div></div>`).join('')}</div>
        ${site.productsQr ? `<div class="qr-box"><div class="svc-qr">${site.productsQr}<span class="qr-scan"></span></div><div class="qr-label">امسح للمزيد · Scan for more</div></div>` : ''}</div>` });
  return deck;
}
function startAbout() {
  const a = site.about, key = a ? JSON.stringify([a, (site.aboutProducts?.length ? site.aboutProducts : site.services || []).map(s => s.nameEn), !!site.productsQr]) : '';
  if (key === aboutKey) return;
  aboutKey = key; clearTimeout(aboutTimer);
  aboutSlides = a ? aboutDeck(a) : [];
  const card = document.querySelector('.news-card');
  card.classList.toggle('about-on', aboutSlides.length > 0);
  card.classList.remove('hidden');
  $('news-title').textContent = aboutSlides.length ? 'عن الجمعية · About us' : 'آخر الأخبار · Latest News';
  if (!aboutSlides.length) { if (!CONFIG.showNews) card.classList.add('hidden'); return; }
  aboutIdx = 0; showAbout();
}
/* The old slide glides out, then the new one glides in: English from the left, Arabic from the right. */
function showAbout() {
  const old = $('about-stage').querySelector('.ab-slide');
  if (old && !CALM) { old.classList.add('ab-out'); setTimeout(drawAbout, 650); } else drawAbout();
}
function drawAbout() {
  const sl = aboutSlides[aboutIdx], st = $('about-stage');
  st.className = `about-stage ${sl.cls || ''}`;
  st.innerHTML = `<div class="ab-slide">${sl.html}</div><div class="news-prog"><i class="run" style="--t:${sl.s}s"></i></div>`;
  ICON.fill(st);
  $('news-count').textContent = `${pad(aboutIdx + 1)} / ${pad(aboutSlides.length)}`;
  aboutTimer = setTimeout(() => { aboutIdx = (aboutIdx + 1) % aboutSlides.length; showAbout(); }, sl.s * 1000);
}

/* The contact panel takes turns: contact details, then each service with its own QR code. */
function startServices() {
  const n = (site.services || []).length;
  $('svc-dots').innerHTML = n ? [...Array(n + 1)].map(() => '<i></i>').join('') : '';
  if (!n) { clearInterval(svcTimer); svcTimer = null; svcIdx = -1; showService(); return; }
  if (!svcTimer) svcTimer = setInterval(() => { svcIdx = svcIdx + 1 >= n ? -1 : svcIdx + 1; showService(); }, SERVICE_SECONDS * 1000);
}
function showService() {
  const s = site.services?.[svcIdx], card = document.querySelector('.contact-card');
  card.classList.toggle('svc-on', !!s);
  [...$('svc-dots').children].forEach((d, i) => d.classList.toggle('on', i === svcIdx + 1));
  $('contact-title').textContent = s ? 'خدماتنا · Our services' : 'تواصل معنا · Contact Us';
  if (!s) return;
  $('svc-slide').innerHTML = `
    ${s.qr ? `<div class="qr-box"><div class="svc-qr">${s.qr}<span class="qr-scan"></span></div><div class="qr-label">امسح للطلب · Scan to order</div></div>` : ''}
    <div class="svc-text">
      <div class="svc-name-ar">${esc(s.nameAr)}</div>
      <div class="svc-name-en">${esc(s.nameEn)}</div>
      <div class="svc-desc">${esc(s.textEn || s.textAr)}</div>
    </div>`;
  $('svc-slide').classList.remove('swap'); void $('svc-slide').offsetWidth; $('svc-slide').classList.add('swap');
}

/* Gallery photos drift slowly behind the welcome text. */
function startPhotos() {
  const list = site.photos || [], key = list.map(p => p.url).join('|');
  if (key === photoKey) return;
  photoKey = key; photoIdx = 0; clearInterval(photoTimer);
  $('w-photos').innerHTML = list.map((p, i) => `<div class="w-photo${i ? '' : ' on'}" style="background-image:url('${encodeURI(p.url)}')"></div>`).join('');
  $('welcome-screen').classList.toggle('has-photos', list.length > 0);
  if (list.length > 1) photoTimer = setInterval(() => {
    const all = $('w-photos').children;
    all[photoIdx].classList.remove('on');
    photoIdx = (photoIdx + 1) % all.length;
    all[photoIdx].classList.add('on');
  }, PHOTO_SECONDS * 1000);
}

/* ============ LIVE INSIGHT LINE: one short fact at a time under the name ============ */
const INSIGHT_SECONDS = 7;
let insightIdx = 0;
function insights() {
  const out = [], now = new Date();
  if (site.closed) out.push(['calendar', 'var(--red)', site.closed.ar, `<b>${esc(site.closed.en)}</b>`]);
  const dur = ms => { const m = Math.round(ms / 60000); return m >= 60 ? `${Math.floor(m / 60)}h ${pad(m % 60)}m` : `${m} min`; };
  if (nextTime) out.push(['mosque', 'var(--c-prayer)', `${nextPrayerAr} بعد ${dur(nextTime - now)}`, `<b>${nextPrayer}</b> in ${dur(nextTime - now)}`]);
  const c = lastWx?.current, mc = lastSea?.current;
  if (c) {
    const [ar, en] = sky(c.weather_code);
    out.push(['thermo', 'var(--c-sky)', `${r0(c.temperature_2m)}° ${ar}`, `<b>${r0(c.temperature_2m)}°C</b> · ${en}`]);
  }
  if (CONFIG.showMarine && c) {
    const k = seaStatus(c.wind_speed_10m, mc?.wave_height);
    if (k) out.push(['waves', STATUS_COLOR[k], SEA_STATUS[k].ar, `<b>${SEA_STATUS[k].en}</b> · wind ${r0(c.wind_speed_10m)} kn${mc?.wave_height != null ? ` · waves ${r0(mc.wave_height, 1)} m` : ''}`]);
  }
  if (c?.uv_index >= 8) out.push(['uv', 'var(--red)', 'أشعة فوق بنفسجية عالية جداً', `<b>UV ${r0(c.uv_index)}</b> · very high`]);
  const { up, set } = sunPhase(now), dl = lastWx?.daily;
  if (dl?.sunset) {
    const rise = hhmm(dl.sunrise?.[now > set ? 1 : 0] || dl.sunrise?.[0]);
    out.push(up ? ['dusk', 'var(--c-sky)', `الغروب ${hhmm(dl.sunset[0])}`, `Sunset at <b>${hhmm(dl.sunset[0])}</b>`]
                : ['dawn', 'var(--c-sky)', `الشروق ${rise}`, `Sunrise at <b>${rise}</b>`]);
  }
  const m = moonInfo(now);
  out.push(['night', 'var(--c-cal)', m.ar, `<b>${m.en}</b> · ${m.illum}% lit`]);
  if ($('hijri-date').textContent) out.push(['calendar', 'var(--c-cal)', $('cal-hijri')?.textContent || '', $('hijri-date').textContent]);
  return out;
}
function showInsight() {
  const list = insights(), box = $('insight');
  if (!list.length) return;
  insightIdx %= list.length;
  const [ic, col, ar, en] = list[insightIdx++];
  [...box.children].forEach(el => { el.classList.add('out'); setTimeout(() => el.remove(), 500); });
  box.insertAdjacentHTML('beforeend', `<span style="--ic:${col}">${ICON.icon(ic)}<em>${esc(ar)}</em> · ${en}</span>`);
}

/* ============ BACKGROUND PARTICLES (light dust drifting up; off in calm mode) ============ */
const cv = $('particles'), cx = cv.getContext('2d');
let dots = [], particleColors = ['#2dd4bf', '#f5b942', '#ff8a5b'];
function sizeParticles() {
  const r = Math.min(devicePixelRatio || 1, 1.5);
  cv.width = innerWidth * r; cv.height = innerHeight * r;
  dots = [...Array(70)].map(() => ({
    x: Math.random() * cv.width, y: Math.random() * cv.height,
    r: (Math.random() * 1.6 + 0.4) * r, c: Math.floor(Math.random() * 3), v: (Math.random() * 0.25 + 0.05) * r, t: Math.random() * 6.28,
  }));
}
function particles() {
  cx.clearRect(0, 0, cv.width, cv.height);
  for (const d of dots) {
    d.y -= d.v; d.t += 0.02; d.x += Math.sin(d.t) * 0.15;
    if (d.y < -4) { d.y = cv.height + 4; d.x = Math.random() * cv.width; }
    cx.fillStyle = particleColors[d.c];
    cx.globalAlpha = 0.25 + 0.35 * (0.5 + 0.5 * Math.sin(d.t * 1.7));
    cx.beginPath(); cx.arc(d.x, d.y, d.r, 0, 6.283); cx.fill();
  }
}

/* ============ AUTO TOUR: the screen is a display - nobody touches it ============
   Every so often one card steps forward to the middle for a few seconds, so
   people waiting notice what's on it. Never while a video plays or at prayer time. */
const TOUR_EVERY = 75, TOUR_SHOW = 8;
let spotted = null, spotTimer = null;
const cards = () => [...document.querySelectorAll('.card')].filter(c => !c.classList.contains('hidden'));

function box(el) {
  const d = $('dash').getBoundingClientRect(), r = el.getBoundingClientRect();
  return { x: (r.left - d.left) / scale, y: (r.top - d.top) / scale, w: r.width / scale, h: r.height / scale };
}
function spot(card, seconds) {
  unspot();
  const r = box(card), k = Math.min(1.9, 1500 / r.w, 880 / r.h);
  card.style.transform = `translate(${960 - (r.x + r.w / 2)}px, ${540 - (r.y + r.h / 2)}px) scale(${k})`;
  card.classList.add('spot');
  $('dash').classList.add('spotlit');
  spotted = card;
  spotTimer = setTimeout(unspot, seconds * 1000);
}
function unspot() {
  clearTimeout(spotTimer);
  if (!spotted) return;
  const c = spotted; spotted = null;
  c.style.transform = '';
  $('dash').classList.remove('spotlit');
  setTimeout(() => { if (spotted !== c) c.classList.remove('spot'); }, 600);   // stay on top while shrinking back
}
function initMotion() {
  cards().forEach(c => c.insertAdjacentHTML('beforeend', '<span class="shine-sweep"></span>'));
  if (CALM) return;
  let tourIdx = 0;
  setInterval(() => {
    const busy = spotted || $('adhan').classList.contains('on') || document.body.classList.contains('occasion-full')
      || ['video', 'youtube'].includes(state?.center);
    if (busy) return;
    const list = cards().filter(c => c.dataset.name !== 'media');
    spot(list[tourIdx++ % list.length], TOUR_SHOW);
  }, TOUR_EVERY * 1000);
  // Now and then a light sweeps across one card, so the screen never sits still.
  setInterval(() => {
    if (spotted) return;
    const list = cards(), c = list[Math.floor(Math.random() * list.length)];
    c.classList.remove('shine'); void c.offsetWidth; c.classList.add('shine');
  }, 12000);
}

/* ============ OCCASIONS: celebrations take over the screen ============
   The server says which occasion runs now. It replaces what agents picked:
     photos_music  photos with songs
     video         videos with their own sound
     video_music   videos without sound, songs over them
     mix           photos with songs, and every few minutes one video with its
                   sound (the songs pause, then carry on where they stopped)
   Prayer pauses still apply. */
let rawState = null, occSig = 'null', occPhase = 'photos', occTimer = null, mixVideoIdx = 0;

function deriveState() {
  const o = rawState?.occasion;
  if (!o) return rawState;
  const base = { ...rawState, shuffle: o.shuffle, video: [], slides: [], music: o.songs, musicOn: o.songs.length > 0 };
  if (o.mode === 'video') return { ...base, center: 'video', video: o.videos, videoMuted: false, musicOn: false, music: [] };
  if (o.mode === 'video_music') return { ...base, center: 'video', video: o.videos, videoMuted: true };
  if (o.mode === 'mix' && occPhase === 'video' && o.videos.length)
    return { ...base, center: 'video', video: [o.videos[mixVideoIdx % o.videos.length]], videoMuted: false };
  return { ...base, center: o.photos.length ? 'slideshow' : 'welcome', slides: o.photos };
}

function startOccasion(o) {
  clearTimeout(occTimer);
  occPhase = 'photos';
  const full = !!(o && o.fullScreen);
  document.body.classList.toggle('occasion', !!o);
  document.body.classList.toggle('occasion-full', full);
  document.body.dataset.occasion = o ? o.theme : '';
  if (full) unspot();
  $('occ-greet').classList.toggle('on', !!(o && (o.greetingAr || o.greetingEn)));
  if (o) { $('occ-greet-ar').textContent = o.greetingAr || ''; $('occ-greet-en').textContent = o.greetingEn || ''; }
  effects(o && !CALM ? o.theme : 'none');
  if (o && o.mode === 'mix' && o.videos.length) scheduleMixVideo(o);
}
function scheduleMixVideo(o) {
  clearTimeout(occTimer);
  occTimer = setTimeout(() => {
    occPhase = 'video';
    state = deriveState(); applyCenter(true); applyAudio();
    occTimer = setTimeout(mixVideoDone, 20 * 60000);       // safety: never stuck on one video
  }, o.videoEvery * 60000);
}
/* Called when a video ends. True = the occasion handled it (back to photos). */
function mixVideoDone() {
  if (occPhase !== 'video') return false;
  occPhase = 'photos'; mixVideoIdx++;
  state = deriveState(); applyCenter(); applyAudio();
  if (rawState?.occasion) scheduleMixVideo(rawState.occasion);
  return true;
}

/* Festive layer drawn over the media: fireworks, lanterns or confetti. */
const fx = { kind: 'none', parts: [], t: 0, timer: 0 };
const FLAG = ['#ef3340', '#00a651', '#ffffff', '#ef3340', '#00a651'];
const CONFETTI = ['#f5b942', '#ff8a5b', '#2dd4bf', '#f472b6', '#a78bfa', '#34d399'];
function effects(kind) {
  fx.kind = kind; fx.parts = []; fx.t = 0;
  clearInterval(fx.timer);
  const c = $('fx'), g = c.getContext('2d');
  g.clearRect(0, 0, c.width, c.height);
  if (kind === 'none') return;
  const box = document.querySelector('.media-card');
  c.width = box.offsetWidth; c.height = box.offsetHeight;
  if (kind === 'eid') {
    for (let i = 0; i < 60; i++) fx.parts.push({ x: Math.random() * c.width, y: Math.random() * c.height * 0.6, r: Math.random() * 1.6 + 0.4, p: Math.random() * 6 });
  }
  fx.timer = setInterval(() => {                             // ~30 fps is plenty and kind to TV sticks
    fx.t++;
    g.clearRect(0, 0, c.width, c.height);
    if (kind === 'national') fireworks(g, c);
    else if (kind === 'eid') lanterns(g, c);
    else confetti(g, c);
  }, 33);
}
function fireworks(g, c) {
  if (fx.t % 18 === 0) {                                      // a new burst every ~0.6 s
    const x = c.width * (0.15 + Math.random() * 0.7), y = c.height * (0.12 + Math.random() * 0.4);
    const col = FLAG[Math.floor(Math.random() * FLAG.length)];
    for (let i = 0; i < 110; i++) {
      const a = Math.random() * Math.PI * 2, v = Math.random() * 6 + 2;
      fx.parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 60 + Math.random() * 25, col });
    }
  }
  g.globalCompositeOperation = 'lighter';
  fx.parts = fx.parts.filter(p => p.life > 0);
  for (const p of fx.parts) {
    p.x += p.vx; p.y += p.vy; p.vy += 0.05; p.vx *= 0.985; p.vy *= 0.985; p.life--;
    g.globalAlpha = Math.min(1, p.life / 40);
    g.fillStyle = p.col;
    g.beginPath(); g.arc(p.x, p.y, 3.6, 0, 6.283); g.fill();
  }
  g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
}
function lanterns(g, c) {
  for (const s of fx.parts) {                                 // twinkling stars
    g.globalAlpha = 0.3 + 0.7 * Math.abs(Math.sin(s.p + fx.t * 0.04));
    g.fillStyle = '#fff'; g.beginPath(); g.arc(s.x, s.y, s.r, 0, 6.283); g.fill();
  }
  g.globalAlpha = 1;
  // crescent, top right
  const mx = c.width - 140, my = 120;
  g.fillStyle = '#f5d27a'; g.shadowColor = '#f5b942'; g.shadowBlur = 30;
  g.beginPath(); g.arc(mx, my, 64, 0, 6.283); g.fill();
  g.globalCompositeOperation = 'destination-out'; g.shadowBlur = 0;
  g.beginPath(); g.arc(mx + 29, my - 17, 58, 0, 6.283); g.fill();
  g.globalCompositeOperation = 'source-over';
  // five lanterns hanging from the top, swaying
  const n = 5;
  for (let i = 0; i < n; i++) {
    const x = c.width * (0.1 + i * 0.13), len = 50 + (i % 3) * 40, sway = Math.sin(fx.t * 0.03 + i) * 0.08;
    g.save(); g.translate(x, 0); g.rotate(sway); g.scale(1.7, 1.7);
    g.strokeStyle = 'rgba(245,185,66,.7)'; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(0, 0); g.lineTo(0, len); g.stroke();
    g.translate(0, len);
    g.shadowColor = '#ffb43d'; g.shadowBlur = 25 + 10 * Math.sin(fx.t * 0.08 + i);
    g.fillStyle = '#c8901f';
    g.beginPath(); g.moveTo(-10, 0); g.lineTo(10, 0); g.lineTo(16, 10); g.lineTo(-16, 10); g.fill();   // cap
    g.fillStyle = '#ffd36b';
    g.beginPath(); g.ellipse(0, 34, 18, 26, 0, 0, 6.283); g.fill();                                   // glowing body
    g.shadowBlur = 0; g.strokeStyle = '#c8901f'; g.lineWidth = 2;
    for (const dx of [-9, 0, 9]) { g.beginPath(); g.moveTo(dx, 10); g.lineTo(dx * 0.8, 58); g.stroke(); }
    g.fillStyle = '#c8901f'; g.fillRect(-8, 58, 16, 6);
    g.restore();
  }
}
function confetti(g, c) {
  if (fx.parts.length < 140) fx.parts.push({ x: Math.random() * c.width, y: -10, vy: 1 + Math.random() * 2,
    vx: Math.random() - 0.5, r: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.2, w: 6 + Math.random() * 6,
    col: CONFETTI[Math.floor(Math.random() * CONFETTI.length)] });
  for (const p of fx.parts) {
    p.y += p.vy; p.x += p.vx + Math.sin((fx.t + p.w) * 0.05) * 0.6; p.r += p.vr;
    if (p.y > c.height + 10) { p.y = -10; p.x = Math.random() * c.width; }
    g.save(); g.translate(p.x, p.y); g.rotate(p.r);
    g.fillStyle = p.col; g.fillRect(-p.w / 2, -p.w / 4, p.w, p.w / 2);
    g.restore();
  }
}

/* ============ PLAYBACK (controlled from the agent panel) ============ */
const vid = $('vid'), music = $('music');
let state = null, lastCommandSeq = null;
let videoList = [], videoIdx = 0, musicList = [], musicIdx = 0, slides = [], slideIdx = 0, slideTimer = null;
let soundBlocked = false;

const sameList = (a, b) => a.length === b.length && a.every((x, i) => x.id === b[i].id && x.url === b[i].url);

function shuffled(list) {
  const a = [...list];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

function tryPlay(el) {
  const p = el.play();
  if (p && p.catch) p.catch(err => {
    if (err.name === 'NotAllowedError') { soundBlocked = true; $('sound-gate').classList.add('on'); }
  });
}
$('sound-gate').addEventListener('click', () => {
  soundBlocked = false; $('sound-gate').classList.remove('on');
  applyCenter(true); applyAudio();
});

function showLayer(which) {
  $('welcome-screen').style.display = which === 'welcome' ? 'flex' : 'none';
  $('slideshow').style.display = which === 'slideshow' ? 'block' : 'none';
  vid.classList.toggle('hidden', which !== 'video');
  $('yt-embed').style.display = which === 'youtube' ? 'block' : 'none';
}

function startSlideshow(list) {
  if (sameList(list, slides) && slideTimer) return;
  slides = list; slideIdx = 0; clearInterval(slideTimer); slideTimer = null;
  $('slideshow').innerHTML = slides.map((s, i) =>
    `<div class="slide${i === 0 ? ' active' : ''}" style="background-image:url('${encodeURI(s.url)}')"></div>`).join('');
  if (slides.length > 1) slideTimer = setInterval(() => {
    const all = document.querySelectorAll('#slideshow .slide');
    if (!all.length) return;
    all[slideIdx].classList.remove('active');
    slideIdx = (slideIdx + 1) % all.length;
    all[slideIdx].classList.add('active');
  }, CONFIG.slideSeconds * 1000);
}
function stopSlideshow() { clearInterval(slideTimer); slideTimer = null; slides = []; $('slideshow').innerHTML = ''; }

function playVideoAt(i) {
  if (!videoList.length) return;
  videoIdx = (i + videoList.length) % videoList.length;
  vid.src = videoList[videoIdx].url;
  vid.loop = videoList.length === 1 && occPhase !== 'video';
  applyVolumes();
  tryPlay(vid);
}
vid.addEventListener('ended', () => { if (!mixVideoDone()) playVideoAt(videoIdx + 1); });
vid.addEventListener('error', () => {
  if (mixVideoDone()) return;
  if (videoList.length > 1) setTimeout(() => playVideoAt(videoIdx + 1), 1000);
});

function stopVideo() { vid.pause(); vid.removeAttribute('src'); vid.load(); videoList = []; }

function applyCenter(force = false) {
  const center = state?.center || 'welcome';
  if (center === 'video' && state.video.length) {
    stopSlideshow(); showLayer('video'); $('yt-iframe').src = 'about:blank';
    if (force || !sameList(state.video, videoList)) { videoList = state.video; playVideoAt(0); }
    else if (vid.paused) tryPlay(vid);
  } else if (center === 'slideshow' && state.slides.length) {
    stopVideo(); showLayer('slideshow'); $('yt-iframe').src = 'about:blank';
    startSlideshow(state.slides);
  } else if (center === 'youtube' && CONFIG.youtubeId) {
    stopVideo(); stopSlideshow(); showLayer('youtube');
    const id = encodeURIComponent(CONFIG.youtubeId);
    const src = `https://www.youtube.com/embed/${id}?autoplay=1&mute=1&loop=1&playlist=${id}&controls=0`;
    if ($('yt-iframe').src !== src) $('yt-iframe').src = src;
  } else {
    stopVideo(); stopSlideshow(); showLayer('welcome'); $('yt-iframe').src = 'about:blank';
  }
}

/* Music pauses while a video plays with sound, and during prayer pause. */
function musicShouldPlay() {
  if (!state?.musicOn || !musicList.length) return false;
  if (inPrayerPause()) return false;
  if (state.center === 'video' && videoList.length && !state.videoMuted) return false;
  return true;
}
function applyVolumes() {
  const v = Math.max(0, Math.min(100, state?.volume ?? 60)) / 100;
  music.volume = v; vid.volume = v;
  vid.muted = !!state?.videoMuted || inPrayerPause();
}
function playMusicAt(i) {
  if (!musicList.length) return;
  musicIdx = (i + musicList.length) % musicList.length;
  music.src = musicList[musicIdx].url;
  music.loop = musicList.length === 1;
  $('now-music-title').textContent = musicList[musicIdx].title;
}
music.addEventListener('ended', () => { playMusicAt(musicIdx + 1); applyAudio(); });
music.addEventListener('error', () => { if (musicList.length > 1) setTimeout(() => { playMusicAt(musicIdx + 1); applyAudio(); }, 1000); });

function applyAudio(forceRestart = false) {
  if (!state) return;
  const incoming = state.musicOn ? state.music : [];
  const baseChanged = !sameList(incoming, musicList._base || []);
  if (baseChanged || forceRestart) {
    musicList = state.shuffle ? shuffled(incoming) : [...incoming];
    musicList._base = incoming;
    if (musicList.length) playMusicAt(0); else { music.pause(); music.removeAttribute('src'); }
  }
  applyVolumes();
  if (musicShouldPlay()) { if (music.paused && music.src) tryPlay(music); }
  else if (!music.paused) music.pause();
  $('now-music').classList.toggle('on', musicShouldPlay());
}

function runCommand(cmd) {
  if (cmd === 'next_music') { playMusicAt(musicIdx + 1); applyAudio(); }
  else if (cmd === 'next_video') playVideoAt(videoIdx + 1);
  else if (cmd === 'restart') { applyCenter(true); applyAudio(true); }
  else if (cmd === 'reload') location.reload();
}

function nowPlaying() {
  const parts = [];
  if (rawState?.occasion) parts.push('🎉 ' + rawState.occasion.name);
  if (soundBlocked) parts.push('⚠ Sound blocked - touch the TV once');
  if (state?.center === 'video' && videoList.length) parts.push('Video: ' + (videoList[videoIdx]?.title || ''));
  else if (state?.center === 'slideshow' && slides.length) parts.push(`Slideshow (${slides.length} photos)`);
  else if (state?.center === 'youtube') parts.push('YouTube');
  else parts.push('Welcome screen');
  if (state?.musicOn) {
    if (inPrayerPause()) parts.push('Music paused for prayer');
    else if (musicShouldPlay()) parts.push('Music: ' + (musicList[musicIdx]?.title || ''));
    else if (state.center === 'video' && !state.videoMuted) parts.push('Music waiting (video has sound)');
  }
  return parts.join(' · ');
}

async function pollState() {
  try {
    const body = new URLSearchParams({ now_playing: nowPlaying() });
    const r = await fetch(TV.stateUrl, { method: 'POST', body, cache: 'no-store', signal: AbortSignal.timeout(10000) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const s = await r.json();
    if (s.contentVersion !== TV.contentVersion) { location.reload(); return; }
    const first = rawState === null;
    const sig = JSON.stringify(s.occasion || null);
    const changed = first || s.version !== rawState.version || sig !== occSig;
    rawState = s;
    if (sig !== occSig) { occSig = sig; startOccasion(s.occasion); }
    state = deriveState();
    if (changed) { applyCenter(); applyAudio(); }
    if (lastCommandSeq === null) lastCommandSeq = s.commandSeq;           // don't replay old commands on load
    else if (s.commandSeq !== lastCommandSeq) { lastCommandSeq = s.commandSeq; runCommand(s.command); }
  } catch (e) { /* server unreachable: keep playing what we have */ }
}

/* ============ START ============ */
function init() {
  if (CALM) document.body.classList.add('calm');
  ICON.fill();
  fit();
  tick(); setInterval(tick, 1000);
  renderCalendar();
  drawAnalog(); setInterval(drawAnalog, 1000);
  matchPrayerHeight(); addEventListener('resize', matchPrayerHeight);
  if ($('cal-flip')) setInterval(flipCalendar, CAL_SECONDS * 1000);
  applyPhase();
  if (CONFIG.showPrayer) { fetchPrayer(); setInterval(fetchPrayer, 60 * 60 * 1000); }
  fetchWeather(); setInterval(fetchWeather, 10 * 60 * 1000);
  fetchNews(); setInterval(fetchNews, 5 * 60 * 1000);
  fetchArabicNews(); setInterval(fetchArabicNews, 10 * 60 * 1000);
  fetchSite(); setInterval(fetchSite, 5 * 60 * 1000);
  setInterval(renderSky, 60 * 1000);
  startFlag();
  pollState(); setInterval(pollState, 3000);
  initMotion();
  showInsight(); setInterval(showInsight, INSIGHT_SECONDS * 1000);
  if (!CALM) setInterval(particles, 33);      // ~30 fps is plenty and kind to TV sticks
}
init();
})();
