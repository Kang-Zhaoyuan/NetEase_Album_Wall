# NetEase_Album_Wall
网易云音乐专辑墙 / Netease Cloud Music tools

## Netease Music Album Exporter

Exports your **Subscribed Albums** (收藏的专辑 / 订阅专辑) from Netease Cloud Music to a clean CSV.

- Internal API: `https://music.163.com/api/album/sublist?limit=1000&offset=0`
- Output: `my_netease_albums.csv` (encoded as **utf-8-sig** so Chinese displays correctly in Excel)

### Requirements

- Python 3.9+
- Install dependencies:
	- `pip install -r requirements.txt`

### Usage

- Run:
	- `python netease_album_exporter.py`
	- Or pass cookie directly: `python netease_album_exporter.py --music-u "<YOUR_MUSIC_U>"`

When you run without `--music-u`:

- The script checks for `cookies.json` next to the script.
- If missing/expired, it opens a Chrome window at https://music.163.com/#/login
- Scan the QR code to login; once a valid `MUSIC_U` cookie is detected, the browser closes automatically.

Optional:

- `--headless-login`: run the Selenium login browser in headless mode (not recommended for QR login).

The script will export:

- Album Name
- Artist Name(s)
- Track Count
- Album ID
- Cover Image URL
- Subscribe Time (YYYY-MM-DD)

### How to find your MUSIC_U cookie

1. Log in to https://music.163.com/ in Chrome.
2. Open DevTools (`F12`) -> **Network**.
3. Refresh the page, click any request to `music.163.com`.
4. In **Headers** -> **Request Headers** -> **Cookie**, find `MUSIC_U=...`.

Security note: treat `MUSIC_U` like a password.
