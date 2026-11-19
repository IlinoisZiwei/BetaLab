"""Trial2 user-reported wall angles, isolated from the original experiment.

Adapted from CIS5810 Beta_Translator ff85726da2fbbd2616c409b01d6c03833ab62ce9
trial2_scene3d.Trial2Scene.__init__: rebuild joined planes and floor in the same
camera. Its old middle<=55-degree experiment guard excludes the user's 62-degree
wall, so extend that assembly locally; do not edit the original project.
"""
VERSION='trial2-grid143-v2'
UPPER_FROM_HORIZONTAL=70.
MIDDLE_FROM_HORIZONTAL=28.


def scene_for(project,middle_deg=None,upper_deg=None):
    import cv2
    import numpy as np
    from beta_translator.trial2_scene3d import Trial2Scene
    middle=90-MIDDLE_FROM_HORIZONTAL if middle_deg is None else float(middle_deg)
    upper=90-UPPER_FROM_HORIZONTAL if upper_deg is None else float(upper_deg)
    if not 0<=upper<=30 or not upper<=middle<85:
        raise ValueError('Review camera/plane geometry for angles outside the supported reconstruction range')
    scene=Trial2Scene(project,middle_deg=upper,upper_deg=upper,spacing_cm=14.3)
    edge=scene.intersect(scene.spec['upper_hinge_px'],0)
    axis=edge[1]-edge[0];axis/=np.linalg.norm(axis)
    scene.normals[1]=cv2.Rodrigues(axis*np.deg2rad(middle-upper))[0]@scene.normals[0]
    scene.origins[1]=edge.mean(0)
    lower=scene.intersect(scene.spec['lower_hinge_px'],1)
    normal=np.cross(lower[1]-lower[0],[0.,1.,0.]);normal/=np.linalg.norm(normal)
    if normal[2]<0:normal=-normal
    scene.normals[2]=normal;scene.origins[2]=lower.mean(0)
    floor=scene.intersect(scene.spec['floor_edge_px'],2)
    scene.floor_edge_disagreement=float(np.ptp(floor[:,1]))
    shift=np.array([0.,floor[:,1].mean(),0.])
    scene.origins-=shift;scene.origins[3]=0
    scene.t+=scene.R@shift;scene.C=-scene.R.T@scene.t
    scene.angles=(middle,upper)
    scene.meshes=[scene.intersect(scene.spec['wall_polygons_px'][name],i) for i,name in enumerate(('upper','middle','lower'))]
    scene.hinges=[scene.intersect(scene.spec['upper_hinge_px'],0),scene.intersect(scene.spec['lower_hinge_px'],1)]
    scene.camera_report.update(middle_deg=middle,upper_deg=upper,t_cm=scene.t.tolist(),camera_center_cm=scene.C.tolist(),
        floor_edge_height_disagreement_cm=scene.floor_edge_disagreement,
        actual_panel_tilts_deg=np.rad2deg(np.arcsin(-scene.normals[:3,1])).tolist(),
        measured_wall_tilt=False,wall_angle_status='User-reported relative to horizontal; measurement accuracy unspecified.')
    scene.spec.update(hole_spacing_cm=14.3,spacing_status='User-confirmed adjacent hole centers',
        angle_definition='Internal angles from vertical; user reported upper70/middle28 from horizontal.',
        angle_source='User report; upper/lower hinge and floor image lines confirmed by user; camera remains assumed',
        boundary_status='user_confirmed_image_lines',lower_panel_status='unknown; vertical proxy is for drawing/coordinate origin only',
        ground_status='unvalidated; must not constrain a certified wall-only fit',all_geometry_measured=False)
    return scene
