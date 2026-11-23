"""Opt-in offline adapter for the two prepared CIS5810 cases; not a web worker.

References Beta_Translator trial1_refinement_pipeline.run_trial1_refinement and
full_sequence_pipeline.run_full_sequence at ff85726da2fbbd2616c409b01d6c03833ab62ce9.
Both use height/template proportions, not independent arm-span personalization.
Default operation only validates inputs; no Trial2 or technique comparison calls.
"""
import argparse
import importlib
import os
from pathlib import Path
import subprocess
import sys

SOURCE_COMMIT = 'ff85726da2fbbd2616c409b01d6c03833ab62ce9'
ENTRY_POINTS = {
    'trial1': ('trial1_sequence', 'load_inputs', 'trial1_refinement_pipeline', 'run_trial1_refinement'),
    'trial3': ('full_sequence_pipeline', 'load_full_sequence_inputs', 'full_sequence_pipeline', 'run_full_sequence'),
}


def run(source, trial, height=180., execute=False):
    if trial not in ENTRY_POINTS or not 100 <= height <= 230:
        raise ValueError('Unsupported case or height')
    if execute and os.getenv('BETALAB_DEMO_COMPUTE_ENABLED') != '1':
        raise ValueError('Live demo computation is disabled; set BETALAB_DEMO_COMPUTE_ENABLED=1 explicitly')
    source = Path(source).resolve()
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != SOURCE_COMMIT:
        raise ValueError('Unexpected Beta Translator revision')
    # Refuse modified scientific code; saved demos remain separately readable.
    if subprocess.check_output(['git', '-C', str(source), 'diff', 'HEAD', '--', 'beta_translator'], text=True):
        raise ValueError('Scientific code has uncommitted changes')
    sys.path.insert(0, str(source))
    loader_module, loader, solver_module, solver = ENTRY_POINTS[trial]
    inputs = getattr(importlib.import_module('beta_translator.' + loader_module), loader)(source)
    if not execute:
        return dict(case=trial, inputs_verified=True, algorithm_run=False,
                    independent_arm_span_supported=False, height_cm=height)
    result = getattr(importlib.import_module('beta_translator.' + solver_module), solver)(source, height_cm=height)
    return dict(case=trial, algorithm_run=True, result=result)


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial', choices=ENTRY_POINTS)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--height', type=float, default=180.)
    parser.add_argument('--execute', action='store_true', help='Run upstream solver and write a separate upstream output run; requires explicit environment opt-in')
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.trial, args.height, args.execute), default=str, indent=2))
