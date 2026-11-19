"""Import the approved local route-highlight batch and generate its catalog migration."""
import argparse
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path, help='route-highlights directory with delivery-manifest.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
items = json.loads((args.source / 'delivery-manifest.json').read_text())['images']
colors = {'teal':'Teal','white':'White','green':'Green','pink':'Pink','blue':'Blue','red':'Red','yellow':'Yellow','black':'Black','pink-right':'Pink · Right','white-v7':'White · V7','white-v8':'White · V8','black-strips':'Black · Rails'}
records = []
for item in items:
    key = f"movement-{item['n']}-{item['color']}"
    filename = f"IMG_{item['n']}_{item['color']}.jpg"
    target = root / 'public/media/movement-facetime' / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        subprocess.run(['sips','-s','format','jpeg','-s','formatOptions','88',str(args.source/item['file']),'--out',str(target)],check=True,stdout=subprocess.DEVNULL)
    grade = re.search(r'\bV(?:Intro|\d+)\b', item['selection'])
    records.append({'id':key,'gym':'Movement Fishtown','name':f"{colors[item['color']]} · {item['n']}",'grade':grade.group() if grade else 'Unrated','version':'Photo collection','archived':False,'image':f'media/movement-facetime/{filename}','sourcePhoto':f"IMG_{item['n']}",'reviewNote':item.get('qaNote','')})
(root/'src/data/movementRoutes.json').write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n')
q = lambda s: "'" + s.replace("'", "''") + "'"
sql = ["-- Bundled route photos; stable IDs preserve user uploads and bookmarks.","INSERT INTO gyms (id, name, location_label) VALUES ('gym-a', 'Movement Fishtown', '') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = now();"]
for r in records:
    sql.append('INSERT INTO routes (id,gym_id,name,grade,set_label,archived) VALUES ('+','.join(map(q,[r['id'],'gym-a',r['name'],r['grade'],r['version']]))+',false) ON CONFLICT (id) DO NOTHING;')
    sql.append('INSERT INTO route_media (id,route_id,kind,storage_key,is_primary) VALUES ('+','.join(map(q,[r['id']+'-wall',r['id'],'wall_image',r['image']]))+',true) ON CONFLICT (id) DO NOTHING;')
(root/'backend/db/migrations/008_movement_route_photos.sql').write_text('\n'.join(sql)+'\n')
print(f'Imported {len(records)} photos')
