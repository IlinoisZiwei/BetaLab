"""Known synthetic folded wall/camera; never use these numbers on real footage."""
def fixture():
    import cv2
    import numpy as np
    from types import SimpleNamespace
    from backend.compute.input_calibration import transform_points
    L = 100.1
    u = np.array([2**-.5,0,2**-.5])
    def xyz(panel, uv):
        return np.array([uv[0],-uv[1],0.]) if panel=='a' else np.array([L,0,0])+uv[0]*u+[0,-uv[1],0]
    K = np.array([[600.,0,360],[0,600,240],[0,0,1]])
    R = np.diag([1.,-1,-1]); center = np.array([80.,-50,400])
    r = cv2.Rodrigues(R)[0]; t = -R@center
    def project(points, offset=0):
        return cv2.projectPoints(np.array(points,float),r,t-np.array([offset,0,0]),K,None)[0][:,0]
    corners = [[0,0],[L,0],[L,L],[0,L]]
    planes = [dict(id=name,polygon=project([xyz(name,p) for p in corners]).tolist(),
        grid_corners=project([xyz(name,p) for p in corners]).tolist(),horizontal_steps=7,vertical_steps=7,
        angle_from_horizontal_deg=90.,note='SYNTHETIC: known test geometry') for name in ['a','b']]
    calibration = dict(review=dict(reference_frame=0,selected_hold_ids=['H1','H2'],
        identity_confirmed=True,contact_reviewed=False,grid_spacing_cm=14.3,planes=planes,notes='SYNTHETIC'))
    summary = dict(frame_count=4,fps=2,reference_frame=0,width=720,height=480,hold_count=2,contact_rows=16,seconds=0)
    holds = [dict(hold_id='H'+str(i+1),cx_px=float(p[0]),cy_px=float(p[1])) for i,p in
        enumerate(project([xyz('a',[40,50]),xyz('b',[50,50])]))]
    c = calibration['review']
    calibration['calibrated'] = transform_points(SimpleNamespace(**{**c,'planes':[SimpleNamespace(**p) for p in planes]}),summary,holds)
    controls = [('a',[10,10]),('a',[90,10]),('a',[10,90]),('b',[10,10]),('b',[90,10]),('b',[90,90]),
                ('a',[50,70]),('b',[50,70])]
    observations = [dict(plane_id=n,uv_cm=p,pixel=px.tolist(),role='fit' if i<6 else 'check')
                    for i,((n,p),px) in enumerate(zip(controls,project([xyz(n,p) for n,p in controls])))]
    review = dict(base_version=None,calibration_version='a'*64,contact_version='b'*64,
        root=dict(plane_id='a',origin_cm=[0,0,0],u_axis=[1,0,0],v_axis=[0,-1,0]),
        joins=[dict(parent='a',child='b',parent_edge_cm=[[L,0],[L,L]],child_edge_cm=[[0,0],[0,L]],fold_deg=45)],
        intrinsics=dict(fx=600,fy=600,cx=360,cy=240,width=720,height=480,distortion=[0]*5,provenance='SYNTHETIC known pinhole'),
        cameras=[dict(frame=0,observations=observations)],fixed_camera_confirmed=True,
        measurements_confirmed=True,notes='SYNTHETIC acceptance only')
    point = np.array([40.,-50,20])
    pose = dict(keypoints=np.tile(project([point]),(4,133,1)),scores=np.ones((4,133)))
    identity = dict(observed=np.array([True,True,False,True]))
    alignment = dict(frames=np.arange(4),matrices=np.tile(np.eye(3),(4,1,1)),statuses=np.array(['ok']*4))
    contacts = dict(frames=[dict(frame=f,time_sec=f/2,limb=limb,state='hold' if limb=='left_hand' else 'unknown',
        hold_id='H1' if limb=='left_hand' else None,source_frame=f*2,source_time_sec=f/2)
        for limb in ['left_hand','right_hand','left_foot','right_foot'] for f in range(4)])
    return dict(review=review,calibration=calibration,summary=summary,holds=holds,contacts=contacts,
                pose=pose,identity=identity,alignment=alignment,point=point,center=center,xyz=xyz,project=project)

if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    import cv2
    import numpy as np
    out = Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    d = fixture()
    for key in ('review','summary','holds'):
        (out/(key+'.json')).write_text(json.dumps(d[key]))
    (out/'calibration.json').write_text(json.dumps(d['calibration']['review']))
    for key in ('pose','identity','alignment'):
        np.savez_compressed(out/(key+'.npz'),**d[key])
    (out/'contacts.csv').write_text('frame,time_sec,limb,hold_id\n0,0,left_hand,H1\n')
    (out/'contact_events.csv').write_text('limb,hold_id,start_frame,end_frame\nleft_hand,H1,0,3\n')
    (out/'frame_map.csv').write_text('frame,source_frame,source_time_sec\n'+''.join(f'{i},{i*2},{i/2}\n' for i in range(4)))
    image = np.full((480,720,3),235,np.uint8)
    cv2.putText(image,'SYNTHETIC GEOMETRY TEST',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,0),2)
    for plane in d['calibration']['review']['planes']:
        cv2.polylines(image,[np.round(plane['polygon']).astype(np.int32)],True,(120,80,30),2)
    cv2.imwrite(str(out/'reference.jpg'),image)
