"""Read-only audit of extracted inputs. Model confidence is not human confirmation."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from .storage import digest

def audit(folder):
    folder=Path(folder)
    summary=json.loads((folder/'input_summary.json').read_text())
    holds=json.loads((folder/'holds.json').read_text())
    def rows(name):
        with (folder/name).open() as stream:return list(csv.DictReader(stream))
    mapping=rows('frame_map.csv');contacts=rows('contacts.csv');events=rows('contact_events.csv')
    n=summary['frame_count'];fps=summary['fps'];ids={h['hold_id'] for h in holds}
    issues=[]
    if len(ids)!=len(holds):issues.append('Duplicate hold IDs')
    if len(mapping)!=n or any(int(r['frame'])!=i for i,r in enumerate(mapping)):
        issues.append('Frame map coverage mismatch')
    times=[float(r['source_time_sec']) for r in mapping]
    if any(b<=a for a,b in zip(times,times[1:])):issues.append('Non-increasing source timestamps')
    if len(contacts)!=4*n:issues.append('Contact row count mismatch')
    keys=[(r['limb'],int(r['frame'])) for r in contacts]
    if len(set(keys))!=len(keys):issues.append('Duplicate limb/frame observations')
    for event in events:
        if event['hold_id'] not in ids or not 0<=int(event['start_frame'])<=int(event['end_frame'])<n:
            issues.append('Invalid contact event: '+str(event))
    return dict(source_video_sha256=summary['source_video_sha256'],frame_count=n,fps=fps,
        sampled_duration_seconds=n/fps,processing_seconds=summary['seconds'],hold_candidates=len(holds),
        contact_rows=len(contacts),contact_status_counts=dict(Counter(r['status'] for r in contacts)),
        candidate_events=len(events),events_requiring_review=events,
        structural_issues=issues,structural_checks_passed=not issues,
        artifact_sha256={p.name:digest(p) for p in folder.iterdir() if p.is_file()},
        human_contact_confirmation=False,generation_ready=False,
        limitations=['Structural checks do not validate pose accuracy, contact truth, wall geometry or camera motion'])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(audit(args.folder),indent=2))
if __name__=='__main__':main()
