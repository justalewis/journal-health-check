"""Continuity: does the journal's site present a valid TLS certificate, and when
does it expire?

Source: a direct TLS handshake to port 443 with hostname verification on.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone

import certifi

from ..models import CONTINUITY, FAIL, NA, PASS, UNKNOWN, WARN, CheckResult, Evidence

NAME = "tls"
AREA = CONTINUITY
LABEL = "HTTPS certificate"

# Let's Encrypt certificates last 90 days and renew with 30 left, so a short
# remaining life is normal. Under two weeks means renewal has likely stalled.
WARN_DAYS = 14


def handshake(host: str, port: int = 443, timeout: float = 15.0) -> dict:
    """{'cert': dict} on success, or {'error': str, 'kind': ...} on failure."""
    # Mozilla's root store via certifi, not the OS store: a Windows box
    # missing a new Let's Encrypt root once failed a valid certificate as
    # "expired". Results must not depend on which machine runs the harvest.
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                return {"cert": tls.getpeercert(), "version": tls.version()}
    except ssl.SSLCertVerificationError as exc:
        return {"error": exc.verify_message or str(exc), "kind": "verify"}
    except ssl.SSLError as exc:
        return {"error": str(exc), "kind": "tls"}
    except (socket.timeout, TimeoutError):
        return {"error": "timed out", "kind": "timeout"}
    except ConnectionRefusedError:
        return {"error": "connection refused on port 443", "kind": "refused"}
    except socket.gaierror as exc:
        return {"error": f"DNS lookup failed: {exc}", "kind": "dns"}
    except OSError as exc:
        return {"error": str(exc), "kind": "os"}


def _name(rdn_seq) -> str | None:
    for rdn in rdn_seq or ():
        for k, v in rdn:
            if k in ("organizationName", "commonName"):
                return v
    return None


def run(journal, http=None, now: datetime | None = None, shake=handshake) -> CheckResult:
    host = journal.host
    if not host:
        return CheckResult(NAME, AREA, NA, "No web presence.")
    now = now or datetime.now(timezone.utc)
    res = shake(host)
    ev_url = f"tls://{host}:443"

    if "error" in res:
        ev = [Evidence(url=ev_url, excerpt=res)]
        if res["kind"] in ("timeout", "os"):
            return CheckResult(NAME, AREA, UNKNOWN, f"The handshake with {host} didn't complete ({res['error']}).",
                               evidence=ev)
        if res["kind"] == "dns":
            return CheckResult(NAME, AREA, FAIL, f"{host} doesn't resolve in DNS.", evidence=ev,
                               value={"host": host})
        if res["kind"] == "refused":
            return CheckResult(NAME, AREA, FAIL, f"{host} doesn't accept HTTPS connections.",
                               evidence=ev, value={"host": host})
        return CheckResult(NAME, AREA, FAIL, f"{host}'s certificate didn't validate: {res['error']}.",
                           evidence=ev, value={"host": host})

    cert = res["cert"]
    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days = (not_after - now).days
    issuer = _name(cert.get("issuer"))
    value = {"host": host, "not_after": not_after.isoformat(), "days_left": days,
             "issuer": issuer, "protocol": res.get("version")}
    ev = [Evidence(url=ev_url, excerpt={
        "subject": _name(cert.get("subject")), "issuer": issuer,
        "notBefore": cert.get("notBefore"), "notAfter": cert.get("notAfter"),
        "subjectAltName": [v for _, v in cert.get("subjectAltName", ())][:10],
        "protocol": res.get("version")})]
    when = f"{not_after.strftime('%B')} {not_after.day}, {not_after.year}"
    if days < WARN_DAYS:
        return CheckResult(NAME, AREA, WARN, f"Valid certificate from {issuer}, but it expires {when}, "
                           f"in {days} days.", value=value, evidence=ev)
    return CheckResult(NAME, AREA, PASS, f"Valid certificate from {issuer}, good through {when}.",
                       value=value, evidence=ev)
