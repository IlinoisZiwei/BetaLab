"""New-video panel assembly and calibrated camera rays (centimeters, Y up).

References CIS5810 Beta_Translator scene3d.py and trial2_scene3d.py at
ff85726da2fbbd2616c409b01d6c03833ab62ce9: world Y-up coordinates, world-to-camera
R/t and pixel reprojection. This measured hinge-tree/PnP adapter is new BetaLab
code. Unlike the experiments it never estimates unmeasured intrinsics, copies
Trial2 geometry, or treats a multi-plane image homography as recovered 3D.
"""
import cv2
import numpy as np

FIT_RMSE_PX = 5.
CHECK_MAX_PX = 8.
TRACK_MAX_PX = 3.

def unit(value):
    v = np.asarray(value, float)
    if abs(np.linalg.norm(v)-1) > 1e-5: raise ValueError('Root axes must be unit vectors')
    return v

def assemble(review, calibration):
    planes = {p['id']: p for p in calibration['review']['planes']}
    root = review['root']
    if root['plane_id'] not in planes: raise ValueError('Unknown root panel')
    u, v = unit(root['u_axis']), unit(root['v_axis'])
    if abs(u@v) > 1e-5: raise ValueError('Root axes must be orthogonal')
    frames = {root['plane_id']: (np.asarray(root['origin_cm']), u, v)}
    pending = list(review['joins'])
    residuals = []
    while pending:
        ready = [j for j in pending if j['parent'] in frames]
        if not ready: raise ValueError('Panel joins are disconnected or cyclic')
        for join in ready:
            parent, child = join['parent'], join['child']
            if child not in planes or child in frames: raise ValueError('Unknown, duplicate or cyclic child panel')
            a, b = np.asarray(join['parent_edge_cm'], float)
            c, d = np.asarray(join['child_edge_cm'], float)
            length, other = np.linalg.norm(b-a), np.linalg.norm(d-c)
            if length < 1 or abs(length-other) > .1: raise ValueError('Joined edge lengths must match within 0.1 cm')
            o, pu, pv = frames[parent]
            start = o+a[0]*pu+a[1]*pv
            axis = ((b-a)[0]*pu+(b-a)[1]*pv)/length
            rotation = cv2.Rodrigues(axis*np.deg2rad(join['fold_deg']))[0]
            normal = rotation @ np.cross(pu, pv)
            side = np.cross(normal, axis)
            direction = (d-c)/other
            cu = direction[0]*axis-direction[1]*side
            cv = direction[1]*axis+direction[0]*side
            co = start-c[0]*cu-c[1]*cv
            frames[child] = (co, cu, cv)
            gap = np.linalg.norm(co+d[0]*cu+d[1]*cv-(o+b[0]*pu+b[1]*pv))
            residuals.append(dict(parent=parent, child=child, seam_gap_cm=float(gap)))
            pending.remove(join)
    if set(frames) != set(planes): raise ValueError('Every calibrated panel must be joined to the root')
    for name, (_, u, v) in frames.items():
        angle = planes[name]['angle_from_horizontal_deg']
        if angle is None: raise ValueError('Each panel needs its measured angle from horizontal')
        measured = min(angle, 180-angle)
        actual = np.rad2deg(np.arccos(np.clip(abs(np.cross(u, v)[1]), 0, 1)))
        if abs(actual-measured) > 2: raise ValueError('Joined orientation disagrees with measured angle: '+name)
    return frames, residuals

def world(frames, plane, uv):
    if plane not in frames: raise ValueError('Unknown panel in camera observations')
    origin, u, v = frames[plane]
    return origin+uv[0]*u+uv[1]*v

def camera(observations, frames, intrinsics, width, height):
    xyz = np.array([world(frames, o['plane_id'], o['uv_cm']) for o in observations], float)
    pixels = np.array([o['pixel'] for o in observations], float)
    train = np.array([o['role']=='fit' for o in observations])
    if train.sum() < 6 or (~train).sum() < 2: raise ValueError('Camera needs 6 fit points and 2 independent check points')
    if len(np.unique(xyz, axis=0)) != len(xyz): raise ValueError('Camera control points must be distinct')
    singular = np.linalg.svd(xyz[train]-xyz[train].mean(axis=0), compute_uv=False)
    if singular[-1] < 1 or singular[-1]/singular[0] < .01:
        raise ValueError('Camera fit needs well-spread noncoplanar points across folded panels')
    if (pixels < 0).any() or (pixels[:,0] >= width).any() or (pixels[:,1] >= height).any():
        raise ValueError('Camera observation outside analysis image')
    k = np.array([[intrinsics['fx'],0,intrinsics['cx']],[0,intrinsics['fy'],intrinsics['cy']],[0,0,1.]], float)
    distortion = np.array(intrinsics['distortion'], float)
    ok, r, t = cv2.solvePnP(xyz[train], pixels[train], k, distortion, flags=cv2.SOLVEPNP_SQPNP)
    if not ok: raise ValueError('Camera pose solve failed')
    r, t = cv2.solvePnPRefineLM(xyz[train], pixels[train], k, distortion, r, t)
    R = cv2.Rodrigues(r)[0]; t = t.ravel()
    if ((xyz@R.T+t)[:,2] <= 0).any(): raise ValueError('Control points lie behind camera')
    projected = cv2.projectPoints(xyz,r,t,k,distortion)[0][:,0]
    errors = np.linalg.norm(projected-pixels,axis=1)
    rmse = float(np.sqrt(np.mean(errors[train]**2)))
    maximum = float(errors[~train].max())
    if rmse > FIT_RMSE_PX or maximum > CHECK_MAX_PX: raise ValueError('Camera reprojection exceeds fixed fit/check thresholds')
    return dict(R=R.tolist(), t_cm=t.tolist(), center_cm=(-R.T@t).tolist(),
                fit_rmse_px=rmse, check_max_px=maximum,
                observations=[dict(pixel=o['pixel'], projected_px=p.tolist(), error_px=float(e), role=o['role'])
                              for o,p,e in zip(observations,projected,errors)])

def align(review, calibration, summary, contacts, pose, identity, alignment):
    # Local coordinates must lie on the reviewed panel polygons, including seams.
    planes = {p['id']:p for p in calibration['review']['planes']}
    def on_panel(name, uv):
        if name not in planes: raise ValueError('Unknown panel')
        inv = np.linalg.inv(np.array(calibration['calibrated']['plane_homographies'][name]))
        pixel = inv @ [*uv,1.]
        if abs(pixel[2]) < 1e-9: raise ValueError('Invalid panel point')
        pixel = pixel[:2]/pixel[2]
        polygon = np.array(planes[name]['polygon'],np.float32)
        if cv2.pointPolygonTest(polygon,tuple(map(float,pixel)),True) < -2:
            raise ValueError('Seam/control point lies outside reviewed panel')
    for join in review['joins']:
        for name,key in [(join['parent'],'parent_edge_cm'),(join['child'],'child_edge_cm')]:
            for uv in join[key]: on_panel(name,uv)
    for cam in review['cameras']:
        for obs in cam['observations']: on_panel(obs['plane_id'],obs['uv_cm'])
    frames, seams = assemble(review, calibration)
    count, width, height = summary['frame_count'], summary['width'], summary['height']
    intrinsics = review['intrinsics']
    if (intrinsics['width'],intrinsics['height']) != (width,height):
        raise ValueError('Intrinsics must match the resized/cropped analysis image exactly')
    if intrinsics['cx'] >= width or intrinsics['cy'] >= height: raise ValueError('Principal point outside image')
    if not calibration['review']['identity_confirmed']: raise ValueError('Confirm climber identity in calibration first')
    cameras = {}
    for entry in review['cameras']:
        if entry['frame'] >= count: raise ValueError('Camera frame outside video')
        cameras[entry['frame']] = camera(entry['observations'],frames,intrinsics,width,height)
    reference = summary['reference_frame']
    if reference not in cameras: raise ValueError('Camera observations are required at the wall reference frame')
    if review['fixed_camera_confirmed'] and len(cameras) != 1:
        raise ValueError('Fixed camera mode uses the reference camera only')
    points, scores = pose['keypoints'], pose['scores']
    if points.shape != (count,133,2) or scores.shape != (count,133) or identity['observed'].shape != (count,):
        raise ValueError('Pose/identity timeline or keypoint schema mismatch')
    indices = {int(frame):i for i,frame in enumerate(alignment['frames'])}
    if len(indices) != len(alignment['frames']): raise ValueError('Duplicate tracking frame')
    if reference not in indices: raise ValueError('Missing reference tracking')
    reference_H = alignment['matrices'][indices[reference]]
    controls = np.array([o['pixel'] for o in review['cameras'][0]['observations']],float)
    frame_cameras, invalid = {}, []
    for frame in range(count):
        if frame in cameras:
            frame_cameras[frame] = cameras[frame]
        elif review['fixed_camera_confirmed']:
            i = indices.get(frame)
            if i is not None and str(alignment['statuses'][i]) == 'ok':
                H = alignment['matrices'][i] @ np.linalg.inv(reference_H)
                transformed = cv2.perspectiveTransform(controls[None],H)[0]
                if np.isfinite(transformed).all() and np.max(np.linalg.norm(transformed-controls,axis=1)) <= TRACK_MAX_PX:
                    frame_cameras[frame] = cameras[reference]
        if frame not in frame_cameras: invalid.append(frame)
    K = np.array([[intrinsics['fx'],0,intrinsics['cx']],[0,intrinsics['fy'],intrinsics['cy']],[0,0,1.]],float)
    distortion = np.array(intrinsics['distortion'],float)
    holds = []
    for h in calibration['calibrated']['holds']:
        xyz = None
        if h['status']=='plane_local_only':
            # Undistort the measured pixel, then intersect its ray with the assigned
            # world plane. Do not treat a distorted-image homography as metric 3D.
            cam = cameras[reference]
            xy = cv2.undistortPoints(np.array(h['center_px'],float).reshape(1,1,2),K,distortion)[0,0]
            ray = np.r_[xy,1.] @ np.array(cam['R'])
            origin = np.array(cam['center_cm'])
            plane_origin,u,v = frames[h['plane_id']]
            normal = np.cross(u,v)
            denominator = ray@normal
            if abs(denominator)<1e-8: raise ValueError('Hold ray parallel to wall')
            distance = ((plane_origin-origin)@normal)/denominator
            if distance<=0: raise ValueError('Hold lies behind camera')
            point = origin+distance*ray
            on_panel(h['plane_id'],[(point-plane_origin)@u,(point-plane_origin)@v])
            xyz = point.tolist()
        holds.append(dict(hold_id=h['hold_id'], xyz_cm=xyz, plane_id=h['plane_id'],
                          status='wall_surface_anchor' if xyz else 'unassigned_or_ambiguous'))
    lookup = {h['hold_id']:h for h in holds}
    if any(row['state']=='hold' and (row['hold_id'] not in lookup or lookup[row['hold_id']]['xyz_cm'] is None)
           for row in contacts['frames']):
        raise ValueError('Reviewed contacts reference unselected or ambiguously assigned holds')
    # 2D observations determine world rays, NOT depth or actual joint positions.
    rays = []
    for frame in range(count):
        cam = frame_cameras.get(frame)
        directions = [None]*133
        if cam and bool(identity['observed'][frame]):
            valid = np.isfinite(points[frame]).all(axis=1) & np.isfinite(scores[frame]) & (scores[frame] >= .3)
            valid &= (points[frame,:,0] >= 0) & (points[frame,:,0] < width) & (points[frame,:,1] >= 0) & (points[frame,:,1] < height)
            if valid.any():
                xy = cv2.undistortPoints(points[frame,valid,None,:].astype(float),K,distortion)[:,0]
                vectors = np.c_[xy,np.ones(len(xy))] @ np.array(cam['R'])
                vectors /= np.linalg.norm(vectors,axis=1)[:,None]
                for index, vector in zip(np.flatnonzero(valid),vectors): directions[int(index)] = vector.tolist()
        rays.append(dict(frame=frame, origin_cm=cam['center_cm'] if cam else None,
                         directions=directions, scores=[float(s) if np.isfinite(s) else None for s in scores[frame]], joint_xyz_cm=None,
                         status='depth_unresolved' if any(d is not None for d in directions) else 'unobserved_or_camera_unavailable'))
    contact_rows = []
    for row in contacts['frames']:
        target = lookup[row['hold_id']]['xyz_cm'] if row['state']=='hold' else None
        contact_rows.append(dict(**row, target_xyz_cm=target,
            target_kind='reviewed_wall_surface_anchor' if target else None,
            camera_aligned=row['frame'] in frame_cameras))
    return dict(coordinate_system='right-handed centimeters, Y up; root origin/axes supplied by reviewer',
        panels={key:dict(origin_cm=o.tolist(),u_axis=u.tolist(),v_axis=v.tolist()) for key,(o,u,v) in frames.items()},
        seams=seams, cameras={str(k):v for k,v in cameras.items()},
        frame_camera_index={str(f):f if f in cameras else reference for f in frame_cameras},
        holds=holds, pose_rays=rays, contacts=contact_rows,
        summary=dict(panel_count=len(frames),hold_count=len(holds),camera_aligned_frames=len(frame_cameras),
            frame_count=count,missing_camera_frames=invalid,pose_depth_reconstructed=False,
            wall_coordinates_assembled=True, camera_timeline_aligned=len(frame_cameras)==count,
            pose_score_threshold=.3, generation_ready=False),
        warnings=['Pose rays retain unknown depth; no 3D skeleton is reconstructed.',
                  'Hold positions are wall-surface anchors, not measured hold protrusion or joint centers.',
                  'Fixed-camera reuse is user-confirmed and gated by image tracking; moving-camera frames need explicit controls.',
                  'Camera residuals test supplied measurements, not independent physical accuracy.'])
