"""New-video plane-local metric input, not a 3D motion or mechanics solver.

14.3 cm hole-grid convention follows the reviewed CIS5810 Beta_Translator scene
workflow (ff85726da2fbbd2616c409b01d6c03833ab62ce9). This validation/schema and
per-plane homography adapter are new BetaLab code. Never reuse Trial2 angles.
"""

def transform_points(review,summary,holds):
    import cv2
    import numpy as np
    if review.reference_frame!=summary['reference_frame']:raise ValueError('Wrong reference frame')
    if not set(review.selected_hold_ids).issubset({h['hold_id'] for h in holds}):raise ValueError('Unknown hold IDs')
    matrices={}
    for plane in review.planes:
        points=np.asarray(plane.grid_corners,np.float32);poly=np.asarray(plane.polygon,np.float32)
        for array in (points,poly):
            if not np.isfinite(array).all() or (array<0).any() or (array[:,0]>=summary['width']).any() or (array[:,1]>=summary['height']).any():raise ValueError('Points outside reference image')
        if not cv2.isContourConvex(points) or abs(cv2.contourArea(points))<25:raise ValueError('Grid corners must form a non-degenerate ordered quadrilateral')
        if not cv2.isContourConvex(poly) or abs(cv2.contourArea(poly))<25:raise ValueError('Use a convex non-degenerate panel polygon')
        if any(cv2.pointPolygonTest(poly,tuple(map(float,p)),False)<0 for p in points):raise ValueError('Grid corners must lie in their panel')
        w,h=plane.horizontal_steps*14.3,plane.vertical_steps*14.3
        H=cv2.getPerspectiveTransform(points,np.float32([[0,0],[w,0],[w,h],[0,h]]))
        if not np.isfinite(H).all() or np.linalg.cond(H)>1e10:raise ValueError('Unstable plane calibration')
        matrices[plane.id]=H.tolist()
    output=[]
    for hold in holds:
        if hold['hold_id'] not in review.selected_hold_ids:continue
        point=(float(hold['cx_px']),float(hold['cy_px']))
        matches=[p for p in review.planes if cv2.pointPolygonTest(np.float32(p.polygon),point,False)>=0]
        item=dict(hold_id=hold['hold_id'],center_px=point,plane_id=None,uv_cm=None,status='unassigned_or_ambiguous')
        if len(matches)==1:
            plane=matches[0];H=np.asarray(matrices[plane.id]);value=H@[*point,1]
            if abs(value[2])<1e-9:raise ValueError('Point lies at homography infinity')
            item.update(plane_id=plane.id,uv_cm=(value[:2]/value[2]).tolist(),status='plane_local_only')
        output.append(item)
    return dict(plane_homographies=matrices,holds=output,world_3d_aligned=False,body_dimensions_estimated=False,
        generation_ready=False,remaining=['Review contact candidates and identity','Calibrate joins/camera for global wall coordinates','Integrate new-video source adaptation separately'])

if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    try:
        from types import SimpleNamespace
        data = json.loads(sys.stdin.read())
        review = SimpleNamespace(**{**data, 'planes': [SimpleNamespace(**p) for p in data['planes']]})
        print(json.dumps(transform_points(review, json.loads(Path(sys.argv[1]).read_text()),
                                          json.loads(Path(sys.argv[2]).read_text())), allow_nan=False))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
