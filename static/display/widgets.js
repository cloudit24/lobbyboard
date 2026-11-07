/* The extra widgets from the layout designer: digital clock, countdown, slideshow, weather.
   Plain older JavaScript on purpose, so TV boxes with old browsers run it too. */
(function () {
  var all = function (sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); };
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };

  function clocks() {
    var now = new Date();
    all('.w-digital').forEach(function (el) {
      var h = now.getHours(), d = el.dataset, ampm = '';
      if (d.hours === '12') { ampm = h < 12 ? ' AM' : ' PM'; h = h % 12 || 12; }
      var t = pad(h) + ':' + pad(now.getMinutes()) + (d.seconds ? ':' + pad(now.getSeconds()) : '') + ampm;
      el.querySelector('.w-time').textContent = t;
      var opt = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }, txt = '';
      if (d.date) {
        if (d.lang !== 'ar') txt += now.toLocaleDateString('en-GB', opt);
        if (d.lang !== 'en') txt += (txt ? ' · ' : '') + now.toLocaleDateString('ar-u-nu-arab', opt);
      }
      el.querySelector('.w-date').textContent = txt;
    });
    all('.w-countdown').forEach(function (el) {
      var until = Date.parse(el.dataset.until), out = el.querySelector('.w-count');
      if (isNaN(until)) { out.textContent = '--'; return; }
      var s = Math.floor((until - now) / 1000);
      if (s <= 0) { out.textContent = el.dataset.done || '00:00:00'; return; }
      var days = Math.floor(s / 86400); s %= 86400;
      out.textContent = (days ? days + (days === 1 ? ' day ' : ' days ') : '') +
        pad(Math.floor(s / 3600)) + ':' + pad(Math.floor(s % 3600 / 60)) + ':' + pad(s % 60);
    });
  }

  function slideshows() {
    all('.w-slides').forEach(function (el) {
      var imgs = el.querySelectorAll('img');
      if (imgs.length < 2) return;
      var i = 0;
      setInterval(function () {
        imgs[i].classList.remove('on'); i = (i + 1) % imgs.length; imgs[i].classList.add('on');
      }, (parseInt(el.dataset.seconds, 10) || 8) * 1000);
    });
  }

  var WX = { 0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Cloudy', 45: 'Fog', 48: 'Fog' };
  function wxText(c) {
    if (WX[c]) return WX[c];
    if (c >= 51 && c <= 57) return 'Drizzle';
    if (c >= 61 && c <= 67) return 'Rain';
    if (c >= 80 && c <= 82) return 'Showers';
    if (c >= 95) return 'Thunderstorm';
    return '';
  }
  function weather() {
    var boxes = all('.w-weather');
    if (!boxes.length || !window.TV || !TV.weatherUrl) return;
    fetch(TV.weatherUrl).then(function (r) { return r.json(); }).then(function (d) {
      var c = d && d.weather && d.weather.current;
      if (!c) return;
      boxes.forEach(function (el) {
        var t = c.temperature_2m, f = el.dataset.unit === 'f';
        el.querySelector('.w-wx-temp').textContent = Math.round(f ? t * 9 / 5 + 32 : t) + (f ? '°F' : '°C');
        el.querySelector('.w-wx-text').textContent = wxText(c.weather_code);
      });
    }).catch(function () { /* keep the last good reading */ });
  }

  clocks(); setInterval(clocks, 1000);
  slideshows();
  weather(); setInterval(weather, 15 * 60 * 1000);
})();
