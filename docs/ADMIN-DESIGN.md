# Admin design standard

Every admin and agent screen follows one look. The whole look is one file:
`static/admin-theme/admin-theme.css` (after changing it, raise the `?v=` number
in `templates/admin/base_site.html`). Agent-panel extras live
in `static/agent/agent.css` and use only the colour variables below.

## The look in one sentence

Soft grey-blue page, white cards with a thin border and rounded corners, small
grey UPPERCASE section titles, pill-shaped buttons, one blue for actions, red
only for alerts and deleting. Light and dark (the ◐ button).

## Colours (names in the CSS file)

`--header-bg` header · `--button-bg` / `--link-fg` actions · `--fd-page`
page · `--fd-card` cards · `--fd-soft` soft fill · `--fd-line` borders ·
`--fd-muted` secondary text · `--accent` gold (current tab) ·
`--fd-alert` alerts/delete · `--fd-ok` success.

Never type a colour into a template.

## Layout

1. Header: app name + "Admin" or "Agent panel", user links, light/dark.
2. Shortcuts bar (`#fd-bar`): admins get the main sections, agents get their
   screens and *Upload files*. Current item underlined in gold.
3. Title and one line saying what the page is for.
4. Cards (`section.fd-group`) with the content.

No left sidebar - the shortcuts bar and the Dashboard replace it.

## Ready-made pieces

| Piece | Markup |
|---|---|
| Page intro with buttons | `<div class="fd-hello"><div><h1>..</h1><p>..</p></div><div class="fd-quick"><a class="fd-btn fd-btn--primary">..</a></div></div>` |
| Number tiles | `<div class="fd-stats"><a class="fd-stat"><b>12</b><span>Label</span></a></div>` (`is-alert` = red) |
| Card with title | `<section class="fd-group"><h2>Title</h2>..</section>` |
| Link list with icon | `<a class="fd-item"><span class="fd-item-icon">📄</span><span class="fd-item-text"><b>..</b><small>..</small></span></a>` |
| Badge | `<span class="fd-badge is-alert">3 waiting</span>` |
| Main + side | `<div class="fd-layout"><div>..</div><aside>..</aside></div>` |

A custom page extends `admin/base_site.html`, adds `fd-dashboard` to the
body class and gets its context from `admin.site.each_context(request)` (see
`screens/views.py`).

## Words

Plain English. Say what a thing is for. Every Dashboard section has one short
line (`core/dashboard.py`, `GROUPS`); a new model goes there too, or it shows
under "Other". Buttons say what happens: "Play video", "Approve", "Upload".
