"""Shared PostgreSQL connections for the API and standalone compute worker."""
from contextlib import contextmanager
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

def connect(**options):
    return psycopg.connect(host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=os.getenv('POSTGRES_PORT', '5433'), dbname=os.getenv('POSTGRES_DB', 'betalab'),
        user=os.getenv('POSTGRES_USER', 'betalab'), password=os.environ['POSTGRES_PASSWORD'],
        row_factory=dict_row, **options)

@contextmanager
def database():
    with connect() as connection:
        yield connection
