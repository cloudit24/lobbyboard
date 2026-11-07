# Contributing

Thanks for helping. Small, focused changes are easiest to review.

1. Open an issue first for anything bigger than a fix, so we can agree on the approach.
2. Fork, then work on a branch: `feat/...`, `fix/...` or `docs/...`.
3. Run the tests: `DEBUG=1 python manage.py test` (or
   `docker compose run --rm --entrypoint python web manage.py test`).
4. Database changes go through migrations (`python manage.py makemigrations`).
5. Update the docs and `CHANGELOG.md` in the same pull request.
6. Never commit real organisation data, `.env`, keys, or files from `data/` or `local/`.

## Adding a widget

1. Add it to `WIDGETS` in `screens/widgets.py`: label, smallest size, whether several are allowed,
   and its settings fields. The designer builds its form from these.
2. Add `templates/display/widgets/<type>.html`. The widget's settings are in `w.o`.
3. Anything that moves or fetches data goes in `static/display/widgets.js`. Keep it plain older
   JavaScript, because TV browsers are often old.
4. Add a test in `screens/test_layout.py` and a row in `docs/WIDGETS.md`.
