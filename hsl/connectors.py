"""Connectors to market and reference data, behind an egress allowlist.

Every connector produces bytes in the same CSV shape (timestamp, price)
and hands them to `ingest.quarantine`, so fetched data is treated exactly
like an upload: no connector can bypass the schema, formula, identifier
and classification checks. Credentials come from the environment only
(HSL_KEY_<SOURCE>), are never written to a file or a ledger entry, and
the ledger records the source, host, symbol, byte count and sha256 of what
came back. Outbound calls are HTTPS only, to hosts on the allowlist, with
a timeout and a response size cap, and redirects to another host are
refused (Security Engineering chapter 21).

Sources:
  bloomberg   Desktop API or B-PIPE through the blpapi package; requires a
              licensed session on the host. Data is `licensed`: rows stay
              in the run directory and never enter an evidence pack.
  lseg        LSEG Data Library (refinitiv.data); licensed, same rule.
  alphavantage REST, API key, public equity data.
  fred        Federal Reserve Economic Data REST, API key.
  ecb         ECB Data Portal, public, no key.
  boe         Bank of England Interactive Database, public, no key.
  replay      a local CSV fixture; the offline path used in tests and demos.

Only `replay` runs in the sandbox; the others are exercised only when a
host is allowlisted and a credential or licensed session is present.
"""

import datetime
import io
import json
import os
import urllib.parse
import urllib.request

from .security import egress_allowed

TIMEOUT_S = 20
MAX_BYTES = 20 * 1024 * 1024


class ConnectorError(Exception):
    pass


def _https_get(url, allowlist, headers=None):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https":
        raise ConnectorError("only https is permitted")
    if not egress_allowed(u.hostname, allowlist):
        raise ConnectorError(f"host {u.hostname} is not on the egress allowlist")

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            if urllib.parse.urlparse(newurl).hostname != u.hostname:
                raise ConnectorError("redirect to another host refused")
            return super().redirect_request(req, fp, code, msg, hdrs, newurl)

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=dict({"User-Agent": "HSL/3.3 (regulatory sandbox)"}, **(headers or {})))
    with opener.open(req, timeout=TIMEOUT_S) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ConnectorError("response exceeds the size cap")
    return data


def _csv_bytes(pairs):
    buf = io.StringIO()
    buf.write("timestamp,price\n")
    for t, p in pairs:
        buf.write(f"{t},{p}\n")
    return buf.getvalue().encode()


class Connector:
    name = "base"
    host = ""
    classification = "public"
    requires_key = False
    licensed = False

    def key(self):
        k = os.environ.get(f"HSL_KEY_{self.name.upper()}")
        if self.requires_key and not k:
            raise ConnectorError(f"HSL_KEY_{self.name.upper()} is not set")
        return k

    def fetch(self, symbol, start, end, allowlist):
        raise NotImplementedError

    def record(self, symbol, start, end, content):
        import hashlib
        return {"source": self.name, "host": self.host, "symbol": symbol, "start": start, "end": end,
                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "classification": self.classification}


class ReplayConnector(Connector):
    """Local fixture, the offline path. The symbol is the name of a file
    inside the fixtures directory (default `sample_data`), never a path:
    anything with a separator or a parent reference is refused, so the
    desk cannot be used to read arbitrary files on the host (Security
    Engineering chapter 6, access control)."""
    name = "replay"
    host = "local"
    classification = "synthetic"
    FIXTURES = "sample_data"

    def __init__(self, path=None):
        self.path = path

    def fetch(self, symbol, start, end, allowlist):
        if self.path:
            path = self.path
        else:
            name = (symbol or "").strip()
            if not name or any(ch in name for ch in ("/", "\\", "\x00")) or ".." in name:
                raise ConnectorError("replay takes the name of a fixture in sample_data, not a path")
            if not name.lower().endswith(".csv") and not name.lower().endswith(".json"):
                name += ".csv"
            path = os.path.join(self.FIXTURES, name)
        if not os.path.isfile(path):
            raise ConnectorError(f"replay fixture {os.path.basename(path)} not found")
        with open(path, "rb") as f:
            return f.read()


class AlphaVantageConnector(Connector):
    name = "alphavantage"
    host = "www.alphavantage.co"
    requires_key = True

    def fetch(self, symbol, start, end, allowlist):
        url = ("https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&outputsize=full&symbol="
               + urllib.parse.quote(symbol) + "&apikey=" + urllib.parse.quote(self.key()))
        data = json.loads(_https_get(url, allowlist).decode())
        series = data.get("Time Series (Daily)") or {}
        if not series:
            raise ConnectorError(data.get("Note") or data.get("Error Message") or "no series returned")
        pairs = sorted((t, v["4. close"]) for t, v in series.items() if start <= t <= end)
        return _csv_bytes(pairs)


class FREDConnector(Connector):
    name = "fred"
    host = "api.stlouisfed.org"
    requires_key = True

    def fetch(self, symbol, start, end, allowlist):
        url = ("https://api.stlouisfed.org/fred/series/observations?series_id=" + urllib.parse.quote(symbol)
               + "&observation_start=" + start + "&observation_end=" + end
               + "&file_type=json&api_key=" + urllib.parse.quote(self.key()))
        data = json.loads(_https_get(url, allowlist).decode())
        pairs = [(o["date"], o["value"]) for o in data.get("observations", []) if o.get("value") not in (".", None)]
        return _csv_bytes(pairs)


class ECBConnector(Connector):
    name = "ecb"
    host = "data-api.ecb.europa.eu"

    def fetch(self, symbol, start, end, allowlist):
        # symbol is FLOW/KEY, for example EXR/D.USD.EUR.SP00.A
        flow, _, key = symbol.partition("/")
        url = (f"https://data-api.ecb.europa.eu/service/data/{urllib.parse.quote(flow)}/{urllib.parse.quote(key)}"
               f"?format=csvdata&startPeriod={start}&endPeriod={end}")
        text = _https_get(url, allowlist, {"Accept": "text/csv"}).decode("utf-8-sig")
        import csv
        rows = list(csv.DictReader(io.StringIO(text)))
        pairs = [(r["TIME_PERIOD"], r["OBS_VALUE"]) for r in rows if r.get("OBS_VALUE") not in ("", None)]
        return _csv_bytes(pairs)


class BankOfEnglandConnector(Connector):
    name = "boe"
    host = "www.bankofengland.co.uk"

    def fetch(self, symbol, start, end, allowlist):
        def fmt(d):
            y, m, dd = d.split("-")
            return f"{int(dd):02d}/{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(m)-1]}/{y}"
        url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&SeriesCodes="
               + urllib.parse.quote(symbol) + f"&Datefrom={fmt(start)}&Dateto={fmt(end)}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
        text = _https_get(url, allowlist, {"Accept": "text/csv"}).decode("utf-8-sig")
        import csv
        rows = list(csv.reader(io.StringIO(text)))
        pairs = [(r[0], r[1]) for r in rows[1:] if len(r) >= 2 and r[1] not in ("", None)]
        return _csv_bytes(pairs)


class BloombergConnector(Connector):
    name = "bloomberg"
    host = "localhost"          # Desktop API session on the licensed host
    classification = "licensed"
    licensed = True

    def fetch(self, symbol, start, end, allowlist):
        try:
            import blpapi  # noqa: F401
        except ImportError as e:
            raise ConnectorError("blpapi is not installed; the Bloomberg connector needs a licensed Desktop API "
                                 "or B-PIPE session on the host") from e
        import blpapi
        session = blpapi.Session()
        if not session.start():
            raise ConnectorError("could not start a Bloomberg session")
        try:
            if not session.openService("//blp/refdata"):
                raise ConnectorError("could not open //blp/refdata")
            svc = session.getService("//blp/refdata")
            req = svc.createRequest("HistoricalDataRequest")
            req.getElement("securities").appendValue(symbol)
            req.getElement("fields").appendValue("PX_LAST")
            req.set("startDate", start.replace("-", ""))
            req.set("endDate", end.replace("-", ""))
            session.sendRequest(req)
            pairs = []
            waited = 0
            while True:
                ev = session.nextEvent(TIMEOUT_S * 1000)
                if ev.eventType() == blpapi.Event.TIMEOUT:
                    waited += TIMEOUT_S
                    if waited >= 3 * TIMEOUT_S:
                        raise ConnectorError("Bloomberg session timed out waiting for the response")
                    continue
                for msg in ev:
                    if msg.hasElement("responseError"):
                        raise ConnectorError("Bloomberg response error: " +
                                             msg.getElement("responseError").getElementAsString("message")[:160])
                    if msg.hasElement("securityData"):
                        sd = msg.getElement("securityData")
                        if sd.hasElement("securityError"):
                            raise ConnectorError("Bloomberg security error for " + symbol)
                        for fd in sd.getElement("fieldData").values():
                            if fd.hasElement("PX_LAST"):
                                pairs.append((fd.getElementAsString("date"), fd.getElementAsFloat("PX_LAST")))
                if ev.eventType() == blpapi.Event.RESPONSE:
                    break
        finally:
            session.stop()
        return _csv_bytes(pairs)


class LSEGConnector(Connector):
    name = "lseg"
    host = "api.refinitiv.com"
    classification = "licensed"
    licensed = True
    requires_key = True

    def fetch(self, symbol, start, end, allowlist):
        try:
            import refinitiv.data as rd  # noqa: F401
        except ImportError as e:
            raise ConnectorError("refinitiv.data is not installed; the LSEG connector needs the LSEG Data "
                                 "Library and an entitled session") from e
        if not egress_allowed(self.host, allowlist):
            raise ConnectorError(f"host {self.host} is not on the egress allowlist")
        import refinitiv.data as rd
        rd.open_session(app_key=self.key())
        try:
            df = rd.get_history(universe=symbol, fields=["TRDPRC_1"], start=start, end=end)
        finally:
            rd.close_session()
        if df is None or len(df) == 0:
            raise ConnectorError(f"LSEG returned no rows for {symbol}")
        pairs = [(str(i)[:10], float(v)) for i, v in zip(df.index, df.iloc[:, 0]) if v == v]
        return _csv_bytes(pairs)


CONNECTORS = {c.name: c for c in (ReplayConnector, AlphaVantageConnector, FREDConnector, ECBConnector,
                                  BankOfEnglandConnector, BloombergConnector, LSEGConnector)}


def fetch_dataset(source, symbol, start, end, cfg, uploader="", replay_path=None):
    """Fetch through a connector and pass the bytes through quarantine.
    Returns (dataset or refusal, connector record)."""
    from .ingest import quarantine
    if source not in CONNECTORS:
        raise ConnectorError(f"unknown source {source}; known: {', '.join(CONNECTORS)}")
    if source != "replay" and not getattr(cfg, "connectors", False):
        raise ConnectorError("connectors are disabled (HSL_CONNECTORS=off); the sandbox is air gapped")
    conn = ReplayConnector(replay_path) if source == "replay" else CONNECTORS[source]()
    allow = getattr(cfg, "egress_allowlist", []) or []
    content = conn.fetch(symbol, start, end, allow)
    rec = conn.record(symbol, start, end, content)
    label = os.path.splitext(os.path.basename(symbol))[0] if source == "replay" else symbol.replace("/", "_")
    label = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in label)[:60]
    ds = quarantine(f"{source}_{label}.csv", content, uploader=uploader,
                    classification=conn.classification, max_bytes=MAX_BYTES)
    if ds.get("ok"):
        ds["source"] = source
        ds["connector"] = rec
    return ds, rec
