"""ScraperEngine — HTTP-based Yahoo Finance equity screener client.

Uses the internal Yahoo Finance screener API (query1.finance.yahoo.com).
No browser required. Auth flow: GET finance.yahoo.com → cookies,
GET /v1/test/getcrumb → crumb token, POST screener with crumb + cookie.
"""

import requests

# ---------------------------------------------------------------------------
# Region name → Yahoo Finance region code mapping
# ---------------------------------------------------------------------------

_REGION_CODES: dict[str, str] = {
    "argentina": "ar",
    "australia": "au",
    "austria": "at",
    "belgium": "be",
    "brazil": "br",
    "canada": "ca",
    "chile": "cl",
    "china": "cn",
    "colombia": "co",
    "czech republic": "cz",
    "denmark": "dk",
    "egypt": "eg",
    "estonia": "ee",
    "finland": "fi",
    "france": "fr",
    "germany": "de",
    "greece": "gr",
    "hong kong": "hk",
    "hungary": "hu",
    "iceland": "is",
    "india": "in",
    "indonesia": "id",
    "ireland": "ie",
    "israel": "il",
    "italy": "it",
    "japan": "jp",
    "jordan": "jo",
    "kenya": "ke",
    "kuwait": "kw",
    "latvia": "lv",
    "lithuania": "lt",
    "luxembourg": "lu",
    "malaysia": "my",
    "mexico": "mx",
    "morocco": "ma",
    "netherlands": "nl",
    "new zealand": "nz",
    "nigeria": "ng",
    "norway": "no",
    "pakistan": "pk",
    "peru": "pe",
    "philippines": "ph",
    "poland": "pl",
    "portugal": "pt",
    "qatar": "qa",
    "romania": "ro",
    "russia": "ru",
    "saudi arabia": "sa",
    "singapore": "sg",
    "south africa": "za",
    "south korea": "kr",
    "spain": "es",
    "sri lanka": "lk",
    "sweden": "se",
    "switzerland": "ch",
    "taiwan": "tw",
    "thailand": "th",
    "turkey": "tr",
    "united arab emirates": "ae",
    "united kingdom": "gb",
    "united states": "us",
    "venezuela": "ve",
    "vietnam": "vn",
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Used for all requests (API calls need Accept: application/json)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://finance.yahoo.com/",
    "Origin": "https://finance.yahoo.com",
}

# Used only for the initial finance.yahoo.com GET — must look like a browser
# to get the A1/A3 session cookies set correctly.
_BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"

_CONSENT_URL = "https://finance.yahoo.com"
_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
_SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener"
_PAGE_SIZE = 250


class ScraperEngine:
    """Fetches Yahoo Finance equity screener data via HTTP — no browser needed."""

    def __init__(self, session: requests.Session) -> None:
        self._session = session
        self._crumb: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self, region: str) -> list[dict[str, str]]:
        """Authenticate (if needed) and return all equity rows for a region."""
        if not self._crumb:
            self._authenticate()
        region_code = self._to_region_code(region)
        return self._fetch_all_pages(region_code)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """Obtain session cookies and crumb from Yahoo Finance.

        The initial GET must use a browser-like Accept header so Yahoo sets
        the A1/A3 session cookies correctly. Without it, getcrumb returns 401.
        """
        self._session.get(
            _CONSENT_URL,
            headers={"Accept": _BROWSER_ACCEPT},
            timeout=15,
        )
        resp = self._session.get(_CRUMB_URL, timeout=10)
        resp.raise_for_status()
        crumb = resp.text.strip()
        if not crumb or crumb.startswith("{"):
            raise RuntimeError(
                f"Failed to obtain Yahoo Finance crumb token. Response: {crumb[:100]}"
            )
        self._crumb = crumb

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _fetch_all_pages(self, region_code: str) -> list[dict[str, str]]:
        all_rows: list[dict[str, str]] = []
        offset = 0
        while True:
            batch = self._fetch_page(region_code, offset)
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return all_rows

    def _fetch_page(self, region_code: str, offset: int) -> list[dict[str, str]]:
        payload = {
            "size": _PAGE_SIZE,
            "offset": offset,
            "sortField": "intradaymarketcap",
            "sortType": "DESC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "and",
                "operands": [
                    {"operator": "eq", "operands": ["region", region_code]}
                ],
            },
            "userId": "",
            "userIdType": "guid",
        }
        params = {
            "crumb": self._crumb,
            "lang": "en-US",
            "region": "US",
            "formatted": "false",
            "corsDomain": "finance.yahoo.com",
        }
        resp = self._session.post(
            _SCREENER_URL, params=params, json=payload, timeout=30
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_response(self, data: dict) -> list[dict[str, str]]:
        """Extract symbol, name, price, and change_pct from API response."""
        try:
            quotes = data["finance"]["result"][0]["quotes"]
        except (KeyError, IndexError, TypeError):
            return []

        results: list[dict[str, str]] = []
        for q in quotes:
            symbol: str = q.get("symbol", "")
            name: str = q.get("longName") or q.get("shortName") or ""
            price = q.get("regularMarketPrice")
            change_pct = q.get("regularMarketChangePercent")

            if not symbol or price is None:
                continue

            results.append({
                "symbol": symbol,
                "name": name,
                "price": str(price),
                "change_pct": str(round(change_pct, 4)) if change_pct is not None else "",
            })
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_region_code(region: str) -> str:
        """Convert a region display name to a Yahoo Finance region code."""
        code = _REGION_CODES.get(region.lower().strip())
        if code:
            return code
        # Fallback: use first two chars as ISO-like code
        normalized = region.strip().lower().replace(" ", "")
        if len(normalized) >= 2:
            return normalized[:2]
        raise ValueError(
            f"Unknown region '{region}'. "
            f"Known regions: {sorted(_REGION_CODES.keys())}"
        )
