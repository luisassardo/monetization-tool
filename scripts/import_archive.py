#!/usr/bin/env python3
"""
import_archive.py — refresh the tool's data/accounts.csv from the Meta
Monetization Archive, normalized and filtered to Latin America.

REFRESH THE DATA — ONE COMMAND (recommended)
--------------------------------------------
    python scripts/import_archive.py --fetch --output data/accounts.csv

`--fetch` pulls each Latin-American country directly from the archive's CSV
export endpoint (the same `csv_data_table` endpoint the site's "Export CSV"
button uses) and normalizes the result. No manual download needed. Use
`--dry-run` first to preview the row counts.

FROM A MANUAL EXPORT (fallback)
-------------------------------
If you'd rather export by hand from https://www.monetization.wtf/monetization-archive
(click "Export CSV"), pass the saved file:
       python scripts/import_archive.py --input raw_export.csv --dry-run
       python scripts/import_archive.py --input raw_export.csv --output data/accounts.csv

The raw export's column names are human-facing and have changed over time
(casing, spacing). This script normalizes them; if a future export uses names
that aren't recognized, extend COLUMN_ALIASES below. Run --dry-run first.

The 17-column target schema (order matters):
    account_id, account_name, account_handle, account_verified,
    page_created_date, account_subscriber_count, account_language_code,
    account_language, admin_location_code, admin_location, last_onboarding,
    first_recorded_monetization, last_recorded_monetization,
    facebook_instant_articles_session_count, facebook_in_stream_ads_session_count,
    facebook_ads_on_reels_session_count, facebook_content_monetization_session_count

Data: monetization.wtf / WHAT TO FIX (supported by Luminate) · CC BY-ND 4.0
"""

import argparse
import csv
import io
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd

# Archive export endpoint (same one the site's "Export CSV" button calls).
ARCHIVE_BASE = 'https://www.monetization.wtf/api/csv_data_table/'
ARCHIVE_REFERER = 'https://www.monetization.wtf/monetization-archive'
ARCHIVE_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Target schema, in output order.
TARGET_COLUMNS = [
    'account_id', 'account_name', 'account_handle', 'account_verified',
    'page_created_date', 'account_subscriber_count', 'account_language_code',
    'account_language', 'admin_location_code', 'admin_location', 'last_onboarding',
    'first_recorded_monetization', 'last_recorded_monetization',
    'facebook_instant_articles_session_count', 'facebook_in_stream_ads_session_count',
    'facebook_ads_on_reels_session_count', 'facebook_content_monetization_session_count',
]

# Raw header (lowercased, stripped, collapsed-whitespace) -> target column.
# Keys are normalized via _norm_header(); add new aliases here as exports evolve.
COLUMN_ALIASES = {
    # ids / names
    'account id': 'account_id',
    'page id': 'account_id',
    'facebook page id': 'account_id',
    'id': 'account_id',
    'account name': 'account_name',
    'page name': 'account_name',
    'facebook page name': 'account_name',
    'name': 'account_name',
    'account handle': 'account_handle',
    'handle': 'account_handle',
    'username': 'account_handle',
    'page username': 'account_handle',
    'vanity': 'account_handle',
    # verified
    'account verified': 'account_verified',
    'verified': 'account_verified',
    'is verified': 'account_verified',
    'page verified': 'account_verified',
    # dates
    'page created date': 'page_created_date',
    'page created': 'page_created_date',
    'created date': 'page_created_date',
    'creation date': 'page_created_date',
    'date created': 'page_created_date',
    'last onboarding': 'last_onboarding',
    'last onboarding date': 'last_onboarding',
    'onboarding date': 'last_onboarding',
    'first recorded monetization': 'first_recorded_monetization',
    'first monetization': 'first_recorded_monetization',
    'first seen': 'first_recorded_monetization',
    'date added': 'first_recorded_monetization',
    'last recorded monetization': 'last_recorded_monetization',
    'last monetization': 'last_recorded_monetization',
    'last seen': 'last_recorded_monetization',
    # subscribers / followers
    'account subscriber count': 'account_subscriber_count',
    'subscriber count': 'account_subscriber_count',
    'subscribers': 'account_subscriber_count',
    'followers': 'account_subscriber_count',
    'facebook page followers': 'account_subscriber_count',
    'facebook page follower count': 'account_subscriber_count',
    'page followers': 'account_subscriber_count',
    'follower count': 'account_subscriber_count',
    # language
    'account language code': 'account_language_code',
    'language code': 'account_language_code',
    'page language code': 'account_language_code',
    'account language': 'account_language',
    'language': 'account_language',
    'page language': 'account_language',
    # location
    'admin location code': 'admin_location_code',
    'primary admin location code': 'admin_location_code',
    'location code': 'admin_location_code',
    'country code': 'admin_location_code',
    'admin location': 'admin_location',
    'primary admin location': 'admin_location',
    'location': 'admin_location',
    'country': 'admin_location',
    # program session counts
    'facebook instant articles session count': 'facebook_instant_articles_session_count',
    'instant articles session count': 'facebook_instant_articles_session_count',
    'instant articles': 'facebook_instant_articles_session_count',
    'facebook in stream ads session count': 'facebook_in_stream_ads_session_count',
    'in stream ads session count': 'facebook_in_stream_ads_session_count',
    'in-stream ads session count': 'facebook_in_stream_ads_session_count',
    'in stream ads': 'facebook_in_stream_ads_session_count',
    'facebook ads on reels session count': 'facebook_ads_on_reels_session_count',
    'ads on reels session count': 'facebook_ads_on_reels_session_count',
    'ads on facebook reels session count': 'facebook_ads_on_reels_session_count',
    'ads on reels': 'facebook_ads_on_reels_session_count',
    'facebook content monetization session count': 'facebook_content_monetization_session_count',
    'content monetization session count': 'facebook_content_monetization_session_count',
    'content monetization': 'facebook_content_monetization_session_count',
}

# Latin America by ISO-3166-1 alpha-2 code. Filtering on code avoids
# display-name inconsistencies in the raw export.
LATAM_CODES = {
    'MX', 'GT', 'SV', 'HN', 'NI', 'CR', 'PA', 'BZ',           # North/Central America
    'CO', 'VE', 'EC', 'PE', 'BO', 'CL', 'AR', 'UY', 'PY', 'BR',  # South America
    'DO', 'CU', 'PR', 'HT',                                    # Caribbean (Latin)
}

# Display-name -> ISO-2, used when the export lacks a usable code column.
LOCATION_NAME_TO_CODE = {
    'mexico': 'MX', 'méxico': 'MX', 'guatemala': 'GT', 'el salvador': 'SV',
    'honduras': 'HN', 'nicaragua': 'NI', 'costa rica': 'CR', 'panama': 'PA',
    'panamá': 'PA', 'belize': 'BZ', 'belice': 'BZ', 'colombia': 'CO',
    'venezuela': 'VE', 'ecuador': 'EC', 'peru': 'PE', 'perú': 'PE',
    'bolivia': 'BO', 'chile': 'CL', 'argentina': 'AR', 'uruguay': 'UY',
    'paraguay': 'PY', 'brazil': 'BR', 'brasil': 'BR',
    'dominican republic': 'DO', 'república dominicana': 'DO', 'republica dominicana': 'DO',
    'cuba': 'CU', 'puerto rico': 'PR', 'haiti': 'HT', 'haití': 'HT',
}

CODE_TO_DISPLAY = {
    'MX': 'Mexico', 'GT': 'Guatemala', 'SV': 'El Salvador', 'HN': 'Honduras',
    'NI': 'Nicaragua', 'CR': 'Costa Rica', 'PA': 'Panama', 'BZ': 'Belize',
    'CO': 'Colombia', 'VE': 'Venezuela', 'EC': 'Ecuador', 'PE': 'Peru',
    'BO': 'Bolivia', 'CL': 'Chile', 'AR': 'Argentina', 'UY': 'Uruguay',
    'PY': 'Paraguay', 'BR': 'Brazil', 'DO': 'Dominican Republic', 'CU': 'Cuba',
    'PR': 'Puerto Rico', 'HT': 'Haiti',
}

# Normalize messy language values -> (code, display).
LANGUAGE_MAP = {
    'spanish': ('spa', 'Spanish'), 'español': ('spa', 'Spanish'), 'espanol': ('spa', 'Spanish'),
    'es': ('spa', 'Spanish'), 'spa': ('spa', 'Spanish'), 'es_la': ('spa', 'Spanish'),
    'es_es': ('spa', 'Spanish'), 'es_mx': ('spa', 'Spanish'),
    'portuguese': ('por', 'Portuguese'), 'português': ('por', 'Portuguese'),
    'portugues': ('por', 'Portuguese'), 'portuguese (brazil)': ('por', 'Portuguese'),
    'pt': ('por', 'Portuguese'), 'pt_br': ('por', 'Portuguese'), 'por': ('por', 'Portuguese'),
    'english': ('eng', 'English'), 'inglés': ('eng', 'English'), 'ingles': ('eng', 'English'),
    'en': ('eng', 'English'), 'en_us': ('eng', 'English'), 'eng': ('eng', 'English'),
    'french': ('fra', 'French'), 'fr': ('fra', 'French'), 'fra': ('fra', 'French'),
    'haitian creole': ('hat', 'Haitian Creole'), 'ht': ('hat', 'Haitian Creole'),
}

TRUE_VALUES = {'true', 'sí', 'si', 'yes', '1', 'y', 'verified', 'verdadero'}
DATE_COLS = ['page_created_date', 'last_onboarding', 'first_recorded_monetization', 'last_recorded_monetization']
INT_COLS = ['account_subscriber_count'] + [c for c in TARGET_COLUMNS if c.endswith('_session_count')]


def _norm_header(h):
    """Lowercase, strip, collapse internal whitespace, drop stray punctuation."""
    s = str(h).strip().lower().replace('_', ' ').replace('-', ' ')
    s = ' '.join(s.split())
    return s


def _clean_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    s = str(v)
    # strip control chars and stray wrapping quotes/backslashes
    s = ''.join(ch for ch in s if ch == '\t' or ord(ch) >= 32)
    s = s.strip().strip('"').strip()
    if s.endswith('\\'):
        s = s.rstrip('\\').strip()
    return s


def _normalize_dates(series):
    dt = pd.to_datetime(series, errors='coerce', utc=False)
    try:
        dt = dt.dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    today = pd.Timestamp(datetime.now().date())
    # Null out epoch / ghost / impossible dates.
    bad = dt.isna() | (dt.dt.year < 2004) | (dt > today + pd.Timedelta(days=365))
    dt = dt.where(~bad)
    return dt.dt.strftime('%Y-%m-%d')


def _http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={'User-Agent': ARCHIVE_UA, 'Referer': ARCHIVE_REFERER})
    try:
        ctx = ssl.create_default_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode('utf-8', 'replace')
    except urllib.error.URLError as e:
        # Some local Python installs lack a usable cert store (the SSL error
        # surfaces as URLError). The archive is a well-known public host, so
        # retry once with an unverified context.
        if isinstance(getattr(e, 'reason', None), ssl.SSLError):
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode('utf-8', 'replace')
        raise


def fetch_latam_csv(max_date=None, platform='facebook'):
    """Pull each LatAm country from the archive's CSV export endpoint and
    concatenate into one CSV string. Mirrors the site's "Export CSV" button."""
    max_date = max_date or datetime.now().strftime('%Y-%m-%d')
    header, body_lines, total = None, [], 0
    for code in sorted(LATAM_CODES):
        params = {
            'languages': '', 'program_name': '',
            'minDateCreated': '', 'maxDateCreated': '',
            'minDateIncluded': '', 'maxDateIncluded': max_date,
            'minSubscribers': '', 'maxSubscribers': '',
            'search': '', 'accountId': '',
            'orderByColumn': 'last_recorded_monetization', 'orderByDirection': 'desc',
            'platform': platform, 'locations': code,
        }
        url = ARCHIVE_BASE + '?' + urllib.parse.urlencode(params)
        try:
            text = _http_get(url)
        except Exception as e:
            print(f"  ! {code}: fetch failed ({e})", file=sys.stderr)
            continue
        lines = text.splitlines()
        if not lines:
            print(f"  {code}: 0 rows")
            continue
        if header is None:
            header = lines[0]
        rows = lines[1:]
        body_lines.extend(rows)
        total += len(rows)
        print(f"  {code}: {len(rows):,} rows (total {total:,})")
        time.sleep(0.3)  # be polite to the source
    if header is None:
        raise RuntimeError('No data returned from the archive endpoint.')
    return io.StringIO('\n'.join([header] + body_lines) + '\n')


def import_archive(input_source, output_path, dry_run=False):
    stats = {'rows_in': 0, 'dropped_non_latam': 0, 'dropped_no_id': 0,
             'dropped_header_dupe': 0, 'dedup_removed': 0, 'rows_out': 0}

    # 1. Read defensively (input_source: a path or a file-like object).
    df = pd.read_csv(
        input_source, dtype=str, keep_default_na=False,
        encoding='utf-8', encoding_errors='replace',
        on_bad_lines='skip', engine='python',
    )
    stats['rows_in'] = len(df)

    # 2. Normalize column casing -> target schema.
    rename, unmatched = {}, []
    for col in df.columns:
        target = COLUMN_ALIASES.get(_norm_header(col))
        if target:
            rename[col] = target
        else:
            unmatched.append(col)
    df = df.rename(columns=rename)
    # Keep only known target columns; create any missing ones empty.
    df = df[[c for c in df.columns if c in TARGET_COLUMNS]]
    df = df.loc[:, ~df.columns.duplicated()]
    for c in TARGET_COLUMNS:
        if c not in df.columns:
            df[c] = ''

    # 3. Drop the stray duplicated-header row (admin_location == 'admin_location').
    before = len(df)
    df = df[df['admin_location'].astype(str).str.strip().str.lower() != 'admin_location']
    stats['dropped_header_dupe'] = before - len(df)

    # 4. Clean strings.
    for c in ['account_id', 'account_name', 'account_handle', 'account_language',
              'account_language_code', 'admin_location', 'admin_location_code']:
        df[c] = df[c].map(_clean_str)

    # Drop rows without an account id (archive excludes these too).
    before = len(df)
    df = df[df['account_id'].astype(str).str.strip() != '']
    stats['dropped_no_id'] = before - len(df)

    # 5. Verified -> bool string.
    df['account_verified'] = df['account_verified'].map(
        lambda v: 'true' if _clean_str(v).lower() in TRUE_VALUES else 'false')

    # 6. Numbers.
    for c in INT_COLS:
        df[c] = (df[c].str.replace(r'[,\s]', '', regex=True)
                 .pipe(pd.to_numeric, errors='coerce').fillna(0).astype('int64'))

    # 7. Dates.
    for c in DATE_COLS:
        df[c] = _normalize_dates(df[c])

    # 8. Language normalization.
    def map_lang(row):
        for key in (row['account_language'], row['account_language_code']):
            hit = LANGUAGE_MAP.get(_clean_str(key).lower())
            if hit:
                return pd.Series(hit)
        return pd.Series((row['account_language_code'], row['account_language']))
    df[['account_language_code', 'account_language']] = df.apply(map_lang, axis=1)

    # 9. Resolve / backfill admin_location_code and filter to LatAm.
    def resolve_code(row):
        code = _clean_str(row['admin_location_code']).upper()
        if len(code) == 2:
            return code
        return LOCATION_NAME_TO_CODE.get(_clean_str(row['admin_location']).lower(), code)
    df['admin_location_code'] = df.apply(resolve_code, axis=1)
    # Prefer clean short display names for known codes (the raw export uses long
    # ISO names like "Bolivia, Plurinational State of"); fall back to the raw value.
    df['admin_location'] = df.apply(
        lambda r: CODE_TO_DISPLAY.get(r['admin_location_code'], r['admin_location']),
        axis=1)

    before = len(df)
    df = df[df['admin_location_code'].isin(LATAM_CODES)]
    stats['dropped_non_latam'] = before - len(df)

    # 10. Dedupe on account_id (keep last).
    before = len(df)
    df = df.drop_duplicates(subset='account_id', keep='last')
    stats['dedup_removed'] = before - len(df)

    # 11. Order columns, sort by subscribers desc for stable, readable output.
    df = df[TARGET_COLUMNS].sort_values('account_subscriber_count', ascending=False)
    stats['rows_out'] = len(df)

    # Summary.
    print('=' * 56)
    print(f"  rows in ................ {stats['rows_in']:,}")
    print(f"  dropped header-dupe .... {stats['dropped_header_dupe']:,}")
    print(f"  dropped (no id) ........ {stats['dropped_no_id']:,}")
    print(f"  dropped (non-LatAm) .... {stats['dropped_non_latam']:,}")
    print(f"  removed (dedupe) ....... {stats['dedup_removed']:,}")
    print(f"  rows out ............... {stats['rows_out']:,}")
    if unmatched:
        print(f"  unmatched columns ...... {', '.join(unmatched)}")
    if not df.empty:
        top = df['admin_location'].value_counts().head(10)
        print('  by country:')
        for loc, c in top.items():
            print(f"      {loc:<22} {c:,}")
    print('=' * 56)

    if dry_run:
        print('DRY RUN — nothing written.')
        return stats

    df.to_csv(output_path, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)
    print(f"Wrote {stats['rows_out']:,} rows -> {output_path}")
    return stats


def main(argv=None):
    p = argparse.ArgumentParser(description='Refresh data/accounts.csv from the Meta Monetization Archive (LatAm).')
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument('--fetch', action='store_true', help='Pull live from the archive export endpoint (all LatAm).')
    src.add_argument('--input', '-i', help='Use a CSV you exported manually from monetization.wtf.')
    p.add_argument('--output', '-o', default='data/accounts.csv', help='Output path (default: data/accounts.csv)')
    p.add_argument('--max-date', help="maxDateIncluded for --fetch (YYYY-MM-DD; default: today).")
    p.add_argument('--dry-run', action='store_true', help='Print the summary without writing.')
    args = p.parse_args(argv)
    try:
        if args.fetch:
            print(f"Fetching LatAm from the archive (maxDateIncluded={args.max_date or 'today'})…")
            source = fetch_latam_csv(max_date=args.max_date)
        else:
            source = args.input
        import_archive(source, args.output, dry_run=args.dry_run)
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
