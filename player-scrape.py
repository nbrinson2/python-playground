import logging
import os
import re
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

    Always loads the page from ``url`` via GET (no local snapshot files).
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
    return round(
        k_data / bb_data - era_data - whip_data - h_data - hr_data + w_data - l_data + (ip_data/g_data) + qs_data
    ) + 100


def get_last_15_data(player_names, session=None, player_slugs=None):
    """Fetch last-15 pitcher stats; match rows by URL slug when ``player_slugs`` is set.

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
        except (ValueError, IndexError) as exc:
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

    # HTML script for sortable table
    sortable_table_script = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            background-color: black;
            color: white;
        }
        
        table th {
            cursor: pointer;
        }
        
        table td, table th {
            padding: 10px;
        }

        table tr:nth-child(even) {
            background-color: rgba(114,111,112,0.5);
            font-weight: 600;
        }

        /* Top 10 team AVG (best offenses): red tint. Bottom 10: green tint. */
        table td.batting-avg-top {
            background-color: rgba(200, 50, 55, 0.55) !important;
        }

        table td.batting-avg-bottom {
            background-color: rgba(45, 160, 85, 0.55) !important;
        }
    </style>
</head>
<body>
    """ + html_table + """
<script>
function makeTableSortable(table) {
    var headers = table.querySelectorAll('th');

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

            var rows = Array.from(table.querySelectorAll('tr'));
            var headerRow = rows.shift();

            rows.sort(function(rowA, rowB) {
                var rawA = rowA.children[index] ? rowA.children[index].textContent : '';
                var rawB = rowB.children[index] ? rowB.children[index].textContent : '';
                return compareSortValues(trimCell(rawA), trimCell(rawB), direction);
            });
            
            // Clear the table
            while (table.firstChild) {
                table.firstChild.remove();
            }
            
            // Add the sorted rows back to the table
            table.appendChild(headerRow);
            rows.forEach(function(row) {
                table.appendChild(row);
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

    # Write the HTML to a file
    with open("probable-pitchers.html", "w", encoding="utf-8") as f:
        f.write(sortable_table_script)
    LOG.info("Wrote probable-pitchers.html")
