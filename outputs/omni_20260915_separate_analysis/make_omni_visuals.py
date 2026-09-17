import csv, math, sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

FILES=[Path(r'C:\Users\user\Documents\OmniCsvLogs\omni_20260915_140714_643.csv'),Path(r'C:\Users\user\Documents\OmniCsvLogs\omni_20260915_140748_147.csv'),Path(r'C:\Users\user\Documents\OmniCsvLogs\omni_20260915_142051_796.csv')]
OUT=Path(r'C:\Users\user\Desktop\G1_Teleop_Project\outputs\omni_20260915_separate_analysis')

def load(path):
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(line for line in f if not line.startswith('#')))
    ns=np.array([int(r['receive_monotonic_ns']) for r in rows],dtype=np.int64)
    t=(ns-ns[0])/1e9
    x=np.array([float(r['movement_x']) for r in rows])
    y=np.array([float(r['movement_y']) for r in rows])
    yaw=np.array([float(r['arm_yaw_deg']) for r in rows])
    # Robust initial heading: median of first 1 s, resisting individual noisy samples.
    init=float(np.median(yaw[t<=min(1.0,t[-1])]))
    dt=np.diff(t,prepend=t[0]); dt=np.clip(dt,0,0.25)
    def rotate(x,y,deg):
        a=np.deg2rad(deg); c=np.cos(a); s=np.sin(a)
        return c*x-s*y, s*x+c*y
    # movementXY already carries movement-plane direction; armYaw is not applied again.
    # Initial yaw correction changes heading display only.
    vx_raw,vy_raw=x.copy(),y.copy()
    vx_cor,vy_cor=x.copy(),y.copy()
    px_raw=np.cumsum(vx_raw*dt); py_raw=np.cumsum(vy_raw*dt)
    px_cor=np.cumsum(vx_cor*dt); py_cor=np.cumsum(vy_cor*dt)
    return dict(t=t,x=x,y=y,yaw=yaw,init=init,vxr=vx_raw,vyr=vy_raw,vxc=vx_cor,vyc=vy_cor,pxr=px_raw,pyr=py_raw,pxc=px_cor,pyc=py_cor)

def limits(a,b,pad=.12):
    lo=min(float(np.min(a)),float(np.min(b))); hi=max(float(np.max(a)),float(np.max(b)))
    span=max(hi-lo,0.2); return lo-pad*span,hi+pad*span

def make(path):
    d=load(path); t=d['t']; duration=float(t[-1]); nframes=min(360,max(90,int(duration*10)))
    frame_t=np.linspace(0,duration,nframes); idx=np.searchsorted(t,frame_t,side='right')-1; idx=np.clip(idx,0,len(t)-1)
    stem=path.stem
    # Static overview
    fig,ax=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    fig.suptitle(f'{stem} — separate Omni movement analysis',fontsize=15,fontweight='bold')
    ax[0,0].plot(t,d['x'],label='movement_x (right +)',lw=1); ax[0,0].plot(t,d['y'],label='movement_y (forward +)',lw=1)
    ax[0,0].set(xlabel='elapsed time (s)',ylabel='normalized input',title='Local movement channels'); ax[0,0].legend(); ax[0,0].grid(alpha=.25)
    ax[0,1].plot(t,d['yaw'],color='#7b2cbf',lw=1); ax[0,1].axhline(d['init'],ls='--',color='gray',label=f'initial median {d["init"]:.1f}°')
    ax[0,1].set(xlabel='elapsed time (s)',ylabel='yaw (deg)',title='Reported Omni yaw'); ax[0,1].legend(); ax[0,1].grid(alpha=.25)
    ax[1,0].plot(d['pxr'],d['pyr'],color='#d95f02'); ax[1,0].scatter([0],[0],c='green',label='start'); ax[1,0].scatter([d['pxr'][-1]],[d['pyr'][-1]],c='red',label='end')
    ax[1,0].set(xlabel='integrated X (normalized·s)',ylabel='integrated Y (normalized·s)',title='Integrated movement_x/y trace (forward is down)'); ax[1,0].axis('equal'); ax[1,0].invert_yaxis(); ax[1,0].legend(); ax[1,0].grid(alpha=.25)
    ax[1,1].plot(d['pxc'],d['pyc'],color='#1b9e77'); ax[1,1].scatter([0],[0],c='green',label='start'); ax[1,1].scatter([d['pxc'][-1]],[d['pyc'][-1]],c='red',label='end')
    ax[1,1].set(xlabel='integrated X (normalized·s)',ylabel='integrated Y (normalized·s)',title=f'Yaw baseline corrected ({d["init"]:.1f}° → 0°); same movement trace'); ax[1,1].axis('equal'); ax[1,1].invert_yaxis(); ax[1,1].legend(); ax[1,1].grid(alpha=.25)
    png=OUT/f'{stem}_analysis.png'; fig.savefig(png,dpi=160); plt.close(fig)
    # Animated 4-panel view
    fig,ax=plt.subplots(2,2,figsize=(12,9),constrained_layout=True)
    fig.suptitle(f'{stem} | Omni movement over time',fontsize=14,fontweight='bold')
    for a in ax.flat:a.grid(alpha=.25)
    ax[0,0].invert_yaxis(); ax[0,1].invert_yaxis()
    for a,title in [(ax[0,0],'Instant movement vector — local X/Y'),(ax[0,1],f'Instant vector — yaw corrected ({d["init"]:.1f}° → 0°)')]:
        a.set_xlim(-1.05,1.05); a.set_ylim(-1.05,1.05); a.set_aspect('equal'); a.set_xlabel('right +'); a.set_ylabel('forward +'); a.set_title(title)
    q0=ax[0,0].quiver([0],[0],[0],[0],angles='xy',scale_units='xy',scale=1,color='#377eb8',width=.018)
    q1=ax[0,1].quiver([0],[0],[0],[0],angles='xy',scale_units='xy',scale=1,color='#984ea3',width=.018)
    xr=limits(d['pxr'],np.array([0.])); yr=limits(d['pyr'],np.array([0.])); xc=limits(d['pxc'],np.array([0.])); yc=limits(d['pyc'],np.array([0.]))
    ax[1,0].set(xlim=xr,ylim=yr,xlabel='integrated X',ylabel='integrated Y',title='Accumulated movement_x/y (forward is down)'); ax[1,0].set_aspect('equal',adjustable='box'); ax[1,0].invert_yaxis()
    ax[1,1].set(xlim=xc,ylim=yc,xlabel='integrated X',ylabel='integrated Y',title='Yaw-zero display; movement is not rotated twice'); ax[1,1].set_aspect('equal',adjustable='box'); ax[1,1].invert_yaxis()
    l0,=ax[1,0].plot([],[],color='#d95f02',lw=2); p0,=ax[1,0].plot([],[],'o',color='red'); l1,=ax[1,1].plot([],[],color='#1b9e77',lw=2); p1,=ax[1,1].plot([],[],'o',color='red')
    txt=fig.text(.5,.01,'',ha='center',fontsize=11)
    def update(k):
        i=int(idx[k]); q0.set_UVC([d['x'][i]],[d['y'][i]]); q1.set_UVC([d['x'][i]],[d['y'][i]])
        l0.set_data(d['pxr'][:i+1],d['pyr'][:i+1]); p0.set_data([d['pxr'][i]],[d['pyr'][i]])
        l1.set_data(d['pxc'][:i+1],d['pyc'][:i+1]); p1.set_data([d['pxc'][i]],[d['pyc'][i]])
        txt.set_text(f't={t[i]:.2f}s   local=({d["x"][i]:+.2f}, {d["y"][i]:+.2f})   yaw={d["yaw"][i]:.1f}°   corrected={d["yaw"][i]-d["init"]:+.1f}°')
        return q0,q1,l0,p0,l1,p1,txt
    ani=FuncAnimation(fig,update,frames=nframes,interval=100,blit=False)
    gif=OUT/f'{stem}_movement.gif'; ani.save(gif,writer=PillowWriter(fps=10),dpi=90); plt.close(fig)
    dist_raw=float(np.sum(np.hypot(d['vxr'],d['vyr'])*np.diff(t,prepend=t[0])))
    return dict(file=path.name,samples=len(t),duration_s=duration,initial_yaw_deg=d['init'],end_corrected=[float(d['pxc'][-1]),float(d['pyc'][-1])],integrated_distance=dist_raw,png=str(png),gif=str(gif))

for f in FILES: print(make(f))

