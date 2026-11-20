"""B5.2: create or update the demo accounts (and optionally upload their demo videos).

Passwords never live in the repository. Copy demo/accounts.example.json to
demo/accounts.local.json (git-ignored), set real passwords, then run from the
repository root with the same .env as the API:

    backend/.venv/bin/python -m backend.db.demo_accounts demo/accounts.local.json
    backend/.venv/bin/python -m backend.db.demo_accounts demo/accounts.local.json --upload   # API must be running

Accounts are written straight to the database, so this works even with
REGISTRATION_ENABLED=false. Rerunning is safe: existing accounts keep their
password unless --reset-passwords is given; profiles are updated; videos whose
title the account already has are skipped. Nothing secret is printed.
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

USERNAME = re.compile(r'^[A-Za-z0-9_]{3,32}$')
PLACEHOLDER = 'CHANGE-ME'


def load(path):
    data = json.loads(Path(path).read_text())
    accounts = data.get('accounts')
    if not isinstance(accounts, list) or not accounts:
        sys.exit('No "accounts" list in ' + str(path))
    for account in accounts:
        name = account.get('username', '')
        if not USERNAME.match(name):
            sys.exit(f'Invalid username {name!r}: 3–32 letters, digits or _')
        password = account.get('password', '')
        if len(password) < 8 or PLACEHOLDER in password:
            sys.exit(f'Set a real password (8+ characters) for {name} in {path}')
        for field, low, high in (('height_cm', 100, 230), ('arm_span_cm', 80, 260)):
            value = account.get(field)
            if value is not None and not low <= value <= high:
                sys.exit(f'{name}: {field} must be between {low} and {high}')
    return accounts


def upsert_accounts(accounts, reset_passwords):
    from backend.auth import passwords
    from backend.database import database
    with database() as db:
        for account in accounts:
            username = account['username'].lower()
            display = account.get('display_name') or account['username']
            row = db.execute('SELECT id FROM users WHERE username = %s', (username,)).fetchone()
            if row:
                db.execute('UPDATE users SET display_name = %s, height_cm = %s, arm_span_cm = %s, updated_at = now() '
                           'WHERE id = %s', (display, account.get('height_cm'), account.get('arm_span_cm'), row['id']))
                if reset_passwords:
                    db.execute('UPDATE users SET password_hash = %s WHERE id = %s',
                               (passwords.hash(account['password']), row['id']))
                    db.execute('DELETE FROM sessions WHERE user_id = %s', (row['id'],))
                print(f'updated  {username}' + (' (password reset)' if reset_passwords else ''))
            else:
                db.execute('INSERT INTO users(id, username, password_hash, display_name, height_cm, arm_span_cm) '
                           'VALUES (%s, %s, %s, %s, %s, %s)',
                           (uuid4(), username, passwords.hash(account['password']), display,
                            account.get('height_cm'), account.get('arm_span_cm')))
                print(f'created  {username}')


class Api:
    """Minimal client for the running API (standard library only)."""

    def __init__(self, base, origin):
        self.base, self.origin, self.csrf = base.rstrip('/'), origin, None
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, content_type='application/json'):
        headers = {'Origin': self.origin}
        if self.csrf and method != 'GET':
            headers['X-CSRF-Token'] = self.csrf
        if body is not None:
            headers['Content-Type'] = content_type
            if content_type == 'application/json':
                body = json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=body, method=method, headers=headers)
        try:
            with self.opener.open(request) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read() or b'{}').get('error', {}).get('message', error.reason)
            raise RuntimeError(f'{method} {path}: {error.code} {detail}') from None
        return json.loads(raw) if raw else None

    def login(self, username, password):
        self.csrf = self.call('POST', '/api/auth/login', {'username': username, 'password': password})['csrf_token']

    def upload(self, video):
        path = Path(video['path']).expanduser()
        boundary = 'betalab' + uuid4().hex
        fields = {'route_id': video['route_id'], 'title': video.get('title', path.stem),
                  'description': video.get('description', ''), 'visibility': video.get('visibility', 'public'),
                  'share_as_beta': 'true' if video.get('share_as_beta') else 'false'}
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                 for k, v in fields.items()]
        media = mimetypes.guess_type(path.name)[0] or 'video/mp4'
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="{path.name}"\r\n'
                     f'Content-Type: {media}\r\n\r\n'.encode() + path.read_bytes() + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        return self.call('POST', '/api/videos', b''.join(parts), f'multipart/form-data; boundary={boundary}')


def upload_videos(accounts, base, origin):
    for account in accounts:
        videos = account.get('videos') or []
        if not videos:
            continue
        api = Api(base, origin)
        api.login(account['username'], account['password'])
        existing = {v['title'] for v in api.call('GET', '/api/videos?owned=true&limit=100')['items']}
        for video in videos:
            title = video.get('title') or Path(video['path']).stem
            if title in existing:
                print(f'skipped  {account["username"]}: "{title}" already uploaded')
                continue
            if not Path(video['path']).expanduser().is_file():
                sys.exit(f'{account["username"]}: video file not found: {video["path"]}')
            created = api.upload(video)
            print(f'uploaded {account["username"]}: "{created["title"]}" ({created["visibility"]}'
                  f'{", Community Beta" if created["share_as_beta"] else ""})')


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('file', help='accounts JSON (keep it out of Git, e.g. demo/accounts.local.json)')
    parser.add_argument('--reset-passwords', action='store_true', help='also reset passwords of existing accounts')
    parser.add_argument('--upload', action='store_true', help='upload each account\'s "videos" through the running API')
    parser.add_argument('--api', default='http://127.0.0.1:8788', help='API base URL for --upload')
    parser.add_argument('--origin', default=None, help='allowed Origin for --upload (default: first APP_ORIGINS entry)')
    args = parser.parse_args()
    accounts = load(args.file)
    upsert_accounts(accounts, args.reset_passwords)
    if args.upload:
        origin = args.origin or os.getenv('APP_ORIGINS', 'http://127.0.0.1:5173').split(',')[0].strip()
        upload_videos(accounts, args.api, origin)


if __name__ == '__main__':
    main()
