# Setting up LobbyBoard

## 1. Install

You need Docker (Docker Desktop on Windows/macOS, Docker Engine on Linux).

```bash
git clone https://github.com/cloudit24/lobbyboard.git
cd lobbyboard
cp .env.example .env
```

Edit `.env`:

| Setting | What to put |
|---|---|
| `SECRET_KEY` | A long random text: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | The first admin, created on first start only |
| `ALLOWED_HOSTS` | The addresses people use to reach the server, e.g. `localhost,192.168.1.20` |
| `PORT` | The port on this computer (default 8080) |
| `TIME_ZONE` | Your time zone, e.g. `Europe/London` |
| `APP_NAME` | The name in the admin header and browser tab |

Then:

```bash
docker compose up -d --build
```

More addresses can be added later in Admin → **Network settings**, without a restart.

## 2. Your organisation

Admin → **Display settings**: names (Arabic and English), logo, welcome text, city and country
(prayer times), the latitude/longitude for weather, contact details and the QR link.

To keep your settings in a file outside the repository (the `local/` folder is git-ignored):

```bash
docker compose exec web python manage.py export_settings > local/my-settings.json
docker compose cp local/my-settings.json web:/tmp/s.json
docker compose exec web python manage.py import_settings /tmp/s.json
```

## 3. The TV

Open `http://<server>:<PORT>/screen/<name>/` in the TV's browser, full screen. Admin → **Screens**
lists every TV and its address; add one row per TV. Pages are designed at 1920 × 1080 and scale
to any screen.

- **Sound**: browsers block sound until someone touches the page once. Either touch the TV once
  after it starts (it shows a reminder), or start the browser in kiosk mode with autoplay allowed:

  ```bash
  chromium --kiosk --autoplay-policy=no-user-gesture-required http://<server>:<PORT>/screen/reception/
  ```

- **Slow TV sticks**: add `?motion=low` to the address to turn the decoration off. If the TV has
  "remove animations" switched on and the screen looks still, add `?motion=full`.
- After you save a design, the TV reloads by itself within a few seconds.

## 4. Reaching it from outside (optional)

With a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):
put `TUNNEL_TOKEN` in `.env`, set the tunnel's public hostname to `http://proxy:80`, add that
hostname in Admin → **Network settings**, then:

```bash
docker compose --profile tunnel up -d
```

Protect the admin and desk pages with Cloudflare Access, or publish only the paths the TVs need:
`/screen/`, `/api/`, `/static/`, `/media/`.

Changing the **port** is saved in Network settings and applied with
`scripts/apply-network.ps1` (Windows) or `scripts/apply-network.sh`.

## 5. Backups and updates

Everything lives in the `data` Docker volume: `db.sqlite3` (settings, users, logs, designs) and
`media/` (uploads). Back up that volume.

To update:

```bash
git pull
docker compose up -d --build
```

Database changes are applied automatically when the container starts.

## Where the data comes from

All free, no account or key: [Open-Meteo](https://open-meteo.com/) (weather, waves, sea
temperature), [AlAdhan](https://aladhan.com/prayer-times-api) (prayer times, Hijri date) and the RSS
feeds you add. The server fetches and caches them; the TVs never call outside services. Sea figures
are model estimates, not official warnings.
