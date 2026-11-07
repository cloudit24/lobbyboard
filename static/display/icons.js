/* FrontDesk TV icons: one small line-icon set (24x24, drawn with currentColor)
   plus animated weather pictures. Used by screen.js; in the page, any
   <i data-icon="name"></i> is filled in when the screen starts. */
window.TV_ICONS = (() => {
'use strict';

const LINE = {
  mosque:   '<path d="M4 21h16M6 21v-7a6 6 0 0 1 12 0v7M10 21v-4a2 2 0 0 1 4 0v4M12 8V5.5"/><path d="M12.6 2.2a1.6 1.6 0 1 0 1.2 2.6"/>',
  sun:      '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon:     '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  dawn:     '<path d="M12 3v5M9 5.5 12 2.6l3 2.9M3 20h18M5.6 13.6 7 15M2 18h2M20 18h2M17 15l1.4-1.4M8 18a4 4 0 0 1 8 0"/>',
  sunlow:   '<circle cx="12" cy="14" r="3.5"/><path d="M3 20h18M12 6.5v2M5.6 8.6 7 10M17 10l1.4-1.4M3 14h2M19 14h2"/>',
  dusk:     '<path d="M12 8V3M9 5.5 12 8.4l3-2.9M3 20h18M5.6 13.6 7 15M2 18h2M20 18h2M17 15l1.4-1.4M8 18a4 4 0 0 1 8 0"/>',
  night:    '<path d="M16 15.5A6.5 6.5 0 1 1 8.5 5a5.2 5.2 0 0 0 7.5 10.5z"/><path d="M18 3v3M16.5 4.5h3M20.5 9v2M19.5 10h2"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  news:     '<path d="M4 5h13v14a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2z"/><path d="M17 9h3v10a2 2 0 0 1-2 2M7 9h7M7 13h7M7 17h4"/>',
  waves:    '<path d="M2 8c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2M2 13c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2M2 18c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/>',
  swell:    '<path d="M2 17c3 0 4-8 9-8 3 0 4 2.5 2.5 4.5M2 21h20"/><path d="M13 17c2 0 3-4 5.5-4S22 15 22 17"/>',
  timer:    '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M9 2h6"/>',
  thermo:   '<path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z"/><path d="M12 11v6"/>',
  wind:     '<path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8"/>',
  drop:     '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  eye:      '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  uv:       '<circle cx="12" cy="12" r="5"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2 2M17.4 17.4l2 2M4.6 19.4l2-2M17.4 6.6l2-2"/>',
  phone:    '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  mobile:   '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  mail:     '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  globe:    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  pin:      '<path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>',
  chat:     '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01"/>',
  sync:     '<path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v4h-4"/>',
  sound:    '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
  remote:   '<rect x="7" y="2" width="10" height="20" rx="3"/><circle cx="12" cy="8" r="2"/><path d="M10 14h.01M14 14h.01M10 17h.01M14 17h.01"/>',
};

function icon(name, cls = '') {
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${LINE[name] || ''}</svg>`;
}

/* Animated weather pictures (64x64). kind: clear, partly, cloudy, fog, drizzle, rain, showers, storm. */
const CLOUD = 'M19 48h27a11 11 0 0 0 1-22 15 15 0 0 0-28.5-3.5A12.5 12.5 0 0 0 19 48z';
function sunG(x, y, r) {
  const rays = [...Array(8).keys()].map(i => {
    const a = i * Math.PI / 4, c = Math.cos(a), s = Math.sin(a);
    return `<line x1="${x + c * (r + 4)}" y1="${y + s * (r + 4)}" x2="${x + c * (r + 9)}" y2="${y + s * (r + 9)}"/>`;
  }).join('');
  return `<g class="w-rays" style="transform-origin:${x}px ${y}px">${rays}</g><circle cx="${x}" cy="${y}" r="${r}" class="w-sun"/>`;
}
function moonG(x, y, r) {
  return `<path class="w-moon" d="M${x + r * 0.55} ${y - r * 0.85}A${r} ${r} 0 1 0 ${x + r} ${y + r * 0.35}A${r * 0.8} ${r * 0.8} 0 0 1 ${x + r * 0.55} ${y - r * 0.85}z"/>
    <circle cx="${x + r + 8}" cy="${y - r + 2}" r="1.6" class="w-star"/><circle cx="${x + r + 2}" cy="${y - r - 7}" r="1.1" class="w-star s2"/>`;
}
const drops = (n, cls) => [...Array(n).keys()].map(i =>
  `<line x1="${24 + i * 8}" y1="52" x2="${21 + i * 8}" y2="60" class="w-drop ${cls}" style="animation-delay:${i * 0.25}s"/>`).join('');

function weather(kind, night = false) {
  const lit = night ? moonG(24, 22, 11) : sunG(24, 22, 9);
  const body = {
    clear:   night ? moonG(30, 30, 15) : sunG(32, 32, 12),
    partly:  `${lit}<path d="${CLOUD}" class="w-cloud drift"/>`,
    cloudy:  `<path d="${CLOUD}" class="w-cloud back drift2" transform="translate(-6 -8) scale(.85)"/><path d="${CLOUD}" class="w-cloud drift"/>`,
    fog:     `<path d="${CLOUD}" class="w-cloud" transform="translate(0 -6)"/><g class="w-fog"><line x1="8" y1="50" x2="44" y2="50"/><line x1="18" y1="56" x2="56" y2="56"/></g>`,
    drizzle: `<path d="${CLOUD}" class="w-cloud" transform="translate(0 -6)"/>${drops(3, 'thin')}`,
    rain:    `<path d="${CLOUD}" class="w-cloud" transform="translate(0 -6)"/>${drops(4, '')}`,
    showers: `${lit}<path d="${CLOUD}" class="w-cloud" transform="translate(0 -6)"/>${drops(3, '')}`,
    storm:   `<path d="${CLOUD}" class="w-cloud dark" transform="translate(0 -8)"/><path d="M34 40 27 51h7l-4 10 11-14h-7l4-7z" class="w-bolt"/>${drops(2, 'thin')}`,
  }[kind] || '';
  return `<svg class="wx-pic" viewBox="0 0 64 64" aria-hidden="true">${body}</svg>`;
}

/* Moon disc with the real lit part. age = days since new moon, syn = month length. */
function moon(age, syn, size = 48) {
  const r = 20, c = 24, p = age / syn, waxing = p < 0.5, k = Math.cos(2 * Math.PI * p);
  const rx = Math.abs(k) * r;
  const outer = waxing ? 1 : 0, inner = k > 0 ? (waxing ? 0 : 1) : (waxing ? 1 : 0);
  return `<svg class="moon-pic" viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">
    <circle cx="${c}" cy="${c}" r="${r}" class="moon-dark"/>
    <path d="M${c} ${c - r}A${r} ${r} 0 0 ${outer} ${c} ${c + r}A${rx} ${r} 0 0 ${inner} ${c} ${c - r}z" class="moon-lit"/>
  </svg>`;
}

function fill(root = document) {
  root.querySelectorAll('i[data-icon]').forEach(el => { el.outerHTML = icon(el.dataset.icon); });
}

return { icon, weather, moon, fill };
})();
