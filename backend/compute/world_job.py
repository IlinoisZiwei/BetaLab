"""Scientific subprocess boundary; separate from all Trial2 execution paths."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
from .input_calibration import transform_points
from .world_geometry import align

def run(payload):
    calibration = payload['calibration']
    review = calibration['review']
    calibration['calibrated'] = transform_points(
        SimpleNamespace(**{**review,'planes':[SimpleNamespace(**p) for p in review['planes']]}),
        payload['summary'],payload['holds'])
    datasets = {}
    for name in ('pose','identity','alignment'):
        with np.load(payload['paths'][name],allow_pickle=False) as data:
            datasets[name] = {key:data[key] for key in data.files}
    return align(payload['review'],calibration,payload['summary'],payload['contacts'],
                 datasets['pose'],datasets['identity'],datasets['alignment'])

if __name__ == '__main__':
    try:
        print(json.dumps(run(json.loads(sys.stdin.read())),allow_nan=False))
    except (ValueError,KeyError,IndexError,np.linalg.LinAlgError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
