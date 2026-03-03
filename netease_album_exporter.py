"""Netease Cloud Music - Subscribed Albums exporter.

Exports your "Subscribed Albums" list to a clean CSV.

Internal API used:
  https://music.163.com/api/album/sublist?limit=1000&offset=0

Notes on cookies:
- You must be logged in to music.163.com.
- In Chrome DevTools: open Network tab -> refresh the page -> click a request to music.163.com
  -> Headers -> Request Headers -> Cookie -> find the value after "MUSIC_U=".

Security tip: treat your MUSIC_U cookie like a password.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests


API_URL = "https://music.163.com/api/album/sublist"
DEFAULT_LIMIT = 1000
DEFAULT_OUTPUT = "my_netease_albums.csv"
COOKIES_FILE = Path(__file__).resolve().parent / "cookies.json"


DEFAULT_HEADERS = {
    "Referer": "https://music.163.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


@dataclass(frozen=True)
class AlbumRow:
    album_name: str
    artist_names: str
    track_count: int
    album_id: int
    cover_url: str
    subscribe_date: str


class NeteaseApiError(RuntimeError):
    def __init__(self, api_code: int, message: str) -> None:
        super().__init__(f"API returned code={api_code}. {message}".strip())
        self.api_code = api_code
        self.message = message


class LoginManager:
    def __init__(
        self,
        cookies_path: Path = COOKIES_FILE,
        headless_login: bool = False,
        poll_interval_s: float = 2.0,
        timeout_s: Optional[int] = None,
    ) -> None:
        self.cookies_path = cookies_path
        self.headless_login = headless_login
        self.poll_interval_s = max(0.5, poll_interval_s)
        self.timeout_s = timeout_s

    def ensure_music_u(self, *, timeout_s: int = 20) -> str:
        """Return a valid MUSIC_U, using cookies.json or Selenium QR login."""
        music_u = self._load_music_u_from_disk()
        if music_u and self._is_music_u_valid(music_u, timeout_s=timeout_s):
            return music_u

        if music_u:
            print("Stored cookies.json session seems expired; launching browser login...", file=sys.stderr)

        music_u, cookies = self._selenium_login_and_get_music_u(timeout_s=timeout_s)
        self._save_music_u_to_disk(music_u, cookies=cookies)
        return music_u

    def _load_music_u_from_disk(self) -> str:
        if not self.cookies_path.exists():
            return ""

        try:
            raw = self.cookies_path.read_text(encoding="utf-8")
            obj = json.loads(raw)
        except Exception:  # noqa: BLE001
            return ""

        if isinstance(obj, dict):
            music_u = obj.get("music_u")
            if isinstance(music_u, str) and music_u.strip():
                return music_u.strip()

            cookies = obj.get("cookies")
            if isinstance(cookies, list):
                for c in cookies:
                    if isinstance(c, dict) and c.get("name") == "MUSIC_U" and c.get("value"):
                        return str(c["value"]).strip()

        if isinstance(obj, list):
            for c in obj:
                if isinstance(c, dict) and c.get("name") == "MUSIC_U" and c.get("value"):
                    return str(c["value"]).strip()

        return ""

    def _save_music_u_to_disk(self, music_u: str, cookies: Optional[List[Dict[str, Any]]] = None) -> None:
        payload: Dict[str, Any] = {
            "music_u": music_u,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        if cookies is not None:
            payload["cookies"] = cookies

        try:
            self.cookies_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"Warning: failed to write {self.cookies_path.name}: {e}", file=sys.stderr)

    def _is_music_u_valid(self, music_u: str, *, timeout_s: int) -> bool:
        try:
            with requests.Session() as session:
                session.headers.update(DEFAULT_HEADERS)
                session.cookies.set("MUSIC_U", music_u, domain="music.163.com", path="/")
                _request_page(session, limit=1, offset=0, timeout_s=timeout_s)
            return True
        except NeteaseApiError as e:
            if e.api_code == 301:
                return False
            # Other API codes are unexpected; treat as invalid but show the reason.
            print(str(e), file=sys.stderr)
            return False
        except Exception as e:  # noqa: BLE001
            print(f"Login check failed: {e}", file=sys.stderr)
            return False

    def _selenium_login_and_get_music_u(self, *, timeout_s: int) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        # Lazy imports so pure-requests usage still starts quickly.
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        options = Options()
        if self.headless_login:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            raise RuntimeError(
                "Failed to launch Chrome via Selenium. "
                "Make sure Google Chrome is installed and try again. "
                f"Details: {e}"
            ) from e

        try:
            driver.set_window_size(1100, 800)
        except Exception:  # noqa: BLE001
            pass

        print("A Chrome window will open for login.", file=sys.stderr)
        print("Please scan the QR code in the browser window to login.", file=sys.stderr)
        if self.headless_login:
            print(
                "Note: --headless-login is enabled; QR scanning may not be possible headlessly.",
                file=sys.stderr,
            )

        try:
            driver.get("https://music.163.com/#/login")

            start = time.time()
            while True:
                cookie = None
                try:
                    cookie = driver.get_cookie("MUSIC_U")
                except Exception:  # noqa: BLE001
                    cookie = None

                if cookie and cookie.get("value"):
                    music_u = str(cookie["value"]).strip()
                    if music_u and self._is_music_u_valid(music_u, timeout_s=timeout_s):
                        try:
                            all_cookies = driver.get_cookies()
                        except Exception:  # noqa: BLE001
                            all_cookies = None
                        return music_u, all_cookies

                if self.timeout_s is not None and (time.time() - start) > self.timeout_s:
                    raise RuntimeError("Login timed out waiting for MUSIC_U cookie.")

                time.sleep(self.poll_interval_s)
        finally:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass


def _extract_music_u(cookie_input: str) -> str:
    """Accepts either a raw MUSIC_U value or a full Cookie header string."""
    value = cookie_input.strip()
    if not value:
        return ""

    # If user pasted a full cookie header, try extracting MUSIC_U.
    # e.g. "MUSIC_U=xxxx; __csrf=yyyy; ..."
    upper = value.upper()
    if "MUSIC_U=" in upper:
        # Find case-insensitively.
        idx = upper.find("MUSIC_U=")
        sub = value[idx + len("MUSIC_U=") :]
        # Ends at semicolon if present.
        semi = sub.find(";")
        return (sub if semi == -1 else sub[:semi]).strip()

    # Otherwise assume it's the raw MUSIC_U value.
    return value


def _ms_to_yyyy_mm_dd(ts: Optional[int]) -> str:
    if not ts:
        return ""
    # Some timestamps may be in seconds; most are ms.
    if ts < 10_000_000_000:  # ~2286-11-20 in seconds
        seconds = ts
    else:
        seconds = ts / 1000.0
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d")


def _join_artist_names(album_obj: Dict[str, Any]) -> str:
    artists = album_obj.get("artists")
    if isinstance(artists, list):
        names = [a.get("name", "") for a in artists if isinstance(a, dict)]
        names = [n for n in names if n]
        return ", ".join(names)

    # Fallbacks seen in some NCM objects.
    artist = album_obj.get("artist")
    if isinstance(artist, dict) and artist.get("name"):
        return str(artist["name"])

    return ""


def _parse_album(album_obj: Dict[str, Any]) -> AlbumRow:
    return AlbumRow(
        album_name=str(album_obj.get("name", "")),
        artist_names=_join_artist_names(album_obj),
        track_count=int(album_obj.get("size") or 0),
        album_id=int(album_obj.get("id") or 0),
        cover_url=str(album_obj.get("picUrl", "")),
        subscribe_date=_ms_to_yyyy_mm_dd(album_obj.get("subTime")),
    )


def _request_page(
    session: requests.Session,
    limit: int,
    offset: int,
    timeout_s: int,
) -> Dict[str, Any]:
    resp = session.get(
        API_URL,
        params={"limit": limit, "offset": offset},
        timeout=timeout_s,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to decode JSON: {e}. Body: {resp.text[:200]}") from e

    if payload.get("code") != 200:
        # Common failures: 301 not logged in, 302/403 etc.
        code = int(payload.get("code") or 0)
        msg = str(payload.get("msg") or payload.get("message") or "").strip()
        if code == 301 and not msg:
            msg = "Not logged in (cookie expired)."
        raise NeteaseApiError(code, msg)

    return payload


def fetch_all_albums(
    music_u: str,
    limit: int = DEFAULT_LIMIT,
    timeout_s: int = 20,
    sleep_s: float = 0.0,
) -> List[AlbumRow]:
    rows: List[AlbumRow] = []

    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)
        session.cookies.set("MUSIC_U", music_u, domain="music.163.com", path="/")
        offset = 0
        seen_ids: set[int] = set()

        while True:
            payload = _request_page(session, limit=limit, offset=offset, timeout_s=timeout_s)
            data = payload.get("data")
            if not isinstance(data, list):
                raise RuntimeError("Unexpected API response: missing/invalid 'data' list.")

            if not data:
                break

            new_count = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                row = _parse_album(item)
                if row.album_id and row.album_id in seen_ids:
                    continue
                if row.album_id:
                    seen_ids.add(row.album_id)
                rows.append(row)
                new_count += 1

            has_more = payload.get("hasMore")
            offset += len(data)

            if sleep_s > 0:
                time.sleep(sleep_s)

            if has_more is False:
                break

            # If server doesn't provide hasMore, stop when page isn't full.
            if has_more is None and len(data) < limit:
                break

            # Safety: if we stopped making progress, break.
            if new_count == 0:
                break

    return rows


def write_csv(rows: Sequence[AlbumRow], output_path: str) -> None:
    fieldnames = [
        "Album Name",
        "Artist Name(s)",
        "Track Count",
        "Album ID",
        "Cover Image URL",
        "Subscribe Time",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "Album Name": r.album_name,
                    "Artist Name(s)": r.artist_names,
                    "Track Count": r.track_count,
                    "Album ID": r.album_id,
                    "Cover Image URL": r.cover_url,
                    "Subscribe Time": r.subscribe_date,
                }
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export Netease Cloud Music subscribed albums to CSV.",
    )
    parser.add_argument(
        "--music-u",
        default="",
        help="Your MUSIC_U cookie value (or paste full Cookie header containing MUSIC_U=...).",
    )
    parser.add_argument(
        "--headless-login",
        action="store_true",
        help="Run the Selenium login browser in headless mode (not recommended for QR login).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Page size for API calls (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request timeout seconds (default: 20).",
    )
    args = parser.parse_args(argv)

    music_u = _extract_music_u(args.music_u)
    if not music_u:
        # Automated path: cookies.json -> validate -> Selenium QR login.
        try:
            manager = LoginManager(headless_login=bool(args.headless_login))
            music_u = manager.ensure_music_u(timeout_s=max(1, args.timeout))
        except KeyboardInterrupt:
            print("Login cancelled.", file=sys.stderr)
            return 130
        except Exception as e:  # noqa: BLE001
            print(f"Error during automated login: {e}", file=sys.stderr)
            print("\nFallback: you can still pass --music-u manually.", file=sys.stderr)
            return 2

    if not music_u:
        print("No MUSIC_U available. Aborting.", file=sys.stderr)
        return 2

    try:
        rows = fetch_all_albums(music_u=music_u, limit=max(1, args.limit), timeout_s=max(1, args.timeout))
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1

    write_csv(rows, args.output)
    print(f"Exported {len(rows)} albums -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
