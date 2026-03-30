from __future__ import annotations

import argparse
import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


def normalize_domain(domain: str) -> str:
    value = domain.strip().lower()
    value = re.sub(r'^https?://', '', value)
    return value.strip('/').split('/')[0]


def _sanitize_package_segment(value: str) -> str:
    segment = re.sub(r'[^a-z0-9_]', '_', value.lower())
    segment = re.sub(r'_+', '_', segment).strip('_')
    if not segment:
        return 'app'
    if not segment[0].isalpha():
        segment = f'x{segment}'
    return segment


def derive_android_package_name(domain: str, app_slug: str = 'signalflow') -> str:
    hostname = normalize_domain(domain)
    labels = [_sanitize_package_segment(part) for part in hostname.split('.') if part.strip()]
    if not labels:
        return f'com.example.{app_slug}'
    reversed_labels = list(reversed(labels))
    if app_slug not in reversed_labels:
        reversed_labels.append(_sanitize_package_segment(app_slug))
    return '.'.join(reversed_labels)


def generate_secret_key(num_bytes: int = 48) -> str:
    return base64.urlsafe_b64encode(os.urandom(num_bytes)).decode('ascii').rstrip('=')


@dataclass(frozen=True)
class ProductionEnvValues:
    domain: str
    database_url: str
    secret_key: str
    android_package_name: str
    android_sha256_cert_fingerprints: str = ''

    @property
    def web_url(self) -> str:
        return f'https://{self.domain}'

    @property
    def api_url(self) -> str:
        return self.web_url

    @property
    def websocket_url(self) -> str:
        return f'wss://{self.domain}/ws/stream'

    def render(self) -> str:
        lines = [
            f'SIGNAL_FLOW_DOMAIN={self.domain}',
            f'SIGNAL_FLOW_SECRET_KEY={self.secret_key}',
            f'DATABASE_URL={self.database_url}',
            f'SIGNAL_FLOW_PUBLIC_WEB_BASE_URL={self.web_url}',
            f'SIGNAL_FLOW_PUBLIC_API_BASE_URL={self.api_url}',
            f'SIGNAL_FLOW_PUBLIC_WS_BASE_URL={self.websocket_url}',
            f'SIGNAL_FLOW_CORS_ORIGINS={self.web_url}',
            f'SIGNAL_FLOW_ANDROID_PACKAGE_NAME={self.android_package_name}',
            f'SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS={self.android_sha256_cert_fingerprints}',
        ]
        return '\n'.join(lines) + '\n'


def build_env_values(
    domain: str,
    database_url: str,
    *,
    android_package_name: str | None = None,
    android_sha256_cert_fingerprints: str = '',
    secret_key: str | None = None,
) -> ProductionEnvValues:
    normalized_domain = normalize_domain(domain)
    return ProductionEnvValues(
        domain=normalized_domain,
        database_url=database_url.strip(),
        secret_key=secret_key or generate_secret_key(),
        android_package_name=android_package_name or derive_android_package_name(normalized_domain),
        android_sha256_cert_fingerprints=android_sha256_cert_fingerprints.strip(),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate a production .env file for Signal Flow.')
    parser.add_argument('--domain', required=True, help='Public HTTPS domain, e.g. signals.example.com')
    parser.add_argument('--database-url', required=True, help='Production PostgreSQL DATABASE_URL')
    parser.add_argument('--output', default='.env.production', help='Output file path')
    parser.add_argument('--android-package-name', help='Override the derived Android package name')
    parser.add_argument(
        '--android-sha256-cert-fingerprints',
        default='',
        help='Comma-separated release certificate SHA256 fingerprints',
    )
    parser.add_argument('--secret-key', help='Override the generated secret key')
    parser.add_argument('--force', action='store_true', help='Overwrite the output file if it already exists')
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        raise SystemExit(f'{output_path} already exists. Use --force to overwrite it.')

    values = build_env_values(
        args.domain,
        args.database_url,
        android_package_name=args.android_package_name,
        android_sha256_cert_fingerprints=args.android_sha256_cert_fingerprints,
        secret_key=args.secret_key,
    )
    output_path.write_text(values.render(), encoding='utf-8')
    print(f'Wrote {output_path}')
    print(f'domain={values.domain}')
    print(f'web={values.web_url}')
    print(f'api={values.api_url}')
    print(f'ws={values.websocket_url}')
    print(f'android_package_name={values.android_package_name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
