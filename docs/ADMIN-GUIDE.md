# Admin guide

## Roles
- **Admins** - everything, including this admin panel (also tick *Staff status*).
- **Secretaries** - desk dashboard: all enquiries and visitors, reassign, Team, Reports, TVs.
- **Reception** - TVs, uploads, visitors registry.
- **Customer care** - enquiries in their topics.

## Add an agent
Easiest: a secretary uses desk → *Team* → *Add agent*. Or here: Users → Add
user → name and password → Save; leave *Staff status* unticked; add the roles
(Reception, Customer care); fill *Name customers see*. They log in at `/login/`.
Secretaries themselves are added here (role *Secretaries*).

## Set up the enquiries mailbox
Mail settings: mailbox login (IMAP), sending (SMTP), send-from address, sender
name (`Customer Care – {agent}`), signature, official CC addresses. Save, press
*Test the connection*, then tick *Check the mailbox*. Enquiry topics: keywords
and agents per topic; one topic is the default.

## Network
Network settings: office IP addresses and tunnel names work at once. A new port
is applied on the server with `scripts/apply-network.ps1` / `.sh`.

## Theme
Dashboard theme: name, colours, font of the desk dashboard. (The TV screen and
this admin panel keep their own look.)

## Limit a screen to some agents
Screens → the screen → tick the agents in *Agents*. Nobody ticked = every agent.

## Add a TV
Screens → Add screen → name (e.g. "Main hall") and short name (e.g.
`main-hall`). Open the address shown on that TV's browser.

## Approve uploads
Dashboard shows *Uploads waiting for review*. Open it, tick files, choose
*Approve* (or *Reject*, then open each file and write a note - the agent sees
it). Only approved files can be played.

## Put files in order / make playlists
Media files: the *Order* column (lower first) - edit and Save. Playlists → Add
→ name, kind (Videos, Music or Photos) → add files with their order. Agents
then see the playlist in their panel.

## Change what the screen shows
Display settings: names, logo, welcome text, YouTube video, prayer city and
method, pause-for-prayer minutes, sea point and safety limits, contact box, QR
link, news on/off, seconds per photo, how long to keep logs. Open screens pick
up the change within a few seconds.

News feeds: RSS addresses, tried in order. Ticker messages: your own lines in
the bottom bar, optionally with start/end times.

## Read the logs
Logs: filter by type (Login, Login failed, Changed, Deleted, Agent action,
Upload, Upload reviewed, Screen online, Page visit), by user, or by date.
Open a row to see details (old → new values). Select rows → *Export as CSV*.
Rows older than *Keep logs for* are deleted each night.

## Undo a change
Every settings page, file, playlist and screen has *History* (top right) -
open an old version and *Revert*.

## Send a topic's work to the right cost centre
Enquiry topics → the topic → **Department / cost centre**. That decides whose
numbers it counts towards, and which address replies come from.
