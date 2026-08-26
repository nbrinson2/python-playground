import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOG = logging.getLogger("player_scrape")


def configure_player_scrape_logging(log_path=None, *, level=logging.INFO):
    """Write player-scrape diagnostics to a log file (UTF-8).

    Default path: ``player-scrape.log`` next to this script. Safe to call once;
    skips if the logger already has handlers.
    """
    log = logging.getLogger("player_scrape")
    if log.handlers:
        return
    log.setLevel(level)
    path = log_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "player-scrape.log",
    )
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(fh)
    log.propagate = False
    log.info("Logging to %s", path)


def _fp_probable_pitchers_headers():
    """Headers closer to a real browser (helps some servers return the full HTML grid)."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }


def _find_probable_pitchers_table(soup):
    """Locate the main grid (``.game-tables``); fallback to the condensed stats table."""
    table = soup.select_one(".game-tables table.table.table-condensed")
    if table is None:
        table = soup.select_one("table.table.table-condensed")
    if table is None:
        table = soup.find("table")
    return table


def _mlb_com_stats_headers():
    """Headers closer to a browser (MLB.com stats app returns a shell without them)."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }


def _mlb_team_stats_batting_avg_column_index(thead_row):
    """Return 0-based header index of the AVG column on mlb.com/stats/team tables."""
    headers = thead_row.find_all("th", recursive=False)
    for i, th in enumerate(headers):
        label = th.get_text(strip=True).upper()
        if "AVG" in label and "OBP" not in label and "SLG" not in label and "OPS" not in label:
            return i
    return 14


def _rank_and_team_name_from_stats_th(th):
    """Extract display rank and team name from a stats table row's leading ``th``."""
    if th is None:
        return None, ""
    raw = th.get_text(strip=True).replace("\u200c", "").strip()
    rank = None
    m = re.match(r"^(\d+)", raw)
    if m:
        rank = int(m.group(1))
    a = th.find("a")
    team = ""
    if a:
        for span in a.find_all("span"):
            name = span.get_text(strip=True).replace("\u200c", "").strip()
            if len(name) >= 2:
                team = name
                break
        if not team:
            team = a.get_text(strip=True).replace("\u200c", "").strip()
    if not team:
        team = re.sub(r"^\d+", "", raw).strip()
    return rank, team


def scrape_mlb_team_batting_averages(
    url="https://www.mlb.com/stats/team/batting-average?timeframe=-6",
    *,
    session=None,
):
    """Fetch and parse MLB.com team batting-average HTML (``#stats-app-root`` table).

    Default ``url`` uses ``timeframe=-6``, the MLB stats site's preset for team AVG over
    the last seven days. Always loads from ``url`` via GET (no local snapshot files).
    """
    sess = session or requests.Session()
    response = sess.get(url, headers=_mlb_com_stats_headers())
    try:
        response.raise_for_status()
    except requests.RequestException:
        LOG.exception("MLB team stats request failed: HTTP %s", response.status_code)
        raise
    text = response.text
    LOG.info(
        "Fetched MLB team stats: HTTP %s, %d bytes",
        response.status_code,
        len(text),
    )

    soup = BeautifulSoup(text, "html.parser")
    root = soup.find(id="stats-app-root")
    if root is None:
        raise ValueError(
            "Could not find #stats-app-root (not an MLB stats page or HTML changed)."
        )
    thead = root.find("thead")
    tbody = root.find("tbody")
    if thead is None or tbody is None:
        raise ValueError("Stats table missing thead or tbody under #stats-app-root.")
    header_row = thead.find("tr")
    if header_row is None:
        raise ValueError("Stats table thead has no header row.")
    avg_col = _mlb_team_stats_batting_avg_column_index(header_row)

    records = []
    for tr in tbody.find_all("tr"):
        th = tr.find("th", recursive=False)
        tds = tr.find_all("td", recursive=False)
        if not th or not tds:
            continue
        td_index = avg_col - 1
        if td_index < 0 or td_index >= len(tds):
            LOG.warning(
                "Skipping row: AVG column index %s out of range (%d tds)",
                td_index,
                len(tds),
            )
            continue
        rank, team = _rank_and_team_name_from_stats_th(th)
        avg_s = tds[td_index].get_text(strip=True)
        try:
            avg_f = float(avg_s) if avg_s else float("nan")
        except ValueError:
            avg_f = float("nan")
        league = tds[0].get_text(strip=True) if tds else ""
        link = th.find("a")
        team_path = link.get("href") if link else ""
        records.append(
            {
                "Rank": rank,
                "Team": team,
                "League": league,
                "AVG": avg_f,
                "TeamPath": team_path,
            }
        )

    if not records:
        raise ValueError("No team rows parsed from stats tbody.")
    LOG.info("Parsed %d MLB team batting-average rows", len(records))
    return pd.DataFrame(records)


# FantasyPros / broadcast-style opponent tokens → ``TeamPath`` slug (see MLB stats ``TeamPath``).
_MLB_OPPONENT_ABBREV_TO_SLUG = {
    "LAD": "dodgers",
    "HOU": "astros",
    "PIT": "pirates",
    "WSH": "nationals",
    "WAS": "nationals",
    "NYM": "mets",
    "KC": "royals",
    "KCR": "royals",
    "OAK": "athletics",
    "ATH": "athletics",
    "BAL": "orioles",
    "PHI": "phillies",
    "ATL": "braves",
    "DET": "tigers",
    "MIL": "brewers",
    "SF": "giants",
    "SFG": "giants",
    "MIA": "marlins",
    "FLA": "marlins",
    "BOS": "redsox",
    "COL": "rockies",
    "SD": "padres",
    "SDP": "padres",
    "TB": "rays",
    "TBR": "rays",
    "CHC": "cubs",
    "MIN": "twins",
    "CIN": "reds",
    "NYY": "yankees",
    "CLE": "guardians",
    "TEX": "rangers",
    "CWS": "whitesox",
    "CHW": "whitesox",
    "STL": "cardinals",
    "ARI": "dbacks",
    "AZ": "dbacks",
    "TOR": "bluejays",
    "LAA": "angels",
    "ANA": "angels",
    "SEA": "mariners",
}


def _team_name_from_opponent_cell(text, batting_df):
    """Map a probable-pitchers opponent cell string to an MLB ``Team`` from ``batting_df``."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    s_raw = str(text).strip()
    if not s_raw:
        return None
    s_lower = s_raw.lower()

    slug_by_path = {}
    for _, row in batting_df.iterrows():
        p = (row.get("TeamPath") or "").strip().strip("/").lower()
        if p:
            slug_by_path[p] = row["Team"]

    for path, team in slug_by_path.items():
        if path in s_lower:
            return team

    for m in re.finditer(r"\b([A-Za-z]{2,3})\b", s_raw):
        slug = _MLB_OPPONENT_ABBREV_TO_SLUG.get(m.group(1).upper())
        if slug and slug in slug_by_path:
            return slug_by_path[slug]

    for _, row in batting_df.iterrows():
        team = str(row["Team"])
        if team.lower() in s_lower:
            return team
        nick = team.split()[-1]
        if len(nick) > 2 and nick.lower() in s_lower:
            return team
    return None


def add_team_batting_highlights_to_pitchers_html(html_table, df, batting_df):
    """Add ``td`` classes for opponent teams in the top / bottom 10 by team AVG (``batting_df``)."""
    top10 = set(batting_df.nlargest(10, "AVG")["Team"])
    bottom10 = set(batting_df.nsmallest(10, "AVG")["Team"])

    skip_cols = {"Rank", "Last 15", "Player"}
    col_names = list(df.columns)
    highlight_indices = {
        i for i, name in enumerate(col_names) if str(name) not in skip_cols
    }

    soup = BeautifulSoup(html_table, "html.parser")
    table = soup.find("table")
    if table is None:
        return html_table

    for tr in table.find_all("tr"):
        if tr.find_parent("thead"):
            continue
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        # pandas ``to_html()`` defaults to ``index=True``: first body cell is ``<th>`` (row index).
        offset = 1 if cells[0].name == "th" else 0
        for j, cell in enumerate(cells):
            if j < offset:
                continue
            df_col = j - offset
            if df_col not in highlight_indices:
                continue
            if cell.name != "td":
                continue
            team = _team_name_from_opponent_cell(cell.get_text(), batting_df)
            if team is None:
                continue
            cls = None
            if team in top10:
                cls = "batting-avg-top"
            elif team in bottom10:
                cls = "batting-avg-bottom"
            if cls:
                cell["class"] = cell.get("class", []) + [cls]

    return str(soup)


def click_sign_in_link(
    url="https://www.fantasypros.com/mlb/probable-pitchers.php",
    *,
    headless=True,
    timeout=20,
    keep_browser_open=False,
):
    """Open FantasyPros in a browser and click the Sign in link in the registration form.

    The overlay is rendered client-side; this uses Selenium (not requests/BeautifulSoup).

    Returns the sign-in page URL after navigation, or the WebDriver if keep_browser_open is True.
    Requires Chrome/Chromium installed (Selenium 4+ manages the driver).
    """
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    retained = False
    try:
        LOG.info("Opening %s for sign-in link (headless=%s)", url, headless)
        driver.get(url)
        wait = WebDriverWait(driver, timeout)
        sign_in = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".sign-up-form__already-have-account a")
            )
        )
        sign_in.click()
        wait.until(EC.url_contains("signin"))
        LOG.info("Navigated to sign-in flow")
        if keep_browser_open:
            retained = True
            return driver
        return driver.current_url
    except Exception:
        LOG.exception("click_sign_in_link failed")
        raise
    finally:
        if not retained:
            driver.quit()


def _fantasypros_signin_url_path(url):
    """Return True if URL path is the accounts sign-in page."""
    path = urlparse(url).path.rstrip("/")
    return path.endswith("accounts/signin")


def _dismiss_onetrust_cookies(driver, short_wait=5):
    try:
        btn = WebDriverWait(driver, short_wait).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
    except TimeoutException:
        pass


def sign_in_fantasypros(
    email=None,
    password=None,
    *,
    signin_url="https://www.fantasypros.com/accounts/signin/?e=&next=https://www.fantasypros.com/mlb/probable-pitchers.php",
    headless=True,
    timeout=40,
    keep_browser_open=False,
    driver=None,
):
    """Sign in on FantasyPros (email + password on the launchpad form).

    Credentials are not read from source code: pass ``email`` / ``password``, or set
    environment variables ``FANTASYPROS_EMAIL`` and ``FANTASYPROS_PASSWORD``.

    Form fields (from the live page): ``#username``, ``#password``,
    ``button.launchpad__form-submit-button``.

    On success, the browser leaves ``/accounts/signin``. If reCAPTCHA or bot checks
    block automation, use ``headless=False`` and complete any challenge manually.

    Returns the ``WebDriver`` when ``keep_browser_open`` is True; otherwise the
    final URL string and the browser is closed (unless ``driver`` was passed in).
    """
    email = email or os.environ.get("FANTASYPROS_EMAIL")
    password = password or os.environ.get("FANTASYPROS_PASSWORD")
    if not email or not password:
        raise ValueError(
            "Provide email and password, or set FANTASYPROS_EMAIL and FANTASYPROS_PASSWORD"
        )

    owns_driver = driver is None
    if owns_driver:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

    retained = False
    try:
        LOG.info(
            "FantasyPros sign-in: headless=%s timeout=%s (credentials from args or env)",
            headless,
            timeout,
        )
        driver.get(signin_url)
        wait = WebDriverWait(driver, timeout)
        _dismiss_onetrust_cookies(driver)

        user_el = wait.until(EC.visibility_of_element_located((By.ID, "username")))
        pwd_el = driver.find_element(By.ID, "password")
        user_el.clear()
        user_el.send_keys(email)
        pwd_el.clear()
        pwd_el.send_keys(password)

        submit = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.launchpad__form-submit-button")
            )
        )
        submit.click()

        try:
            wait.until(lambda d: not _fantasypros_signin_url_path(d.current_url))
        except TimeoutException as exc:
            LOG.error(
                "Sign-in did not leave /accounts/signin (captcha, bad password, or bot check)"
            )
            raise TimeoutException(
                "Still on sign-in after submit — wrong credentials, captcha/bot check, "
                "or try headless=False."
            ) from exc

        LOG.info("Sign-in succeeded; session left sign-in page")
        if keep_browser_open:
            retained = True
            return driver
        return driver.current_url
    finally:
        if owns_driver and not retained:
            driver.quit()


def _driver_to_requests_session(driver):
    """Copy Selenium cookie jar into a ``requests.Session`` for the same origin."""
    session = requests.Session()
    for c in driver.get_cookies():
        session.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain"),
            path=c.get("path", "/"),
        )
    return session


def fantasypros_requests_session(
    email=None,
    password=None,
    *,
    signin_url="https://www.fantasypros.com/accounts/signin/?e=&next=https://www.fantasypros.com/mlb/probable-pitchers.php",
    headless=True,
    timeout=40,
):
    """Sign in with Selenium, then return a ``requests.Session`` carrying site cookies."""
    LOG.info("Building authenticated requests session via Selenium sign-in")
    driver = sign_in_fantasypros(
        email,
        password,
        signin_url=signin_url,
        headless=headless,
        timeout=timeout,
        keep_browser_open=True,
    )
    try:
        n_cookies = len(driver.get_cookies())
        sess = _driver_to_requests_session(driver)
        LOG.info("Copied %d browser cookies into requests.Session", n_cookies)
        return sess
    finally:
        driver.quit()


def _canonical_mlb_player_slug_from_href(href):
    """Normalize ``/mlb/players/…`` or ``/mlb/stats/…`` slug for cross-page matching.

    Stats rows use links like ``/mlb/stats/mike-soroka.php`` while the grid uses
    ``/mlb/players/mike-soroka.php``; display text may say *Michael Soroka* vs *Mike Soroka*,
    but the slug matches. Trailing ``-p`` (pitcher) is stripped on both sides.
    """
    m = re.search(r"/mlb/(?:players|stats)/([^/.?#]+)\.php", href or "", re.I)
    if not m:
        return None
    s = m.group(1).lower()
    if s.endswith("-p") and len(s) > 2:
        s = s[:-2]
    return s


def _last_15_name_match_variants(player_name):
    """Substrings to try against the stats table name cell (first match wins)."""
    if not player_name or not str(player_name).strip():
        return [player_name]
    n = str(player_name).strip()
    out = [n]
    if n.endswith(" P"):
        out.append(n[:-2].rstrip())
    return out


def _last_15_find_row_cells(soup, canonical_slug, name_variants):
    """Return ``td`` cells for a stats row: prefer URL slug, else display-name substring."""
    if canonical_slug:
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) <= 15:
                continue
            link = cells[1].find("a", href=True)
            if not link:
                continue
            row_slug = _canonical_mlb_player_slug_from_href(link.get("href") or "")
            if row_slug == canonical_slug:
                return cells
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) <= 15:
            continue
        cell_text = cells[1].text
        if any(v and v in cell_text for v in name_variants):
            return cells
    return None


def _last_15_compute_from_cells(cells):
    """Apply the same formula as before to a matched stats row."""
    ip_data = float(cells[2].text)
    k_data = float(cells[3].text)
    w_data = float(cells[4].text)
    qs_data = float(cells[5].text)
    era_data = float(cells[7].text)
    h_data = float(cells[10].text)
    bb_data = float(cells[11].text)
    if bb_data == 0:
        bb_data = 1
    hr_data = float(cells[12].text)
    l_data = float(cells[15].text)
    g_data = float(cells[13].text)
    whip_data = float(cells[8].text)
    ip_per_g = (ip_data / g_data) if g_data else 0.0
    return round(
        k_data / bb_data - era_data - whip_data - h_data - hr_data + w_data - l_data + ip_per_g + qs_data
    ) + 100


def get_last_15_data(player_names, session=None, player_slugs=None):
    """Fetch pitcher stats for the source site's **last 15 days** range; match rows by URL slug when ``player_slugs`` is set.

    ``player_slugs`` must be the same length as ``player_names`` (use ``None`` entries to
    fall back to name substring matching for that row). Slugs should come from
    :func:`_canonical_mlb_player_slug_from_href` on each player's ``/mlb/players/…`` link.
    """
    if player_slugs is not None and len(player_slugs) != len(player_names):
        raise ValueError("player_slugs and player_names must have the same length")

    url = "https://www.fantasypros.com/mlb/stats/pitchers.php?range=15&page=ALL"
    h = _fp_probable_pitchers_headers()
    response = (
        session.get(url, headers=h) if session else requests.get(url, headers=h)
    )
    try:
        response.raise_for_status()
    except requests.RequestException:
        LOG.exception(
            "Last-15 stats request failed: HTTP %s", response.status_code
        )
        raise
    LOG.info(
        "Fetched last-15 pitcher stats: HTTP %s, %d bytes, %d players to match",
        response.status_code,
        len(response.content),
        len(player_names),
    )
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    missing = []
    for i, player_name in enumerate(player_names):
        canonical = None
        if player_slugs is not None:
            canonical = player_slugs[i]
        variants = _last_15_name_match_variants(player_name)
        cells = _last_15_find_row_cells(soup, canonical, variants)
        if cells is None:
            results.append('')
            missing.append(player_name)
            continue
        if canonical:
            LOG.debug("Last-15 matched %r by slug %r", player_name, canonical)
        else:
            hit = next((v for v in variants if v and v in cells[1].text), None)
            if hit and hit != variants[0]:
                LOG.debug(
                    "Last-15 matched lookup %r using name variant %r", player_name, hit
                )
        try:
            results.append(_last_15_compute_from_cells(cells))
        except (ValueError, IndexError, ZeroDivisionError) as exc:
            LOG.warning("Last-15 parse failed for %r: %s", player_name, exc)
            results.append('')
            missing.append(player_name)

    if missing:
        LOG.warning(
            "Last-15 table: no row for %d player(s), e.g. %s",
            len(missing),
            ", ".join(missing[:5]) + ("..." if len(missing) > 5 else ""),
        )
    return results


def _full_name_from_player_href(href):
    """Derive a display full name from a FantasyPros ``/mlb/players/{slug}.php`` href.

    Pitcher pages often use a trailing ``-p`` in the slug (e.g. ``edward-cabrera-p``) to
    disambiguate from hitters; the last-15 stats table uses ``Edward Cabrera`` without
    that suffix, so it is stripped before title-casing.
    """
    m = re.search(r"/mlb/players/([^/.?#]+)", href or "")
    if not m:
        return None
    slug = m.group(1)
    if slug.endswith("-p") and len(slug) > 2:
        slug = slug[:-2]
    return " ".join(part.capitalize() for part in slug.split("-"))


def collect_probable_pitcher_entries(table):
    """Return one entry per distinct pitcher on the page (order = first appearance in the table).

    Each entry is ``{"fpid": str, "name": str, "full_name": str, "slug": str|None}``.
    ``slug`` is the canonical URL slug for :func:`get_last_15_data` matching.
    Rows match on ``fpid``, so duplicate short names (e.g. two different Millers) stay distinct.

    Expects the classic FantasyPros grid (``table.table.table-condensed`` inside
    ``.game-tables``).
    """
    seen = set()
    entries = []
    for row in table.find_all("tr"):
        for td in row.find_all("td")[1:]:
            div = td.find("div", class_="player-cell")
            if not div:
                continue
            a = div.find("a", class_="player-name")
            if not a:
                continue
            fpid = a.get("data-fpid")
            if not fpid or fpid in seen:
                continue
            seen.add(fpid)
            href = a.get("href") or ""
            short = a.get_text(strip=True)
            full = _full_name_from_player_href(href)
            entries.append(
                {
                    "fpid": fpid,
                    "name": short,
                    "full_name": full or short,
                    "slug": _canonical_mlb_player_slug_from_href(href),
                }
            )
    return entries


def scrape_player_data(
    player_names=None,
    *,
    name_mapping=None,
    email=None,
    password=None,
    headless=True,
    sign_in_timeout=40,
    session=None,
    sign_in=None,
):
    """Fetch probable-pitchers table and related stats.

    If ``player_names`` is ``None`` (default), pitcher rows are built from everyone listed
    on the probable-pitchers page (unique by FantasyPros player id). Otherwise ``player_names``
    is an explicit list of short names; pass ``name_mapping`` to map them to full names for
    the last-15 stats table.

    When ``sign_in`` is true and credentials are set (arguments or ``FANTASYPROS_EMAIL`` /
    ``FANTASYPROS_PASSWORD``), signs in via Selenium first and reuses those cookies for
    ``requests`` (probable pitchers + last-15 stats). Pass ``session`` to reuse an
    existing authenticated session.

    If ``sign_in`` is ``None``, sign-in is used only when both email and password resolve
    to non-empty values (args or env). Set ``sign_in=False`` to force an anonymous fetch
    even if env vars are set.
    """
    resolved_email = email if email is not None else os.environ.get("FANTASYPROS_EMAIL")
    resolved_password = (
        password if password is not None else os.environ.get("FANTASYPROS_PASSWORD")
    )
    has_creds = bool(resolved_email and resolved_password)

    if sign_in is None:
        use_sign_in = has_creds
    else:
        use_sign_in = sign_in
        if use_sign_in and not has_creds:
            LOG.error("sign_in=True but no email/password in args or env")
            raise ValueError(
                "sign_in=True requires email and password (arguments or FANTASYPROS_EMAIL / FANTASYPROS_PASSWORD)"
            )

    LOG.info(
        "Starting scrape: pitchers=%s, authenticated_requests=%s",
        "auto-discover" if player_names is None else len(player_names),
        use_sign_in,
    )

    if session is None and use_sign_in:
        session = fantasypros_requests_session(
            resolved_email,
            resolved_password,
            headless=headless,
            timeout=sign_in_timeout,
        )

    url = "https://www.fantasypros.com/mlb/probable-pitchers.php"
    h = _fp_probable_pitchers_headers()
    response = session.get(url, headers=h) if session else requests.get(url, headers=h)
    try:
        response.raise_for_status()
    except requests.RequestException:
        LOG.exception(
            "Probable-pitchers request failed: HTTP %s", response.status_code
        )
        raise
    LOG.info(
        "Fetched probable pitchers: HTTP %s, %d bytes",
        response.status_code,
        len(response.content),
    )
    soup = BeautifulSoup(response.text, "html.parser")

    # Get table headers
    table = _find_probable_pitchers_table(soup)
    if table is None:
        LOG.error("No probable-pitchers table in response (missing .game-tables grid)")
        raise ValueError("Could not find probable-pitchers table in HTML.")
    headers = [header.text for header in table.find_all("th")]
    headers[0] = "Player"

    if player_names is None:
        entries = collect_probable_pitcher_entries(table)
        if not entries:
            LOG.error("collect_probable_pitcher_entries returned no pitchers")
            raise ValueError(
                "No pitchers found on probable-pitchers page (empty table or HTML changed)."
            )
        if len(entries) < 45:
            LOG.warning(
                "Only %d distinct pitchers parsed — response may be a partial shell "
                "(full grid is `.game-tables`); try sign-in or browser fetch for full list",
                len(entries),
            )
        else:
            LOG.info("Parsed %d distinct pitchers from probable-pitchers grid", len(entries))
        fpid_to_index = {e["fpid"]: i for i, e in enumerate(entries)}
        player_names = [e["name"] for e in entries]
        last_15_lookup = [e["full_name"] for e in entries]
        last_15_slugs = [e["slug"] for e in entries]
        use_fpid = True
    else:
        fpid_to_index = None
        use_fpid = False
        mapping = name_mapping if name_mapping is not None else {}
        last_15_lookup = [mapping.get(n, n) for n in player_names]
        last_15_slugs = None
        LOG.info("Using %d explicit player names for grid + last-15", len(player_names))

    # Prepare data frame
    data = {header: [""]*len(player_names) for header in headers}
    data[headers[0]] = player_names  # Set player names as first column

    # Prepare player ranks list
    player_ranks = [""]*len(player_names)

    # Loop over table rows
    for row in table.find_all('tr'):
        cells = row.find_all('td')

        # Check if cells is not empty
        if cells:
            # Get spans from other cells
            for i in range(1, len(cells)):
                player_cell_div = cells[i].find(
                    'div', {'class': 'player-cell'})
                if player_cell_div:
                    if use_fpid:
                        a = player_cell_div.find("a", class_="player-name")
                        fpid = a.get("data-fpid") if a else None
                        if not fpid or fpid not in fpid_to_index:
                            continue
                        player_index = fpid_to_index[fpid]
                    else:
                        matched = False
                        for player_name in player_names:
                            if player_name in player_cell_div.text:
                                player_index = player_names.index(player_name)
                                matched = True
                                break
                        if not matched:
                            continue

                    # Extract player rank from the span title
                    span_title = player_cell_div.find(
                        'span', {'title': True})
                    if span_title:
                        rank = span_title['title'].split(': ')[1]
                        player_ranks[player_index] = rank

                    # Extract player opponent from span
                    span_opponent = player_cell_div.find(
                        'span', {'data-woba': True})
                    data[headers[i]][player_index] = span_opponent.text

        else:
            continue

    # Call get_last_15_data() for the list of players
    last_15 = get_last_15_data(
        last_15_lookup,
        session=session,
        player_slugs=last_15_slugs,
    )

    # Convert dictionary to data frame
    df = pd.DataFrame(data)

    # Insert 'Last 15' and player ranks as the first columns
    df.insert(0, 'Last 15', last_15)
    df.insert(0, 'Rank', player_ranks)

    LOG.info(
        "Scrape finished: %d rows, %d columns", len(df.index), len(df.columns)
    )
    return df


if __name__ == "__main__":
    configure_player_scrape_logging()
    try:
        # Scrape data; credentials from FANTASYPROS_EMAIL / FANTASYPROS_PASSWORD if set.
        df = scrape_player_data()
        batting_df = scrape_mlb_team_batting_averages()
    except Exception:
        LOG.exception("Player scrape run failed")
        raise

    print(df)

    # Convert the DataFrame to HTML; tint matchup cells by opponent team MLB AVG tier.
    html_table = df.to_html(index=False)
    html_table = add_team_batting_highlights_to_pitchers_html(
        html_table, df, batting_df
    )

    now_utc = datetime.now(timezone.utc)
    generated_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    generated_at = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    n_pitchers = len(df.index)

    page_title = "MLB Probable Pitchers — Today's Starting Pitchers & Matchups"
    page_description = (
        "MLB probable pitchers for today's games: sortable starting pitcher list with "
        "last-15-days pitching stats and opponent batting average matchup shading. "
        f"Updated {generated_at}."
    )
    # Optional absolute URL for canonical / Open Graph (e.g. https://yoursite.example).
    site_url = (os.environ.get("PROBABLE_PITCHERS_SITE_URL") or "").rstrip("/")
    canonical_link = (
        f'\n    <link rel="canonical" href="{site_url}/">' if site_url else ""
    )
    og_url_meta = (
        f'\n    <meta property="og:url" content="{site_url}/">' if site_url else ""
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": page_title,
        "description": page_description,
        "dateModified": generated_iso,
        "about": {
            "@type": "Thing",
            "name": "MLB probable pitchers",
        },
        "keywords": [
            "MLB probable pitchers",
            "probable pitchers",
            "MLB starting pitchers",
            "today's pitchers",
            "pitcher matchups",
        ],
    }
    if site_url:
        json_ld["url"] = f"{site_url}/"
    json_ld_script = json.dumps(json_ld, ensure_ascii=True)

    page_head = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{page_title}</title>
    <meta name="description" content="{page_description}">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="keywords" content="MLB probable pitchers, probable pitchers, MLB starting pitchers, today's pitchers, pitcher matchups, fantasy baseball">
    <meta name="author" content="player-scrape.py">
    <meta name="updated-time" content="{generated_iso}">{canonical_link}
    <meta property="og:type" content="website">
    <meta property="og:title" content="{page_title}">
    <meta property="og:description" content="{page_description}">
    <meta property="og:site_name" content="MLB Probable Pitchers">{og_url_meta}
    <meta property="og:locale" content="en_US">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{page_title}">
    <meta name="twitter:description" content="{page_description}">
    <script type="application/ld+json">{json_ld_script}</script>
    <style>
        :root {{
            --bg: #0d0d0f;
            --surface: #16161a;
            --border: #2a2a30;
            --text: #e8e6e3;
            --muted: #9a9691;
            --accent: #c4a35a;
            --legend-top: rgba(200, 50, 55, 0.65);
            --legend-bottom: rgba(45, 160, 85, 0.65);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 1.25rem 1rem 2.5rem;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
        }}
        .shell {{
            max-width: 120rem;
            margin: 0 auto;
        }}
        header.page-header {{
            margin-bottom: 1.25rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        header.page-header h1 {{
            margin: 0 0 0.35rem;
            font-size: clamp(1.35rem, 2.5vw, 1.75rem);
            font-weight: 650;
            letter-spacing: -0.02em;
        }}
        header.page-header .tagline {{
            margin: 0;
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .meta-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem 1.25rem;
            align-items: baseline;
            margin-bottom: 1.25rem;
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .meta-bar strong {{ color: var(--text); font-weight: 600; }}
        .meta-bar time {{ color: var(--accent); }}
        section.legend {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem 1.1rem;
            margin-bottom: 1.25rem;
        }}
        section.legend h2 {{
            margin: 0 0 0.65rem;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            font-weight: 600;
        }}
        .legend-grid {{
            display: grid;
            gap: 0.65rem 1.5rem;
        }}
        @media (min-width: 640px) {{
            .legend-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
        .legend-item {{
            display: flex;
            gap: 0.6rem;
            align-items: flex-start;
            font-size: 0.88rem;
        }}
        .swatch {{
            flex-shrink: 0;
            width: 1.1rem;
            height: 1.1rem;
            border-radius: 4px;
            margin-top: 0.2rem;
            border: 1px solid rgba(255,255,255,0.12);
        }}
        .swatch.top {{ background: var(--legend-top); }}
        .swatch.bottom {{ background: var(--legend-bottom); }}
        .swatch.neutral {{ background: rgba(114,111,112,0.45); }}
        .table-wrap {{
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--surface);
        }}
        .table-wrap table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}
        .table-wrap table th {{
            cursor: pointer;
            user-select: none;
            text-align: left;
            padding: 0.65rem 0.75rem;
            background: #1e1e24;
            color: #c8c4be;
            font-weight: 600;
            white-space: nowrap;
            border-bottom: 1px solid var(--border);
        }}
        .table-wrap table th:hover {{ color: var(--text); background: #25252c; }}
        .table-wrap table td {{
            padding: 0.55rem 0.75rem;
            border-bottom: 1px solid rgba(42,42,48,0.8);
            vertical-align: middle;
        }}
        .table-wrap table tbody tr:nth-child(even) td {{
            background: rgba(255,255,255,0.03);
        }}
        .table-wrap table tbody tr:hover td {{
            background: rgba(196, 163, 90, 0.08);
        }}
        table td.batting-avg-top {{
            background-color: rgba(200, 50, 55, 0.5) !important;
        }}
        table td.batting-avg-bottom {{
            background-color: rgba(45, 160, 85, 0.5) !important;
        }}
        footer.page-footer {{
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-size: 0.8rem;
            color: var(--muted);
        }}
        footer.page-footer p {{ margin: 0 0 0.65rem; }}
        footer.page-footer p:last-child {{ margin-bottom: 0; }}
        footer.page-footer a {{ color: var(--accent); }}
    </style>
</head>
<body>
<div class="shell">
    <header class="page-header">
        <h1>MLB Probable Pitchers</h1>
        <p class="tagline">Today's MLB starting pitchers in a sortable grid. <strong>Last 15</strong> uses the last <strong>15 days</strong> of pitching stats; red/green matchup shading ranks teams by batting average over the <strong>last 7 days</strong> (MLB.com).</p>
    </header>
    <div class="meta-bar">
        <span><strong>{n_pitchers}</strong> pitchers in this run</span>
        <span>Updated <time datetime="{generated_iso}">{generated_at}</time></span>
    </div>
    <section class="legend" aria-labelledby="legend-heading">
        <h2 id="legend-heading">Legend</h2>
        <div class="legend-grid">
            <div class="legend-item">
                <span class="swatch top" aria-hidden="true"></span>
                <span><strong>Red cell</strong> — Opponent is in the <strong>top 10</strong> by team batting average over the <strong>last 7 days</strong> (stronger recent offense; tougher matchup).</span>
            </div>
            <div class="legend-item">
                <span class="swatch bottom" aria-hidden="true"></span>
                <span><strong>Green cell</strong> — Opponent in the <strong>bottom 10</strong> by team AVG over the <strong>last 7 days</strong> (weaker recent offense).</span>
            </div>
            <div class="legend-item">
                <span class="swatch neutral" aria-hidden="true"></span>
                <span><strong>Striped rows &amp; hover</strong> — Easier scanning; click any <strong>column header</strong> to sort (toggle asc/desc). Empty values sort last.</span>
            </div>
            <div class="legend-item">
                <span class="swatch neutral" aria-hidden="true"></span>
                <span><strong>Rank</strong> — Pitcher rank from the source page tooltip. <strong>Last 15</strong> — Composite score from pitching stats over the <strong>last 15 days</strong>; <strong>higher is better</strong>.</span>
            </div>
        </div>
    </section>
    <div class="table-wrap" role="region" aria-label="Probable pitchers data table">
"""

    page_script = """
    </div>
    <footer class="page-footer">
        <p><strong>Disclaimer:</strong> This page is an independent, unofficial tool. It is not affiliated with, endorsed by, or sponsored by Major League Baseball (MLB), the MLBPA, or any MLB club.</p>
        <p>Sources: Public probable-pitchers listings; pitching stats over the <strong>last 15 days</strong>; MLB.com team batting average over the <strong>last 7 days</strong> (opponent tier coloring). Generated by <code>player-scrape.py</code>.</p>
    </footer>
</div>
<script>
function makeTableSortable(table) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var theadRow = table.tHead && table.tHead.rows[0];
    if (!theadRow) return;
    var headers = theadRow.querySelectorAll('th');

    function trimCell(text) {
        var t = (text || '').trim();
        if (t.toLowerCase() === 'nan') return '';
        return t;
    }

    /** Empty cells always sort to the bottom (asc or desc). */
    function compareSortValues(a, b, direction) {
        var emptyA = a === '';
        var emptyB = b === '';
        if (emptyA && emptyB) return 0;
        if (emptyA) return 1;
        if (emptyB) return -1;

        var na = parseFloat(a);
        var nb = parseFloat(b);
        var bothNumeric = !isNaN(na) && !isNaN(nb) && isFinite(na) && isFinite(nb);

        if (bothNumeric) {
            if (na < nb) return direction === 'asc' ? -1 : 1;
            if (na > nb) return direction === 'asc' ? 1 : -1;
            return 0;
        }
        if (a < b) return direction === 'asc' ? -1 : 1;
        if (a > b) return direction === 'asc' ? 1 : -1;
        return 0;
    }

    headers.forEach(function(header, index) {
        header.addEventListener('click', function() {
            var direction = header.getAttribute('data-sort') || 'asc';
            direction = (direction === 'asc') ? 'desc' : 'asc';

            var rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort(function(rowA, rowB) {
                var rawA = rowA.children[index] ? rowA.children[index].textContent : '';
                var rawB = rowB.children[index] ? rowB.children[index].textContent : '';
                return compareSortValues(trimCell(rawA), trimCell(rawB), direction);
            });

            while (tbody.firstChild) {
                tbody.removeChild(tbody.firstChild);
            }
            rows.forEach(function(row) {
                tbody.appendChild(row);
            });
            
            // Update the sort direction
            header.setAttribute('data-sort', direction);
        });
    });
}

// Make all tables sortable when the page loads
window.addEventListener('DOMContentLoaded', function() {
    var tables = document.querySelectorAll('table');
    tables.forEach(makeTableSortable);
});
</script>
</body>
</html>
"""

    sortable_table_script = page_head + html_table + page_script

    # Write the HTML to a file
    with open("probable-pitchers.html", "w", encoding="utf-8") as f:
        f.write(sortable_table_script)
    LOG.info("Wrote probable-pitchers.html")
