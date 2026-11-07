# Security

Please do not open a public issue for a security problem. Use GitHub's
**Report a vulnerability** button on the repository's *Security* tab instead. You will get an
answer within a week.

When you run LobbyBoard:
- Set a long random `SECRET_KEY` and a strong admin password.
- Keep the admin and desk pages inside your network, or behind Cloudflare Access if you open the
  server to the internet. The TVs only need `/screen/`, `/api/`, `/static/` and `/media/`.
- Back up the `data` volume.
