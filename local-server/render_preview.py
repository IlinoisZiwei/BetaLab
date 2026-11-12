"""Shared app rendering: reconstructed route holds and active contact targets."""
import json,subprocess
from pathlib import Path
import numpy as np,cv2
from beta_translator.body_render import setup_axis,draw_frame,plot_xyz
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def render(fit,scene,holds,destination):
    destination=Path(destination)
    fig=plt.figure(figsize=(6,7),dpi=100,facecolor='#f2f8fd');ax=fig.add_subplot(111,projection='3d')
    artists=setup_axis(ax,scene,fit['joints']);ax.set_axis_off();fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
    patches=[]
    for hold in holds:
        poly=Poly3DCollection([np.stack(plot_xyz(hold['polygon']),axis=-1)],facecolors='#a9cce1',edgecolors='#5785a3',linewidths=1,alpha=.9)
        ax.add_collection3d(poly);patches.append((hold,poly))
    raw=destination.with_suffix('.raw.mp4');writer=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*'mp4v'),30,(600,700))
    if not writer.isOpened():raise RuntimeError('Video encoder unavailable')
    try:
        for i in range(len(fit['frames'])):
            draw_frame(artists,fit,i)
            active=set(str(x) for x in fit['labels'][i][fit['known'][i]])
            for hold,poly in patches:
                poly.set_facecolor('#efaa66' if hold['id'] in active else '#a9cce1')
                poly.set_edgecolor('#b76d32' if hold['id'] in active else '#5785a3')
            fig.canvas.draw();writer.write(cv2.cvtColor(np.asarray(fig.canvas.buffer_rgba()),cv2.COLOR_RGBA2BGR))
            if i==0:fig.savefig(destination.with_suffix('.png'),dpi=100)
    finally:writer.release();plt.close(fig)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(raw),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(destination)],check=True)
    raw.unlink()
