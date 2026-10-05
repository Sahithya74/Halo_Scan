#!/usr/bin/env python
"""Generate a self-signed TLS certificate for local HTTPS.

Browsers only allow camera access on HTTPS or http://localhost, so this is needed to use the
camera from a phone or tablet on the same network. The cert is self-signed: the browser will
warn once, and you accept it for this device.

Usage:
  python scripts/make_dev_cert.py --host 192.168.1.20
  cd backend
  HALO_COOKIE_SECURE=true .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8443 \
      --ssl-keyfile secrets/dev-key.pem --ssl-certfile secrets/dev-cert.pem
"""
import argparse
import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "secrets"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", action="append", default=[], help="LAN IP or hostname (repeatable)")
    args = parser.parse_args()

    names: list[x509.GeneralName] = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    for h in args.host:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(h)))
        except ValueError:
            names.append(x509.DNSName(h))

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Halo Scan dev")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(key, hashes.SHA256())
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dev-key.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (OUT_DIR / "dev-cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Wrote {OUT_DIR / 'dev-cert.pem'} and dev-key.pem (valid 1 year) for: "
          + ", ".join(str(n.value) for n in names))


if __name__ == "__main__":
    main()
