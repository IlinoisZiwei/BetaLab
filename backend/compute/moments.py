"""Turn measured model gaps and missing support evidence into review moments.

Frame/limb conventions follow CIS5810 Beta_Translator trials.py and body_regions.py
@ ff85726da2fbbd2616c409b01d6c03833ab62ce9. No technique is inferred here.
"""
import math
LIMBS=('left_hand','right_hand','left_foot','right_foot')

def runs(mask):
    start=None
    for frame,active in enumerate([*mask,False]):
        if active and start is None:
            start=frame
        elif not active and start is not None:
            yield start,frame-1
            start=None

def build_moments(known,trusted,gaps=None,fps=30):
    moments=[]
    for limb,name in enumerate(LIMBS):
        for first,last in runs([bool(k[limb] and not t[limb]) for k,t in zip(known,trusted)]):
            moments.append(dict(id=f'uncertain-{name}-{first}',kind='unconfirmed_contact',frame=first,end_frame=last,
                at_seconds=first/fps,limb=name,title='Insufficient contact evidence',
                explanation='This contact candidate has no supporting evidence. Check it against the recording; no technique advice is given.',media='video',gap_cm=None))
    if gaps is not None:
        candidates=[]
        for limb,name in enumerate(LIMBS):
            mask=[bool(t[limb] and math.isfinite(g[limb]) and g[limb]>5) for t,g in zip(trusted,gaps)]
            for first,last in runs(mask):
                peak=max(range(first,last+1),key=lambda f:gaps[f][limb])
                candidates.append(dict(id=f'gap-{name}-{first}',kind='contact_gap',frame=peak,end_frame=last,
                    at_seconds=peak/fps,limb=name,title='Skeleton contact offset',gap_cm=float(gaps[peak][limb]),media='video',
                    explanation=f'The model contact point is {gaps[peak][limb]:.1f} cm from the candidate hold. This is a model diagnostic, not an assessment of the actual climb.'))
        moments += sorted(candidates,key=lambda m:m['gap_cm'],reverse=True)[:8]
    return sorted(moments,key=lambda m:(m['frame'],m['limb']))
