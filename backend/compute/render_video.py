"""Original recording beside a reference-wall skeleton, preserving native timing.

Projection/body conventions reference CIS5810 Beta_Translator trial2_scene3d.py
and body_legs.py @ ff85726da2fbbd2616c409b01d6c03833ab62ce9.
OpenCV rendering and H.264 export here are BetaLab integration code.
"""
import json
import subprocess
import cv2
import numpy as np

def render(video, joints, scene, holds, labels, trusted, destination, title, progress, geometry_failed=False):
    camera=scene['camera']
    xyz=joints.reshape(-1,3)
    uvw=(xyz@np.asarray(camera['R']).T+np.asarray(camera['t_cm']))@np.asarray(camera['K']).T
    uv=(uvw[:,:2]/uvw[:,2,None]).reshape(joints.shape[:-1]+(2,))
    # Each pane maps the original 1920x1080/reference image to 480x270.
    uv=np.clip(np.nan_to_num(uv),-10000,10000)*.25
    base=np.full((270,480,3),245,np.uint8)
    for polygon in scene['assumptions']['wall_polygons_px'].values():
        cv2.polylines(base,[(np.asarray(polygon,dtype=float)*.25).astype(np.int32)],True,(200,200,200),1)
    for hold in holds:
        x,y=(np.asarray(hold['center_px'])*.25).astype(int)
        cv2.circle(base,(x,y),3,(165,175,185),-1)
    source=cv2.VideoCapture(str(video))
    raw=destination.with_suffix('.raw.mp4')
    writer=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*'mp4v'),30,(960,350))
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
                    cv2.circle(pane,tuple((np.asarray(hold['center_px'])*.25).astype(int)),5,(40,140,240),-1)
            points=uv[frame].astype(int)
            for limb in range(4):
                color=(40,130,20) if trusted[frame,limb] else (140,120,100)
                cv2.polylines(pane,[points[limb]],False,color,3,cv2.LINE_AA)
                for point in points[limb]:
                    cv2.circle(pane,tuple(point),3,color,-1)
            torso=np.array([points[0,0],points[1,0],points[3,0],points[2,0]])
            cv2.polylines(pane,[torso],True,(60,100,180),2,cv2.LINE_AA)
            image=np.full((350,960,3),255,np.uint8)
            image[35:305,:480]=cv2.resize(original,(480,270))
            image[35:305,480:]=pane
            cv2.putText(image,'Original recording',(10,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(30,30,30),1,cv2.LINE_AA)
            cv2.putText(image,title,(490,24),cv2.FONT_HERSHEY_SIMPLEX,.45,(30,30,30),1,cv2.LINE_AA)
            cv2.putText(image,f'{frame/30:.2f}s | '+('GEOMETRY CHECK FAILED - diagnostic preview only' if geometry_failed else 'WALL-ONLY PREVIEW - ground and mechanics not checked'),
                        (10,330),cv2.FONT_HERSHEY_SIMPLEX,.5,(40,40,140),1,cv2.LINE_AA)
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
