"""
IGDB API client for fetching game metadata (cover art, year, genre).
Credentials are stored in %APPDATA%/RetroPickerWheel/igdb_config.json.

Obtain a Client ID and Client Secret by registering an application at
https://dev.twitch.tv/console/apps
"""

import os
import sys
import json
import threading
import urllib.request
import urllib.parse
import urllib.error
import time
import datetime


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    d = os.path.join(base, "RetroPickerWheel")
    os.makedirs(d, exist_ok=True)
    return d


_CONFIG_FILE = os.path.join(_data_dir(), "igdb_config.json")
_CACHE_DIR   = os.path.join(_data_dir(), "igdb_cache")


def _safe_year_from_timestamp(value):
    """Best-effort conversion of IGDB timestamp-like values to year."""
    if value is None:
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None

    # Some sources provide milliseconds; normalize to seconds.
    if abs(ts) > 100_000_000_000:
        ts = ts / 1000.0

    try:
        return datetime.datetime.utcfromtimestamp(ts).year
    except (OverflowError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Bundled credentials (credentials.py, not committed to version control)
# ---------------------------------------------------------------------------

def _bundled_credentials():
    """Return (client_id, client_secret) from credentials.py, or (None, None)."""
    try:
        import credentials as _creds
        cid = getattr(_creds, "IGDB_CLIENT_ID", "").strip()
        sec = getattr(_creds, "IGDB_CLIENT_SECRET", "").strip()
        if cid and sec:
            return cid, sec
    except ImportError:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    """Return the stored IGDB config dict, or {} if none exists.

    Bundled credentials from credentials.py take precedence over any
    user-saved config so the app works out of the box.
    """
    cid, sec = _bundled_credentials()
    if cid and sec:
        return {"client_id": cid, "client_secret": sec}

    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg):
    """Persist the IGDB config dict to disk."""
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def is_configured():
    """Return True when client_id and client_secret are both set."""
    cfg = load_config()
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


# ---------------------------------------------------------------------------
# OAuth token
# ---------------------------------------------------------------------------

def _get_access_token(client_id, client_secret):
    """
    Return a valid Twitch OAuth access token (fetches/refreshes as needed).
    Also returns the updated config dict so callers can use it immediately.
    """
    cfg = load_config()
    token      = cfg.get("access_token")
    expires_at = cfg.get("token_expires_at", 0)

    # Re-use cached token if still valid (keep a 1-hour safety buffer)
    if token and time.time() < expires_at - 3600:
        return token, cfg

    url  = "https://id.twitch.tv/oauth2/token"
    data = urllib.parse.urlencode({
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "client_credentials",
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())

    token      = body["access_token"]
    expires_in = body.get("expires_in", 5_184_000)   # default 60 days
    cfg["access_token"]      = token
    cfg["token_expires_at"]  = time.time() + expires_in
    save_config(cfg)
    return token, cfg


# ---------------------------------------------------------------------------
# Core metadata fetch
# ---------------------------------------------------------------------------

def fetch_game_metadata(game_name, console_name=None):
    """
    Look up *game_name* on IGDB and return a dict with any of:
        year       (int)
        genres     (list[str])
        cover_url  (str)
        error      (str)  — present only on failure
    
    If console_name is provided, searches specifically for games on that console.
    """
    cfg           = load_config()
    client_id     = cfg.get("client_id")
    client_secret = cfg.get("client_secret")

    if not client_id or not client_secret:
        return {"error": "not_configured"}

    try:
        token, _ = _get_access_token(client_id, client_secret)
    except Exception as exc:
        return {"error": f"Auth error: {exc}"}

    headers = {
        "Client-ID":     client_id,
        "Authorization": f"Bearer {token}",
        "Content-Type":  "text/plain",
    }

    # --- Get platform ID if console name provided ---
    platform_id = None
    if console_name:
        try:
            all_platforms = fetch_all_platforms()
            for p in all_platforms:
                if p["name"].lower() == console_name.lower():
                    platform_id = p["id"]
                    break
        except Exception:
            pass

    # --- Search for the game ---
    safe_name = game_name.replace("\\", "\\\\").replace('"', '\\"')
    
    if platform_id:
        # Search specifically on this platform for exact name match
        query = (
            f'search "{safe_name}"; '
            f"fields name,cover,first_release_date,genres,platforms; "
            f"where platforms = ({platform_id}); "
            f"limit 10;"
        )
    else:
        # Broad search if no console specified
        query = (
            f'search "{safe_name}"; '
            f"fields name,cover,first_release_date,genres,platforms; "
            f"limit 10;"
        )
    
    try:
        req = urllib.request.Request(
            "https://api.igdb.com/v4/games",
            data=query.encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            games = json.loads(resp.read())
    except Exception as exc:
        return {"error": f"Search failed: {exc}"}

    if not games:
        return {"error": "not_found"}

    # --- Select the game: prioritize exact name match ---
    game = None
    
    # First pass: exact name match (case-insensitive)
    for g in games:
        if g.get("name", "").lower() == game_name.lower():
            game = g
            break
    
    # Fall back to first result if no exact match
    if not game:
        game = games[0]

    result = {}

    # --- Release year ----------------------------------------------------------
    if "first_release_date" in game:
        year = _safe_year_from_timestamp(game["first_release_date"])
        if year is not None:
            result["year"] = year

    # --- Genres ----------------------------------------------------------------
    if "genres" in game:
        genre_ids   = ",".join(str(g) for g in game["genres"])
        genre_query = f"where id = ({genre_ids}); fields name; limit 10;"
        try:
            req = urllib.request.Request(
                "https://api.igdb.com/v4/genres",
                data=genre_query.encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                genres = json.loads(resp.read())
            result["genres"] = [g["name"] for g in genres]
        except Exception:
            pass

    # --- Platform names ---------------------------------------------------------
    if "platforms" in game and isinstance(game["platforms"], list):
        platform_ids = [pid for pid in game["platforms"] if isinstance(pid, int)]
        if platform_ids:
            id_str = ",".join(str(pid) for pid in platform_ids)
            platform_query = f"where id = ({id_str}); fields id,name; limit {len(platform_ids)};"
            try:
                req = urllib.request.Request(
                    "https://api.igdb.com/v4/platforms",
                    data=platform_query.encode(),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    platforms = json.loads(resp.read())

                name_by_id = {
                    p.get("id"): p.get("name")
                    for p in platforms
                    if p.get("id") is not None and p.get("name")
                }
                ordered_names = [name_by_id[pid] for pid in platform_ids if pid in name_by_id]
                if ordered_names:
                    result["platforms"] = ordered_names
            except Exception:
                pass

    # --- Cover art URL ---------------------------------------------------------
    if "cover" in game:
        cover_id    = game["cover"]
        cover_query = f"where id = {cover_id}; fields image_id; limit 1;"
        try:
            req = urllib.request.Request(
                "https://api.igdb.com/v4/covers",
                data=cover_query.encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                covers = json.loads(resp.read())
            if covers:
                image_id = covers[0]["image_id"]
                result["cover_url"] = (
                    "https://images.igdb.com/igdb/image/upload/"
                    f"t_cover_big/{image_id}.jpg"
                )
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Platform (console) browsing
# ---------------------------------------------------------------------------

# IGDB platform category IDs commonly used for gaming hardware.
# 1=Console, 2=Arcade, 5=Portable console, 6=Computer.
_CONSOLE_CATEGORIES = (1, 2, 5, 6)


def _igdb_post(endpoint, query, headers):
    """POST *query* to an IGDB API *endpoint* and return the parsed JSON list."""
    last_exc = None
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://api.igdb.com/v4/{endpoint}",
            data=query.encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < 3:
                retry_after = exc.headers.get("Retry-After")
                try:
                    wait_s = float(retry_after) if retry_after is not None else 1.0
                except (TypeError, ValueError):
                    wait_s = 1.0
                wait_s = max(0.5, min(wait_s, 8.0)) + attempt * 0.75
                time.sleep(wait_s)
                continue

            try:
                detail = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                detail = ""
            msg = f"HTTP {exc.code} on /{endpoint}."
            if detail:
                msg += f" {detail}"
            msg += f" Query: {query[:220]}"
            raise RuntimeError(msg) from exc

    # Defensive fallback; loop should return or raise before this point.
    if last_exc is not None:
        raise RuntimeError(f"HTTP {last_exc.code} on /{endpoint}.") from last_exc
    raise RuntimeError(f"Unknown error on /{endpoint}.")


def _make_headers():
    cfg           = load_config()
    client_id     = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    if not client_id or not client_secret:
        raise RuntimeError("not_configured")
    token, _ = _get_access_token(client_id, client_secret)
    return {
        "Client-ID":     client_id,
        "Authorization": f"Bearer {token}",
        "Content-Type":  "text/plain",
    }


def fetch_all_platforms():
    """
    Return a list of dicts for every IGDB console/portable platform.

    Each dict has:
        id          (int)
        name        (str)
        year        (int | None)   first_release_date year, None if unknown
        category    (int)          1 = console, 5 = portable
    """
    headers = _make_headers()

    platforms = []
    offset    = 0
    page_size = 500

    while True:
        query = (
            f"fields id,name,category; "
            f"limit {page_size}; offset {offset};"
        )
        try:
            page = _igdb_post("platforms", query, headers)
        except RuntimeError as exc:
            # Fallback for stricter IGDB query parsing: fetch all then filter locally.
            if "HTTP 400" not in str(exc):
                raise
            platforms = []
            offset = 0
            while True:
                fallback_query = (
                    f"fields id,name,category; "
                    f"limit {page_size}; offset {offset};"
                )
                page = _igdb_post("platforms", fallback_query, headers)
                if not page:
                    break
                platforms.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
            break

        if not page:
            break
        platforms.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    year_by_platform = _fetch_platform_years(headers)

    result = []
    for p in platforms:
        raw_category = p.get("category")
        try:
            category = int(raw_category) if raw_category is not None else None
        except (TypeError, ValueError):
            category = None

        # Keep known gaming hardware categories.
        if category is not None and category not in _CONSOLE_CATEGORIES:
            continue
        year = year_by_platform.get(p["id"])
        result.append({
            "id":       p["id"],
            "name":     p["name"],
            "year":     year,
            "category": category if category is not None else 1,
        })

    # If category metadata is unusable for this API key, fall back to named platforms.
    if not result:
        for p in platforms:
            name = str(p.get("name", "")).strip()
            if not name:
                continue
            result.append({
                "id": p["id"],
                "name": name,
                "year": year_by_platform.get(p["id"]),
                "category": 1,
            })

    # Sort: platforms with a known year first (ascending), unknowns at the end
    result.sort(key=lambda p: (p["year"] is None, p["year"] or 9999, p["name"].lower()))
    return result


def _fetch_platform_years(headers):
    """
    Best-effort platform -> year mapping.

    Some IGDB schemas do not expose `first_release_date` on `platforms`.
    This fallback derives a year from the earliest platform version release.
    Returns an empty dict when the related endpoints/fields are unavailable.
    """
    try:
        # 1) Platform versions give us: platform_version_id -> platform_id
        version_to_platform = {}
        offset = 0
        page_size = 500
        while True:
            query = (
                f"fields id,platform; "
                f"limit {page_size}; offset {offset};"
            )
            versions = _igdb_post("platform_versions", query, headers)
            if not versions:
                break
            for v in versions:
                vid = v.get("id")
                pid = v.get("platform")
                if vid is not None and pid is not None:
                    version_to_platform[vid] = pid
            if len(versions) < page_size:
                break
            offset += page_size

        if not version_to_platform:
            return {}

        # 2) Version release dates give us: platform_version_id -> date
        year_by_platform = {}
        offset = 0
        while True:
            query = (
                f"fields platform_version,date; "
                f"limit {page_size}; offset {offset};"
            )
            release_rows = _igdb_post("platform_version_release_dates", query, headers)
            if not release_rows:
                break
            for row in release_rows:
                vid = row.get("platform_version")
                dt = row.get("date")
                if vid is None or dt is None:
                    continue
                pid = version_to_platform.get(vid)
                if pid is None:
                    continue
                year = _safe_year_from_timestamp(dt)
                if year is None:
                    continue
                prev = year_by_platform.get(pid)
                if prev is None or year < prev:
                    year_by_platform[pid] = year
            if len(release_rows) < page_size:
                break
            offset += page_size

        return year_by_platform
    except Exception:
        # Year enrichment is optional; if IGDB rejects these endpoints/fields,
        # we still return usable platform data without years.
        return {}


def fetch_games_for_platform(platform_id, regions=None, limit=500):
    """
    Return a list of dicts for games released on *platform_id*.

    *regions* is an optional list of IGDB region IDs to filter by:
        1  = Europe
        2  = North America
        3  = Australia
        4  = New Zealand
        5  = Japan
        6  = China
        7  = Asia
        8  = Worldwide
        9  = Korea
        10 = Brazil

    Each dict has:
        id        (int)
        name      (str)
        year      (int | None)
        region    (int | None)    as returned by IGDB release_dates
    """
    headers = _make_headers()

    def _fetch_release_dates(use_regions):
        rows = []
        offset = 0
        while True:
            where_parts = [f"platform = {platform_id}"]
            if use_regions and regions:
                region_str = ",".join(str(r) for r in regions)
                where_parts.append(f"region = ({region_str})")
            where_clause = " & ".join(where_parts)
            rd_query = (
                f"where {where_clause}; "
                f"fields game,region,date; "
                f"limit {limit}; offset {offset};"
            )
            page = _igdb_post("release_dates", rd_query, headers)
            if not page:
                break
            rows.extend(page)
            if len(page) < limit:
                break
            offset += limit
        return rows

    release_dates = _fetch_release_dates(use_regions=True)
    # If the selected regions have no rows, fall back to all regions.
    if not release_dates and regions:
        release_dates = _fetch_release_dates(use_regions=False)

    if not release_dates:
        # Final fallback: query games directly by platform membership.
        return _fetch_games_direct_from_platform(platform_id, headers, limit=limit)

    # Deduplicate: keep the earliest release per game, track region
    game_map = {}  # game_id -> {region, year}
    for rd in release_dates:
        gid  = rd.get("game")
        if gid is None:
            continue
        year = None
        if "date" in rd:
            year = _safe_year_from_timestamp(rd["date"])
        region = rd.get("region")
        if gid not in game_map or (year and (game_map[gid]["year"] is None or year < game_map[gid]["year"])):
            game_map[gid] = {"region": region, "year": year}

    if not game_map:
        return []

    # Fetch game names in batches of 500
    game_ids  = list(game_map.keys())
    all_games = []
    for chunk_start in range(0, len(game_ids), 500):
        chunk  = game_ids[chunk_start : chunk_start + 500]
        id_str = ",".join(str(g) for g in chunk)
        q      = f"where id = ({id_str}); fields id,name; limit 500;"
        batch  = _igdb_post("games", q, headers)
        all_games.extend(batch)

    result = []
    for g in all_games:
        meta = game_map.get(g["id"], {})
        result.append({
            "id":     g["id"],
            "name":   g["name"],
            "year":   meta.get("year"),
            "region": meta.get("region"),
        })

    result.sort(key=lambda g: (g["year"] is None, g["year"] or 9999, g["name"].lower()))
    return result


def _fetch_games_direct_from_platform(platform_id, headers, limit=500):
    """Fallback when release_dates returns nothing: fetch games from platforms."""
    all_games = []
    offset = 0
    while True:
        query = (
            f"where platforms = ({platform_id}); "
            f"fields id,name,first_release_date; "
            f"limit {limit}; offset {offset};"
        )
        page = _igdb_post("games", query, headers)
        if not page:
            break
        all_games.extend(page)
        if len(page) < limit:
            break
        offset += limit

    result = []
    for g in all_games:
        year = None
        if g.get("first_release_date"):
            year = _safe_year_from_timestamp(g["first_release_date"])
        result.append({
            "id": g["id"],
            "name": g.get("name", ""),
            "year": year,
            "region": None,
        })
    result.sort(key=lambda g: (g["year"] is None, g["year"] or 9999, g["name"].lower()))
    return result


# IGDB region ID -> human-readable label
REGION_LABELS = {
    1:  "Europe",
    2:  "North America",
    3:  "Australia",
    4:  "New Zealand",
    5:  "Japan",
    6:  "China",
    7:  "Asia",
    8:  "Worldwide",
    9:  "Korea",
    10: "Brazil",
}


# ---------------------------------------------------------------------------
# Cover image download (disk-cached)
# ---------------------------------------------------------------------------

def fetch_cover_bytes(cover_url):
    """
    Download cover image bytes.  Results are cached on disk in
    %APPDATA%/RetroPickerWheel/igdb_cache/.
    Raises on network error.
    """
    os.makedirs(_CACHE_DIR, exist_ok=True)
    filename   = cover_url.split("/")[-1]
    cache_path = os.path.join(_CACHE_DIR, filename)

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    req = urllib.request.Request(
        cover_url, headers={"User-Agent": "RetroPickerWheel/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()

    with open(cache_path, "wb") as f:
        f.write(data)
    return data


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

def fetch_metadata_async(game_name, console_name, schedule_fn, callback):
    """
    Fetch metadata in a background thread, then deliver the result dict on
    the tkinter main thread via ``schedule_fn(0, callback, result)``.

    *schedule_fn* should be ``app.after``.
    """
    def _worker():
        result = fetch_game_metadata(game_name, console_name)
        if "cover_url" in result:
            try:
                result["cover_data"] = fetch_cover_bytes(result["cover_url"])
            except Exception:
                pass   # cover unavailable; text metadata still shown
        schedule_fn(0, callback, result)

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

def open_settings_dialog(app, on_save=None):
    """
    Open a modal dialog for configuring IGDB Client ID / Client Secret.
    *on_save* (optional) is called with no arguments after credentials are saved.
    """
    import tkinter as tk

    cfg    = load_config()
    dialog = tk.Toplevel(app)
    dialog.title("IGDB API Settings")
    dialog.configure(bg="#1a1a2e")
    dialog.transient(app)
    dialog.grab_set()
    dialog.resizable(False, False)

    tk.Label(
        dialog, text="IGDB API Credentials",
        bg="#1a1a2e", fg="#e0e0ff",
        font=("Segoe UI", 12, "bold"),
    ).pack(padx=24, pady=(18, 4))

    tk.Label(
        dialog,
        text=(
            "Get your credentials from the Twitch Developer Console:\n"
            "dev.twitch.tv/console/apps  →  Register Your Application"
        ),
        bg="#1a1a2e", fg="#7777aa",
        font=("Segoe UI", 8),
        justify="center",
    ).pack(padx=24, pady=(0, 14))

    form = tk.Frame(dialog, bg="#1a1a2e")
    form.pack(padx=24, pady=4)

    def _lbl(row, text):
        tk.Label(
            form, text=text, bg="#1a1a2e", fg="#aaaacc",
            font=("Segoe UI", 9), width=14, anchor="e",
        ).grid(row=row, column=0, pady=5, sticky="e")

    def _entry(row, var, show=None):
        kw = dict(
            textvariable=var, bg="#16213e", fg="#e0e0ff",
            insertbackground="#e0e0ff", font=("Segoe UI", 9),
            relief="flat", width=38,
        )
        if show:
            kw["show"] = show
        tk.Entry(form, **kw).grid(row=row, column=1, padx=(8, 0), pady=5)

    client_id_var = tk.StringVar(value=cfg.get("client_id", ""))
    secret_var    = tk.StringVar(value=cfg.get("client_secret", ""))

    _lbl(0, "Client ID:")
    _entry(0, client_id_var)
    _lbl(1, "Client Secret:")
    _entry(1, secret_var, show="*")

    status_lbl = tk.Label(
        dialog, text="", bg="#1a1a2e", fg="#ff7777", font=("Segoe UI", 8)
    )
    status_lbl.pack(padx=24)

    def _save():
        cid    = client_id_var.get().strip()
        secret = secret_var.get().strip()
        if not cid or not secret:
            status_lbl.configure(text="Both fields are required.")
            return
        new_cfg = dict(cfg)
        new_cfg["client_id"]     = cid
        new_cfg["client_secret"] = secret
        # Clear cached token so it is refreshed with the new credentials
        new_cfg.pop("access_token",     None)
        new_cfg.pop("token_expires_at", None)
        save_config(new_cfg)
        dialog.destroy()
        if on_save:
            on_save()

    def _cancel():
        dialog.destroy()

    btns = tk.Frame(dialog, bg="#1a1a2e")
    btns.pack(fill="x", padx=24, pady=(10, 18))
    tk.Button(
        btns, text="Cancel", bg="#2c2c4a", fg="#aaaacc",
        font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
        cursor="hand2", command=_cancel,
    ).pack(side="right")
    tk.Button(
        btns, text="Save", bg="#0f3460", fg="#e0e0ff",
        font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=4,
        cursor="hand2", command=_save,
    ).pack(side="right", padx=(0, 6))

    dialog.bind("<Return>", lambda _e: _save())
    dialog.bind("<Escape>", lambda _e: _cancel())

    dialog.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width()  - dialog.winfo_width())  // 2
    y = app.winfo_rooty() + (app.winfo_height() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
