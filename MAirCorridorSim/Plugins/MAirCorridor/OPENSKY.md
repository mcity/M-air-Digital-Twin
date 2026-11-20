# Live air traffic from the OpenSky Network

The planner and the level show the real aircraft over M-City, fetched by
[`Tools/adsb.py`](Tools/adsb.py) from the [OpenSky Network](https://opensky-network.org/). This is
everything needed to make that work well: an account, API credentials, more than one credential,
and a receiver of your own that feeds OpenSky and doubles what you may ask for.

1. [What each kind of account gets](#1-what-each-kind-of-account-gets)
2. [Create an account](#2-create-an-account)
3. [Create an API client and give it to the tools](#3-create-an-api-client-and-give-it-to-the-tools)
4. [More than one client: rotation](#4-more-than-one-client-rotation)
5. [Feed OpenSky with a receiver of your own: 8,000 credits a day](#5-feed-opensky-with-a-receiver-of-your-own-8000-credits-a-day)
6. [Troubleshooting](#6-troubleshooting)
7. [Sources](#7-sources)

Without any of this the traffic still works, anonymously, with a tenth of the credits and a coarser
picture.

## 1. What each kind of account gets

OpenSky meters its REST API in **credits**, refilled daily, counted separately for `/states`,
`/tracks` and `/flights`. The traffic uses only `/states`.

| Account | `/states` credits | Refilled | Time resolution |
| --- | --- | --- | --- |
| Anonymous (no credentials) | 400 | daily | 10 s, the latest state only |
| Registered user | 4,000 | daily | 5 s, up to an hour back |
| **Active feeder** (a receiver of yours online at least 30 % of the month) | **8,000** | daily | 5 s |
| Licensed (by agreement with OpenSky) | 14,400 | **hourly** | 5 s |

A request for the aircraft in a box costs by the box's size: **1 credit up to 25 square degrees**,
2 up to 100, 3 up to 400, 4 beyond that or for the whole world. `adsb.py`'s box around the corridor
(the landscape plus 25 km) is well under 25 square degrees, so **every request costs one credit**.

What that buys, polling all day:

| Credits a day | Sustained interval | `adsb.py` |
| --- | --- | --- |
| 400 | one request every 216 s | anonymous; aircraft are dead reckoned in between |
| 4,000 | every 21.6 s | the default, `--interval 20` |
| 8,000 | every 10.8 s | `--interval 11` |

`adsb.py` reads the credits left from every response (`X-Rate-Limit-Remaining`), prints them, and
never asks faster than every 5 s. Asking faster than an account can sustain only spends the day's
credits by mid-afternoon.

## 2. Create an account

1. Go to [opensky-network.org](https://opensky-network.org/) and choose **Sign up** (top right).
2. Register with your own name and e-mail address, and confirm the address from the e-mail
   OpenSky sends.
3. Sign in. Your account page is where the API client (step 3) and, later, your receiver (step 5)
   appear.

**One account per person.** OpenSky's API is offered for research and non-commercial use under its
[terms of use](https://opensky-network.org/about/terms-of-use), which govern who may hold an
account and how it may be used. Read them before you register. Everyone on the team who wants
credentials should register themselves, rather than one person registering several accounts.

## 3. Create an API client and give it to the tools

Since March 2025 OpenSky accepts only **OAuth2 client credentials**: a client id and a secret,
which `adsb.py` exchanges for a token that lasts 30 minutes and renews by itself. Usernames and
passwords no longer work for the API.

1. Sign in, open your **Account** page and find **API Client**.
2. Create a client. OpenSky shows a **client id** and a **client secret**, and offers them as a
   `credentials.json` download. **The secret is shown once.** Save it now.
3. Put the file at **`<project>\api\credentials.json`**. In this workspace that is
   `C:\Unreal Projects\AirCorridor\MCity_MAir\api\credentials.json`:

   ```json
   { "clientId": "your-client-id", "clientSecret": "your-client-secret" }
   ```

   `adsb.py` looks for `api\credentials.json` in each folder above the plugin, so the project root
   is the natural place. Elsewhere, set `OPENSKY_CREDENTIALS` to the file, or pass `--credentials`.
4. Check it, from `Plugins\MAirCorridor\Tools`:

   ```
   py -3.10 adsb.py --check-credentials            asks the token endpoint; prints no secret
   py -3.10 adsb.py --check-credentials --probe    and spends one credit to read what is left
   py -3.10 adsb.py --once                         what is overhead now
   ```

   `ok` means the secret was accepted. `--probe` shows the credits left, which should be up to
   4,000 at the start of the day.

**Keep the secret out of every repository.** `api\` is in the project's `.gitignore`. Never commit
the file, paste it into a chat or a ticket, or put it in a mission. Nothing in `adsb.py` ever prints,
logs or writes a secret: output names a credential by its label and by a fingerprint, a hash of the
client id. If a secret does leak, delete that client in your OpenSky account and make a new one
(see [Replacing a secret](#replacing-a-secret-without-a-gap)).

## 4. More than one client: rotation

The credentials file can hold a list of clients, and `adsb.py` moves between them:

```json
{
  "clients": [
    { "label": "sean",    "clientId": "...", "clientSecret": "...",                 "added": "2026-11-02" },
    { "label": "lab-pi",  "clientId": "...", "clientSecret": "env:OPENSKY_LAB_SECRET", "added": "2026-11-02" }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `label` | Your name for it, used in every message; never the secret |
| `clientId`, `clientSecret` | From the account's API Client page |
| `added` | A date, used by `--rotation newest-first` |

A secret can be written in the file, or kept out of it: `"env:NAME"` reads an environment variable,
and `"file:C:/path/to/secret.txt"` reads a file of its own.

### Credits belong to the account, not to the client

**Two clients created in the same OpenSky account share that account's credits.** Rotating
between them does not buy a single extra request. `--check-credentials` notices two entries with
the same client id and says so, but it cannot see that two different clients belong to one account,
so keep that in mind when labelling them. Rotation is for two jobs:

- **Replacing a secret without stopping the feed.** This needs only your own account.
- **Spreading the day's requests across accounts that each have their own credits.** For example,
  a teammate's own account, or the account a feeder receiver is registered to (section 5). Each
  account must be a real person's, used under OpenSky's terms. Registering extra accounts only to
  multiply the allowance is not what rotation is for here. If the project needs more than its
  members' accounts provide, a feeder (section 5) doubles an account honestly, and OpenSky licenses
  higher volumes (14,400 credits an hour) by agreement.

### The three policies

```
py -3.10 adsb.py --watch --rotation exhaustion      the default
py -3.10 adsb.py --watch --rotation round-robin
py -3.10 adsb.py --watch --rotation newest-first
py -3.10 adsb.py --watch --credential lab-pi        use only that one
```

| `--rotation` | What it does | Use it for |
| --- | --- | --- |
| `exhaustion` | Stays on one client until its credits are down to 25 or OpenSky refuses it, then moves on | Spending one account at a time through the day |
| `round-robin` | One request each, in turn | Spending several accounts evenly |
| `newest-first` | Prefers the latest `added`; the others are fallbacks | A secret being replaced |

**Failover is automatic.** A client that gets `429 Too Many Requests` is rested for as long as
OpenSky's `X-Rate-Limit-Retry-After-Seconds` says (fifteen minutes if it does not say) and the
request is retried once on the next client. A client whose secret is refused is rested for five
minutes and handed over the same way. Credits and rest periods are remembered between runs in the
system's temporary folder, keyed by a hash of the client id, with no secret in them.

### Replacing a secret without a gap

1. In your OpenSky account, create a new API client.
2. Add it to `credentials.json` beside the old one, with today's date as `added`.
3. `py -3.10 adsb.py --check-credentials`. The new entry must say `ok`. This asks the token
   endpoint every time, so a dead secret cannot pass on a cached token.
4. Run with `--rotation newest-first` and watch the new client serve traffic.
5. Remove the old entry from the file, then delete the old client in OpenSky.

## 5. Feed OpenSky with a receiver of your own: 8,000 credits a day

Aircraft broadcast ADS-B on 1090 MHz. A small radio receiver hears them and sends what it hears to
OpenSky. Keep one online for **at least 30 % of each month** and the account it is registered to
becomes an **active feeder**: **8,000 credits a day instead of 4,000**. OpenSky reassesses this every
two hours, and the new allowance appears after about 50 requests. A receiver near M-City also adds
coverage exactly where the corridor is, and OpenSky's `/states/own` endpoint, which returns what
your own receivers hear, costs no credits at all. (`adsb.py` does not use `/states/own` yet; it
asks `/states/all` for the box.)

**This project's receiver** is the setup below: a Raspberry Pi with an RTL-SDR v5 dongle, running
adsb.im, feeding OpenSky. On the network it serves at <http://adsb-feeder.local>. A second station
is built the same way, and the steps also cover rebuilding this one.

### What to buy

| Part | What to look for |
| --- | --- |
| Computer | A Raspberry Pi 4 (2 GB or more) is the usual choice. Any small Debian or Ubuntu machine, ARM64 or x86, also works. A **Raspberry Pi 5 works with adsb.im but not with OpenSky's old kit image** |
| Power supply | The official one for that Pi. Undervoltage makes the radio drop out |
| microSD card | 16 GB or more, a reputable brand |
| SDR dongle | An RTL-SDR USB receiver. Best is one made for ADS-B with a **built-in 1090 MHz filter and amplifier** (for example the FlightAware Pro Stick Plus). A general-purpose RTL-SDR (this project's receiver uses an RTL-SDR v5) works too, and better with a 1090 MHz filter in line |
| Antenna | A **1090 MHz** antenna, tuned for it, not a wide-band or TV one |
| Coax | As short as the mounting allows, low-loss (LMR-240 or LMR-400 class for runs of several metres) |
| Network | Wired Ethernet if you can; Wi-Fi works |

**The antenna matters more than anything else.** 1090 MHz travels by line of sight: put the
antenna **outdoors, as high as you can, with open sky all round**, such as on a roof or a mast. An
antenna indoors behind a window hears a fraction of the sky. Keep the radio near the antenna and
the coax short, because every metre of cable loses signal.

### Set it up with adsb.im (recommended)

OpenSky's own pre-built receiver image is deprecated. OpenSky itself recommends community images,
and the simplest is [adsb.im](https://adsb.im/home), which runs the decoder and the OpenSky feeder
together and is set up from a web page.

1. **Register** on OpenSky first (section 2) and note your **username**. The receiver is linked to
   your account by it, and the 8,000 credits go to that account. **Create your API client in that
   same account.**
2. **Find the antenna's position**: latitude and longitude to five decimal places (from a map or a
   phone), and its height above sea level in metres, which is the ground elevation plus the height
   of the building or mast.
3. **Flash the card.** Download the adsb.im image for your board from [adsb.im](https://adsb.im/home)
   and write it to the microSD card (Raspberry Pi Imager or balenaEtcher). For Wi-Fi, set it while
   writing the card, or join the `adsb.im-feeder` hotspot after first boot.
4. **Boot it** with the dongle and antenna connected. The first boot takes a few minutes, sometimes
   15 to 20.
5. **Open the setup page** at <http://adsb-feeder.local>, or <http://my.adsb.im> if your network
   does not resolve `.local` names.
6. **Basic setup**: enter the antenna's latitude, longitude and elevation, your time zone, and a
   station name.
7. **Aggregators**: tick **OpenSky Network** and enter your OpenSky **username**. Any other networks
   you tick are your choice and do not affect OpenSky. Click **Setup**.
8. The feeder contacts OpenSky and is given a **serial number**. Note it from the OpenSky section of
   the adsb.im page. It identifies this receiver from now on, and a reinstall must reuse it, or the
   receiver starts again as a new one with no history.

Already running `readsb` or `dump1090`, or prefer Docker? The SDR-Enthusiasts
[`docker-opensky-network`](https://github.com/sdr-enthusiasts/docker-opensky-network) container
feeds OpenSky from an existing decoder's BEAST output (port 30005). It needs `OPENSKY_USERNAME`,
`LAT`, `LONG`, `ALT` (metres) and `BEASTHOST`. Run it once to be given a serial, then always pass it
as `OPENSKY_SERIAL`, or every restart registers a new receiver.

### Check that it counts

1. **Live**: the adsb.im page (<http://adsb-feeder.local>) shows the aircraft being heard (its map
   is `tar1090`), and its OpenSky entry shows the feeder connected. Expect dozens around Ann Arbor
   at most times of day, with Detroit Metro twenty miles east.
2. **On OpenSky**: sign in and find the receiver under your account's receivers. It should show as
   online, with messages arriving. Its public profile shows its range and its uptime.
3. **The credits**: the day after it has been running, OpenSky's own test is that
   **more than 4,000 credits** are left at the start of the UTC day:

   ```
   py -3.10 adsb.py --check-credentials --probe
   ```

   Up to 8,000 means the account is an active feeder. Then poll faster:

   ```
   py -3.10 adsb.py --watch --interval 11 --snapshot <file>
   ```

**Keep it online.** The 30 % is of the month, so a receiver that is off for a long spell falls out
of feeder status until its uptime recovers. Plug it in somewhere it can stay, on a supply that does
not get switched off at night.

## 6. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `--check-credentials` says `REFUSED`, HTTP 401 | The secret is wrong or the client was deleted. Make a new client (section 3) |
| `HTTP 429`, "out of credits" | The day's credits are spent. They refill daily (UTC). Poll less often, add a feeder, or add another member's account |
| Credits left never above 4,000 | The receiver is not linked to this account (wrong username), has been online under 30 % of the month, or fewer than ~50 requests have been made since it qualified |
| The receiver hears nothing | The antenna is not a 1090 MHz one, is indoors, or the coax or dongle is loose. Check the dongle is seen (`lsusb` lists a Realtek RTL2838) |
| It hears a few aircraft, close only | Antenna placement. Move it outside and higher; shorten the coax; use a dongle or filter made for 1090 MHz |
| OpenSky shows a new receiver after a reinstall | The serial was not reused. Set the old serial again (adsb.im's OpenSky settings, or `OPENSKY_SERIAL`) |
| The planner says the feed is `degraded` or `stale` | Requests are failing. `adsb.py --once` prints why. The last good picture is kept and aged, never shown as an empty sky |

## 7. Sources

- OpenSky REST API documentation, for authentication, credit limits, feeder status, credit costs
  and rate-limit headers:
  [openskynetwork.github.io/opensky-api/rest.html](https://openskynetwork.github.io/opensky-api/rest.html)
- OpenSky terms of use:
  [opensky-network.org/about/terms-of-use](https://opensky-network.org/about/terms-of-use)
- OpenSky receiver kit, deprecated, with OpenSky's pointer to community images:
  [github.com/openskynetwork/receiver-kit](https://github.com/openskynetwork/receiver-kit)
- adsb.im feeder image: [adsb.im/home](https://adsb.im/home)
- SDR-Enthusiasts OpenSky feeder container:
  [github.com/sdr-enthusiasts/docker-opensky-network](https://github.com/sdr-enthusiasts/docker-opensky-network)
- How `adsb.py` uses all of this: [Tools/README.md, Live air traffic](Tools/README.md#live-air-traffic)

Figures as of November 2026. OpenSky changes its limits from time to time; the REST documentation
above is the authority.
