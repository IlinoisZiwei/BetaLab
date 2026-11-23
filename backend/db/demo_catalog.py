"""Seed prepared skeleton demos via authenticated uploads; keep credentials/media local.

Run after migration 016 and demo_render preparation. The JSON config is local-only.
Reruns reuse source videos and saved entries. No solver or analysis is submitted.
"""
import argparse
import json
from pathlib import Path
from psycopg.types.json import Jsonb
from backend.database import database
from backend.db.demo_accounts import Api, load, upsert_accounts
from backend.compute.storage import digest, resolve, video_path


def seed(config_path, base='http://127.0.0.1:8788', origin='http://127.0.0.1:5173'):
    config = json.loads(Path(config_path).read_text())
    accounts = load(config_path)
    upsert_accounts(accounts, False)
    account = accounts[0]
    api = Api(base, origin); api.login(account['username'], account['password'])
    with database() as db:
        owner = db.execute('SELECT id FROM users WHERE username=%s', (account['username'].lower(),)).fetchone()['id']
    receipt = []
    for case in config['cases']:
        with database() as db:
            db.execute('INSERT INTO routes(id,gym_id,name,grade,set_label) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                       (case['route_id'], 'gym-a', case['title'], 'Demo', 'Demo case · venue unverified'))
            old = db.execute('SELECT * FROM user_videos WHERE owner_id=%s AND title=%s', (owner, case['title'])).fetchone()
        if old:
            if old['route_id'] != case['route_id'] or digest(video_path(old)) != digest(case['original']):
                raise ValueError('Existing demo video identity differs')
            video_id = str(old['id'])
        else:
            video_id = api.upload(dict(path=case['original'], route_id=case['route_id'], title=case['title'],
                visibility='public', share_as_beta=True,
                description='CIS5810 demonstration. Use skeleton opens a pre-generated diagnostic, not live personalized generation. Venue not independently verified.'))['id']
        artifacts = {}
        for name, item in case['artifacts'].items():
            path = resolve(item)
            artifacts[name] = dict(storage_key=item, sha256=digest(path), media_type='video/mp4' if path.suffix=='.mp4' else 'image/jpeg' if path.suffix=='.jpg' else 'application/json')
        payload = dict(title=case['title'], target_height_cm=case['target_height_cm'],
            target_arm_span_cm=case.get('target_arm_span_cm'), frame_count=case['frame_count'], fps=30.,
            limitations=case['limitations'], artifacts=artifacts,
            source_sha256=digest(case['original']), generation_mode='precomputed')
        with database() as db:
            db.execute('INSERT INTO demo_previews(video_id,payload) VALUES (%s,%s) ON CONFLICT(video_id) DO UPDATE SET payload=EXCLUDED.payload',
                       (video_id, Jsonb(payload)))
            db.execute('INSERT INTO saved_demo_previews(owner_id,video_id) VALUES (%s,%s) ON CONFLICT DO NOTHING', (owner,video_id))
        receipt.append(dict(video_id=video_id, route_id=case['route_id'], title=case['title']))
    path = Path(config_path).with_name('showcase-receipt.local.json')
    path.write_text(json.dumps(receipt, indent=2)); print('Prepared',len(receipt),'demo cases; receipt:',path)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--api',default='http://127.0.0.1:8788')
    parser.add_argument('--origin',default='http://127.0.0.1:5173')
    args=parser.parse_args();seed(args.config,args.api,args.origin)
