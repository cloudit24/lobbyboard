# FrontDesk

A self-hosted front-desk system: a **desk dashboard** for the people at
reception and customer care, and a **reception TV** they control.

**Desk dashboard** (`/agent/`), one login, pages depend on your role:
- **Visitors registry** - check people in and out, who is in the building now, search.
- **Enquiries** - emails and website-form messages land in one mailbox; the
  app reads it, sorts each message into a topic (general, membership,
  services...) by keywords and gives it to an agent. Agents reply from the
  dashboard; the customer sees *"Customer Care – <agent name>"*, and your
  official addresses get a copy (CC). Customer replies join the same enquiry.
  Phone and walk-in enquiries can be logged by hand.
- **TV control** - play a welcome screen, photos, videos or playlists with
  background music on any reception TV; upload files (an admin approves them).
- **Secretary** - sees every enquiry and visitor, reassigns work, adds and
  manages agents, and runs reports (Excel export).

**Roles:** Admin (everything, in `/admin/`), Secretary, Reception (TVs,
uploads, visitors), Customer care (enquiries). A person can have several.

**The TV** (`/screen/<name>/`) shows clock, Gregorian and Hijri dates, prayer
times, calendar, sea and weather conditions with a safety badge, news, your
ticker messages, contact details with a QR code - and whatever the desk plays.

**Admin panel** (`/admin/`) - every text and setting: display, mail server,
enquiry topics, roles, dashboard theme (colours, font, name), network
(port, office IP addresses, Cloudflare Tunnel names).

**Logs** - every login, failed login, page visit, change (old → new),
visitor in/out, enquiry, reply, reassignment, upload, review and TV action,
with user and IP. Export as CSV.

No organisation data or branding ships with it: set yours in the admin, or load
it from a private JSON file (see *Your organisation's settings*).

## Run it

Needs Docker.

```bash
cp .env.example .env        # then edit .env: SECRET_KEY, ADMIN_PASSWORD, ALLOWED_HOSTS
docker compose up -d --build
```

Open `http://<server-ip>:8080/admin/` and log in with `ADMIN_USERNAME` /
`ADMIN_PASSWORD` from `.env` (used on first start only - change the password
afterwards).

On the TV's browser open `http://<server-ip>:8080/screen/reception/`
(Admin → Screens shows each screen's address). It is designed at 1920×1080
and scales to any screen size.

The screen moves: its colours follow the sun (dawn, day, dusk, night) and
each panel has its own colour, the sea along the weather card rises and speeds
up with the real waves, a line under the name takes turns showing live facts
(next prayer, sea state, sunset, moon), the welcome screen greets by time of
day, and news headlines take turns in a large spotlight. For the first minute
of each prayer the whole screen shows a calm prayer-time card.

The TV is a display: nobody touches it. A panel steps forward by itself every
75 seconds (never while a video plays), and the only way to interact is with a
phone, through the QR codes. On a slow TV stick add `?motion=low` to the
address to turn the decoration off; if the TV box has "remove animations"
switched on and the screen looks still, add `?motion=full`.

### Your website on the TV

If your website publishes a `tv-feed.json` (office-closed notice, your news,
your services with their order links, your photo gallery), set its address in
Admin → Website feed. The TV then shows a closed-today notice, puts your news
first, turns the contact panel into a slideshow of your services each with its
own "scan to order" QR code, and drifts your photos behind the welcome text.

The flag panel plays `media/display/flag.mp4` if you put one there, otherwise
it draws a waving flag.

### About us (standalone)

Admin → About us: vision, mission, values, strategic objectives and products
(each with an SVG icon), in Arabic and English. When it's on, the news panel
becomes an "About us" slideshow: a welcome, the vision, mission, values, each
objective, then the products with a QR code to your products page. Outside news
then runs only in the ticker. It's stored on this server, so the TV doesn't
depend on any website. To fill it from your website's pages once:

    docker compose exec web python manage.py copy_about       --about-ar URL --about-en URL --products-ar URL --products-en URL --hide trading

The pages need the usual cards (`strategy-card`, `product-card`). Running it
again replaces the copy.

### Occasions (National Day, Eid, celebrations)

Admin → Occasions: a greeting, a look (fireworks in flag colours, Eid lanterns
and crescent, confetti, or none) and what plays: photos with songs, videos with
their sound, videos without sound under songs, or photos with songs and a video
every few minutes. It can fill the whole TV (clock, name and ticker stay). Give
it dates and it starts and stops by itself; agents can also press Play now /
Stop on their TV page. Prayer pauses still apply.

### Sound on the TV

Browsers block sound until someone touches the page once. Either touch/click
the TV once after it starts (it shows a reminder), or start the browser in
kiosk mode with autoplay allowed:

```bash
chromium --kiosk --autoplay-policy=no-user-gesture-required http://<server-ip>:8080/screen/reception/
```

## Enquiries mailbox

1. Create a mailbox for enquiries (e.g. `care@your-domain`) with IMAP and SMTP.
2. Admin → **Mail settings**: fill in the mailbox (IMAP) and sending (SMTP),
   the sender name (`Customer Care – {agent}`), the signature and the official
   addresses to copy. *Test the connection*, then tick *Check the mailbox*.
3. Admin → **Enquiry topics**: words that send an enquiry to each topic, and
   the agents who answer it.
4. Point your website's contact form at that mailbox. Forms that send from a
   no-reply address are understood: the customer is taken from Reply-To or
   from `Name:` / `Email:` / `Phone:` lines in the message.

## Reaching it from outside (Cloudflare Tunnel)

Put `TUNNEL_TOKEN` in `.env`, set the tunnel's public hostname to
`http://proxy:80`, add that hostname in Admin → **Network settings**, then
`docker compose --profile tunnel up -d`. Office addresses (local IP) are added
in the same page - no restart. Changing the **port** is saved there too, then
applied with `scripts/apply-network.ps1` (Windows) or `scripts/apply-network.sh`.

## Everyday use

1. **Admin or secretary:** add each person (secretary: desk → *Team*; admin:
   Users) and give them roles - **Reception** and/or **Customer care**.
   Only admins tick *Staff*. Optionally limit a screen to certain agents.
2. **Agent:** Agent panel → *Upload files* (MP4 video, MP3/M4A music, JPG/PNG
   photos).
3. **Admin:** Dashboard → *Review uploads* → select → *Approve*. Set *Order*,
   and make **Playlists** (videos, music or photos) in the order they should
   play.
4. **Agent:** open the screen in the agent panel → play a video, a playlist,
   photos or music. The TV follows within a few seconds.

Music pauses by itself while a video plays with sound. Optionally it also
pauses for N minutes at each prayer time (Display settings → Prayer times).

## Your organisation's settings

Keep them out of the repository (the `local/` folder is git-ignored):

```bash
docker compose exec web python manage.py export_settings > local/my-settings.json
docker compose cp local/my-settings.json web:/tmp/s.json
docker compose exec web python manage.py import_settings /tmp/s.json
```

## Data and backups

Everything lives in the `data` Docker volume: `db.sqlite3` (settings, users,
logs) and `media/` (uploads). Back up that volume.

## Where the data comes from

All free, no account or key: [Open-Meteo](https://open-meteo.com/) (weather,
waves, sea temperature), [AlAdhan](https://aladhan.com/prayer-times-api)
(prayer times, Hijri date) and the RSS feeds you add. The server fetches and
caches them - the TVs never call outside services. The moon phase is
calculated locally. Sea figures are model estimates, not official warnings.

## Development

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
DEBUG=1 python manage.py migrate
DEBUG=1 python manage.py createsuperuser
DEBUG=1 python manage.py runserver
DEBUG=1 python manage.py test
```

Stack: Django 5.2, SQLite (WAL), Gunicorn + WhiteNoise, nginx for media,
imap-tools (mailbox), openpyxl (Excel reports), optional cloudflared.
Admin look: `static/admin-theme/admin-theme.css`, rules in
[docs/ADMIN-DESIGN.md](docs/ADMIN-DESIGN.md).

## License

MIT - see [LICENSE](LICENSE).

### Arabic headlines (picker under the prayer times)
Add an RSS feed in Admin → News feeds with **Language: Arabic** (e.g. the WAM Arabic RSS link). Arabic feeds show only in the iPhone-style picker; English feeds stay in the news list. The panel hides itself when no Arabic feed has items.

## Design each TV
Admin → Screens → a TV → **Design this TV**. Drag widgets onto a 24 x 12 grid, resize them, click one to
change its settings (text, colours, box look, file, speed...). Widgets: logo, clocks, prayer times, headlines,
video/slideshow, about us, picture, video loop, photo slideshow, text, countdown, QR code, scrolling
announcements, weather, web page. Pick a background photo or video and how dark it is. Tick
**Use this on every TV** to give all TVs the same design, or copy one TV's design to another.

## Announcements from reception
The TV control page starts with **Announcement on the whole screen**: one tap for "On a break",
"Back in 15 minutes", "Prayer" or "Closed", or your own text, with a movement, a colour or a picture/video
behind it, and an optional time after which it goes away by itself.
