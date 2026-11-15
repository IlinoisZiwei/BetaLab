"""Run catalog migrations/seeds through Compose's psql; no host dependencies."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DB = Path(__file__).resolve().parent


def execute(sql):
    subprocess.run(
        ['docker', 'compose', 'exec', '-T', 'db', 'sh', '-c',
         'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
        input=sql, text=True, cwd=ROOT, check=True,
    )


def migrate():
    # One transaction and advisory lock serialize concurrent migration commands.
    statements = ['BEGIN;', 'SELECT pg_advisory_xact_lock(73114001);',
                  'CREATE TABLE IF NOT EXISTS schema_migrations '
                  '(version text PRIMARY KEY, checksum text NOT NULL, '
                  'applied_at timestamptz NOT NULL DEFAULT now());']
    for path in sorted((DB / 'migrations').glob('*.sql')):
        sql = path.read_text()
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        version = path.name.replace("'", "''")
        statements.append(f"""
DO $migration$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '{version}'
               AND checksum <> '{checksum}') THEN
        RAISE EXCEPTION 'Applied migration changed: {version}';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '{version}') THEN
        {sql}
        INSERT INTO schema_migrations(version, checksum) VALUES ('{version}', '{checksum}');
    END IF;
END
$migration$;
""")
    statements.append('COMMIT;')
    execute('\n'.join(statements))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['migrate', 'seed'])
    args = parser.parse_args()
    if args.command == 'migrate':
        migrate()
    else:
        execute('BEGIN;\n' + (DB / 'seeds/catalog.sql').read_text() + '\nCOMMIT;')
