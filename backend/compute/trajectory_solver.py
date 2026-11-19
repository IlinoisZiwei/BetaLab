"""Block-tridiagonal damped Gauss–Newton for a fixed native-frame trajectory.

New BetaLab numerical adapter. The caller supplies the CIS5810 Beta Translator
kinematics and bounds; no mechanics or technique feasibility is inferred here.
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

def solve(local,initial,lo,hi,step,progress,iterations=100):
    q=initial.copy();n,width=q.shape;damping=.1;rate_weight=100.
    rows=np.repeat(np.arange(n*width),width)
    cols=(np.arange(n)[:,None,None]*width+np.arange(width)[None,None,:]+np.zeros((n,width,1),int)).ravel()
    left=np.arange((n-1)*width);right=left+width
    def terms(x):
        residual=local(x);delta=np.diff(x,axis=0)/step
        smooth=.1*delta;excess=np.maximum(np.abs(delta)-1,0)*rate_weight
        return residual,delta,float((np.sum(residual**2)+np.sum(smooth**2)+np.sum(excess**2))/2)
    residual,delta,cost=terms(q);history=[cost]
    accepted=0
    for iteration in range(iterations):
        jac=np.empty((*residual.shape,width))
        for j in range(width):
            perturbed=q.astype(complex);perturbed[:,j]+=1e-25j
            jac[:,:,j]=local(perturbed).imag/1e-25
        gradient=np.einsum('nri,nr->ni',jac,residual)
        diagonal=np.einsum('nri,nrj->nij',jac,jac)
        active=np.abs(delta)>1
        coupling=(.01+rate_weight**2*active)/step**2
        edge_gradient=(.01*delta+rate_weight**2*np.sign(delta)*np.maximum(np.abs(delta)-1,0))/step
        gradient[:-1]-=edge_gradient;gradient[1:]+=edge_gradient
        ids=np.arange(width)
        diagonal[:-1,ids,ids]+=coupling;diagonal[1:,ids,ids]+=coupling
        success=False
        for _ in range(8):
            block=diagonal.copy();block[:,ids,ids]+=damping/step**2
            matrix=coo_matrix((np.r_[block.ravel(),-coupling.ravel(),-coupling.ravel()],
                (np.r_[rows,left,right],np.r_[cols,right,left])),shape=(n*width,n*width)).tocsc()
            direction=spsolve(matrix,-gradient.ravel(),permc_spec='NATURAL').reshape(q.shape)
            candidate=np.clip(q+direction,lo,hi)
            new_residual,new_delta,new_cost=terms(candidate)
            if np.isfinite(new_cost) and new_cost<cost:
                q=candidate;residual,delta,cost=new_residual,new_delta,new_cost
                history.append(cost);accepted+=1;damping=max(damping/3,1e-7);success=True;break
            damping*=10
        if (iteration+1)%10==0:progress('source_skeleton',f'Temporal refinement {iteration+1}/{iterations}, cost {cost:.2f}')
        if not success:break
        if len(history)>1 and (history[-2]-cost)<1e-7*max(1,cost):break
    return q,dict(method='block_temporal_gauss_newton',iterations=iteration+1,accepted_steps=accepted,
        initial_cost=history[0],final_cost=cost,cost_history=history,
        success=bool(iteration+1<iterations and success),
        note='Numerical stopping only; independent geometry and hard rate checks remain required.')
