"""Back up, verify and restore the database, uploads and compute storage (A5.2).

Like manage.py, PostgreSQL tools run inside the Compose `db` container by
default (only Docker and Python are needed on the host); with --direct they
run on the host against the configured POSTGRES_* server. From the
repository root:

    python3 -m backend.db.backup backup                 # -> backups/<UTC time>/
    python3 -m backend.db.backup verify backups/<dir>   # restore into a scratch DB and compare
    python3 -m backend.db.backup restore backups/<dir> --yes

A backup holds db.dump (pg_dump custom format), uploads.tar.gz (UPLOAD_DIR),
compute.tar.gz (COMPUTE_STORAGE_DIR: published artifacts and reviews) and
manifest.json (row count per table, every referenced upload and artifact key,
SHA-256 of each file). `verify` restores the dump into a temporary database,
compares every table's row count with the manifest and checks that each file
the database references is in its archive; only a verified backup should be
trusted. `restore` replaces the live database and moves the current upload and
compute folders aside (never deletes them). Stop the API and worker first.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def read_env(path):
    """Minimal .env reader so this runs on a plain python3 (no packages), like manage.py."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


read_env(ROOT / '.env')
DB_NAME = os.getenv('POSTGRES_DB', 'betalab')


def folder(variable, default):
    path = Path(os.getenv(variable, default))
    return path if path.is_absolute() else (ROOT / path).resolve()


UPLOAD_DIR = folder('UPLOAD_DIR', './data/uploads')
COMPUTE_DIR = folder('COMPUTE_STORAGE_DIR', './data/compute')
ARCHIVES = {'uploads.tar.gz': UPLOAD_DIR, 'compute.tar.gz': COMPUTE_DIR}
CHECK_DB = f'{DB_NAME}_restore_check'
DIRECT = False  # set by --direct


def in_db(command, *, stdin=None, capture=True):
    """Run a shell command with POSTGRES_* set: in the db container, or on the host with --direct."""
    if DIRECT:
        env = dict(os.environ, PGHOST=os.getenv('POSTGRES_HOST', '127.0.0.1'), PGPORT=os.getenv('POSTGRES_PORT', '5433'),
                   PGPASSWORD=os.environ.get('POSTGRES_PASSWORD', ''), POSTGRES_USER=os.getenv('POSTGRES_USER', 'betalab'),
                   POSTGRES_DB=DB_NAME)
        result = subprocess.run(['sh', '-c', command], input=stdin, capture_output=capture, cwd=ROOT, env=env)
    else:
        result = subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'sh', '-c', command],
                                input=stdin, capture_output=capture, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f'Command failed in db container: {command}\n{(result.stderr or b"").decode(errors="replace")}')
    return result.stdout


def sql(query, database=None):
    target = f'"{database}"' if database else '"$POSTGRES_DB"'
    out = in_db(f'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d {target}', stdin=query.encode())
    return out.decode().strip()


def table_counts(database=None):
    tables = sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename", database).split()
    if not tables:
        return {}
    union = ' UNION ALL '.join(f"SELECT '{t}', count(*) FROM \"{t}\"" for t in tables)
    rows = sql(union + ';', database).splitlines()
    return {name: int(count) for name, count in (row.split('|') for row in rows)}


def referenced_files(database=None):
    """Files the database points at, per archive: local uploads and published compute artifacts."""
    uploads = sql("SELECT storage_key FROM user_videos WHERE storage_backend = 'local' ORDER BY storage_key", database)
    artifacts = sql("SELECT DISTINCT a.value->>'storage_key' FROM compute_results r, "
                    "jsonb_each(CASE WHEN jsonb_typeof(r.payload->'artifacts') = 'object' "
                    "THEN r.payload->'artifacts' ELSE '{}'::jsonb END) a "
                    "WHERE a.value ? 'storage_key' ORDER BY 1", database)
    return {'uploads.tar.gz': uploads.splitlines() if uploads else [],
            'compute.tar.gz': artifacts.splitlines() if artifacts else []}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup(args):
    target = Path(args.out or ROOT / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    target.mkdir(parents=True, exist_ok=False)
    # Counts first, then dump: a write in between shows up as a verify mismatch rather than passing silently.
    counts, keys = table_counts(), referenced_files()
    (target / 'db.dump').write_bytes(in_db('exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'))
    for name, source in ARCHIVES.items():
        with tarfile.open(target / name, 'w:gz') as archive:
            if source.is_dir():
                for path in sorted(source.rglob('*')):
                    if path.is_file() and not path.name.startswith('.upload-'):  # skip in-progress uploads
                        archive.add(path, arcname=path.relative_to(source).as_posix())
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'database': DB_NAME,
        'migrations': sql('SELECT version FROM schema_migrations ORDER BY version').splitlines(),
        'table_counts': counts,
        'referenced_files': keys,
        'files': {name: sha256(target / name) for name in ('db.dump', *ARCHIVES)},
    }
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Backup written to {target}')
    print(f"  {sum(counts.values())} rows in {len(counts)} tables, {len(keys['uploads.tar.gz'])} video files, "
          f"{len(keys['compute.tar.gz'])} compute artifacts")
    print(f'Next: python3 -m backend.db.backup verify {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}'
          + (' --direct' if DIRECT else ''))


def load_backup(path):
    folder = Path(path)
    manifest = json.loads((folder / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if sha256(folder / name) != expected:
            sys.exit(f'{name} does not match its checksum; the backup is damaged.')
    return folder, manifest


def archive_names(folder, name):
    with tarfile.open(folder / name, 'r:gz') as archive:
        return {member.name for member in archive.getmembers() if member.isfile()}


def verify(args):
    folder, manifest = load_backup(args.backup)
    problems = []
    in_db(f'exec psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \'DROP DATABASE IF EXISTS "{CHECK_DB}" WITH (FORCE)\' '
          f'-c \'CREATE DATABASE "{CHECK_DB}"\'')
    try:
        in_db(f'exec pg_restore --no-owner --exit-on-error -U "$POSTGRES_USER" -d "{CHECK_DB}"',
              stdin=(folder / 'db.dump').read_bytes())
        restored = table_counts(CHECK_DB)
        for table, expected in manifest['table_counts'].items():
            if restored.get(table) != expected:
                problems.append(f'table {table}: expected {expected} rows, restored {restored.get(table)}')
        restored_keys = referenced_files(CHECK_DB)
    finally:
        in_db(f'exec psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \'DROP DATABASE IF EXISTS "{CHECK_DB}" WITH (FORCE)\'')
    for name, keys in restored_keys.items():
        missing = sorted(set(keys) - archive_names(folder, name))
        if missing:
            problems.append(f'{len(missing)} file(s) referenced by the database are not in {name}: {missing[:5]}')
    if problems:
        print('Backup verification FAILED:')
        for problem in problems:
            print(f'  - {problem}')
        sys.exit(1)
    print(f'Backup verified: restored into a scratch database, {len(manifest["table_counts"])} tables match, '
          f"all {len(restored_keys['uploads.tar.gz'])} video files and {len(restored_keys['compute.tar.gz'])} "
          'compute artifacts present.')


def restore(args):
    folder, manifest = load_backup(args.backup)
    if not args.yes:
        sys.exit('restore replaces the current database, upload and compute folders. Stop the API and worker, then re-run with --yes.')
    print(f'Restoring database "{DB_NAME}" from {folder} …')
    in_db('exec pg_restore --clean --if-exists --no-owner --single-transaction --exit-on-error '
          '-U "$POSTGRES_USER" -d "$POSTGRES_DB"', stdin=(folder / 'db.dump').read_bytes())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for name, target in ARCHIVES.items():
        if target.exists():
            aside = target.with_name(f'{target.name}.before-restore-{stamp}')
            target.rename(aside)
            print(f'Previous {target.name} moved to {aside} (delete it yourself once the restore looks right).')
        target.mkdir(parents=True)
        with tarfile.open(folder / name, 'r:gz') as archive:
            members = archive.getmembers()
            for member in members:  # refuse anything that would land outside the folder
                destination = (target / member.name).resolve()
                if not member.isfile() and not member.isdir() or not destination.is_relative_to(target):
                    sys.exit(f'Refusing unsafe archive entry: {member.name}')
            try:
                archive.extractall(target, members=members, filter='data')
            except TypeError:  # Python without extraction filters (e.g. macOS 3.9); entries were checked above
                archive.extractall(target, members=members)
    counts = table_counts()
    mismatched = [t for t, n in manifest['table_counts'].items() if counts.get(t) != n]
    if mismatched:
        sys.exit(f'Restore finished but row counts differ for: {", ".join(mismatched)}')
    print('Restore complete; row counts match the backup. Start the API and worker again and sign in to check.')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('backup', help='write a new backup folder')
    p.add_argument('--out', help='folder to create (default: backups/<UTC time>)')
    p.set_defaults(run=backup)
    p = commands.add_parser('verify', help='restore into a scratch database and compare with the manifest')
    p.add_argument('backup')
    p.set_defaults(run=verify)
    p = commands.add_parser('restore', help='replace the live database and uploads with a backup')
    p.add_argument('backup')
    p.add_argument('--yes', action='store_true', help='confirm replacing current data')
    p.set_defaults(run=restore)
    for command in commands.choices.values():
        command.add_argument('--direct', action='store_true', help='use host PostgreSQL tools instead of Docker')
    args = parser.parse_args()
    global DIRECT
    DIRECT = args.direct
    args.run(args)


if __name__ == '__main__':
    main()
