"""Reference-wall skeleton above the original recording, preserving native timing.

Projection/body conventions reference CIS5810 Beta_Translator trial2_scene3d.py
and body_legs.py @ ff85726da2fbbd2616c409b01d6c03833ab62ce9.
OpenCV rendering and H.264 export here are BetaLab integration code.
"""
import json
import subprocess
import cv2
import numpy as np

def focus_transform(joints_px, holds):
    """One stable, aspect-preserving view containing the whole motion and used holds."""
    points = np.asarray(joints_px).reshape(-1, 2)
    if holds:
        points = np.concatenate([points, np.asarray([h['center_px'] for h in holds])])
    points = points[np.isfinite(points).all(axis=1)]
    if not len(points):
        return np.zeros(2), .5
    low, high = points.min(axis=0), points.max(axis=0)
    size = np.maximum(high - low, 100) * 1.24
    scale = min(960 / size[0], 540 / size[1])
    origin = (low + high) / 2 - np.array([960, 540]) / (2 * scale)
    return origin, scale


def render(video, joints, scene, holds, labels, trusted, destination, title, progress, geometry_failed=False):
    camera=scene['camera']
    xyz=joints.reshape(-1,3)
    uvw=(xyz@np.asarray(camera['R']).T+np.asarray(camera['t_cm']))@np.asarray(camera['K']).T
    uv=(uvw[:,:2]/uvw[:,2,None]).reshape(joints.shape[:-1]+(2,))
    # Only the skeleton view is focused; the original keeps its complete frame.
    # Display only holds with supported wall contact; this does not change evidence.
    visited = {str(label) for label in labels[trusted]}
    holds = [hold for hold in holds if hold["id"] in visited]
    origin, scale = focus_transform(uv, holds)
    def project(points):
        return np.clip(np.nan_to_num((np.asarray(points) - origin) * scale), -10000, 10000).astype(np.int32)
    uv = project(uv)
    base=np.full((540,960,3),245,np.uint8)
    for polygon in scene['assumptions']['wall_polygons_px'].values():
        cv2.polylines(base,[project(polygon)],True,(200,200,200),1)
    for hold in holds:
        x,y=project(hold['center_px'])
        cv2.circle(base,(x,y),3,(165,175,185),-1)
    source=cv2.VideoCapture(str(video))
    raw=destination.with_suffix('.raw.mp4')
    writer=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*'mp4v'),30,(960,1180))
    if not source.isOpened() or not writer.isOpened():
        raise RuntimeError('Video decoder/encoder unavailable')
    try:
        for frame in range(len(joints)):
            ok,original=source.read()
            if not ok:
                raise ValueError('Original video ended before the native skeleton time axis')
            pane=base.copy()
            active=set(str(x) for x in labels[frame][trusted[frame]])
            for hold in holds:
                if hold['id'] in active:
                    cv2.circle(pane,tuple(project(hold['center_px'])),5,(40,140,240),-1)
            points=uv[frame].astype(int)
            for limb in range(4):
                color=(40,130,20) if trusted[frame,limb] else (140,120,100)
                cv2.polylines(pane,[points[limb]],False,color,3,cv2.LINE_AA)
                for point in points[limb]:
                    cv2.circle(pane,tuple(point),3,color,-1)
            torso=np.array([points[0,0],points[1,0],points[3,0],points[2,0]])
            cv2.polylines(pane,[torso],True,(60,100,180),2,cv2.LINE_AA)
            image=np.full((1180,960,3),255,np.uint8)
            # Letterbox portrait recordings rather than stretch or crop them.
            h, w = original.shape[:2]
            ratio = min(960 / w, 540 / h)
            width, height = round(w * ratio), round(h * ratio)
            x, y = (960 - width) // 2, 610 + (540 - height) // 2
            image[610:1150] = 24
            image[y:y+height, x:x+width] = cv2.resize(original, (width, height))
            image[35:575]=pane
            cv2.putText(image,'Original recording',(10,600),cv2.FONT_HERSHEY_SIMPLEX,.55,(30,30,30),1,cv2.LINE_AA)
            cv2.putText(image,title,(10,24),cv2.FONT_HERSHEY_SIMPLEX,.45,(30,30,30),1,cv2.LINE_AA)
            cv2.putText(image,f'{frame/30:.2f}s | '+('GEOMETRY CHECK FAILED - diagnostic preview only' if geometry_failed else 'WALL-ONLY PREVIEW - ground and mechanics not checked'),
                        (10,1174),cv2.FONT_HERSHEY_SIMPLEX,.5,(40,40,140),1,cv2.LINE_AA)
            writer.write(image)
            if frame==0:
                cv2.imwrite(str(destination.with_suffix('.png')),image)
            if (frame+1)%200==0:
                progress('rendering',f'{frame+1}/{len(joints)} frames')
    finally:
        source.release()
        writer.release()
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(raw),'-an','-c:v','libx264',
                    '-pix_fmt','yuv420p','-movflags','+faststart',str(destination)],check=True)
    raw.unlink()
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-count_frames','-show_entries','stream=codec_name,pix_fmt,nb_read_frames,avg_frame_rate:format=duration',
        '-of','json',str(destination)],text=True))
    stream=probe['streams'][0]
    if stream['codec_name']!='h264' or stream['pix_fmt']!='yuv420p' or int(stream['nb_read_frames'])!=len(joints):
        raise ValueError('Encoded video validation failed')
    return probe
