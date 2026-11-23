import { useState } from 'react'
type Plane = { id: string; polygon: number[][]; grid_corners: number[][]; horizontal_steps: number | null; vertical_steps: number | null; angle_from_horizontal_deg: number | null; note: string }
type Draft = { selected_hold_ids: string[]; planes: Plane[]; identity_confirmed: boolean; notes: string }
// Edits the same validated review document as the advanced JSON editor.
export function CalibrationGuide({ draft, onChange, image, width, height }: { draft: string; onChange: (value: string) => void; image: string; width: number; height: number }) {
  const [index, setIndex] = useState(0)
  const [mode, setMode] = useState<'polygon' | 'grid_corners'>('polygon')
  let data: Draft
  try { data = JSON.parse(draft); if (!Array.isArray(data.planes)) throw Error() } catch { return <p>Fix the JSON syntax below to use the guided editor.</p> }
  const plane = data.planes[index]
  const change = (patch: Partial<Draft>) => onChange(JSON.stringify({...data,...patch}, null, 2))
  const update = (patch: Partial<Plane>) => change({planes:data.planes.map((p,i) => i===index ? {...p,...patch}:p)})
  return <section aria-label="Guided wall calibration">
    <h4>1. Choose holds and confirm the climber</h4>
    <label>Selected hold IDs (comma separated)<input key={data.selected_hold_ids.join(',')} defaultValue={data.selected_hold_ids.join(', ')} onBlur={e => change({selected_hold_ids:e.target.value.split(',').map(x=>x.trim()).filter(Boolean)})} /></label>
    <label><input type="checkbox" checked={data.identity_confirmed} onChange={e=>change({identity_confirmed:e.target.checked})} />I checked the climber identity in this recording</label>
    <h4>2. Outline each wall panel and its grid</h4>
    <button type="button" onClick={() => {setIndex(data.planes.length);change({planes:[...data.planes,{id:`panel-${crypto.randomUUID()}`,polygon:[],grid_corners:[],horizontal_steps:null,vertical_steps:null,angle_from_horizontal_deg:null,note:''}]})}}>Add wall panel</button>
    {data.planes.length > 0 && <label>Panel<select value={index} onChange={e=>setIndex(Number(e.target.value))}>{data.planes.map((p,i)=><option key={p.id} value={i}>{p.id}</option>)}</select></label>}
    {plane && <>
      <label>Panel name<input value={plane.id} onChange={e=>update({id:e.target.value})}/></label>
      <label>Click to mark<select value={mode} onChange={e=>setMode(e.target.value as typeof mode)}><option value="polygon">Wall boundary (ordered convex polygon)</option><option value="grid_corners">Grid corners: TL → TR → BR → BL on the wall</option></select></label>
      <p>Use the same panel's hole grid. Count intervals, not holes. Unknown angles stay blank. Fold joins and camera calibration remain in the global editor.</p>
      <svg onPointerDown={e => e.stopPropagation()} viewBox={`0 0 ${width} ${height}`} style={{width:'100%',cursor:'crosshair'}} aria-label="Mark wall calibration points" onClick={e=>{
        const box=e.currentTarget.getBoundingClientRect()
        if (mode==='grid_corners' && plane.grid_corners.length>=4) return
        update({[mode]:[...plane[mode],[Math.min(width-1,Math.round((e.clientX-box.left)/box.width*width)),Math.min(height-1,Math.round((e.clientY-box.top)/box.height*height))]]})
      }}><image href={image} width={width} height={height}/><polygon points={plane.polygon.map(p=>p.join(',')).join(' ')} fill="#3498db33" stroke="#3498db" strokeWidth="3"/>{plane[mode].map((p,i)=><g key={i}><circle cx={p[0]} cy={p[1]} r="5" fill="#e85d04"/><text x={p[0]+7} y={p[1]} fill="#fff" fontSize="18">{i+1}</text></g>)}</svg>
      <button type="button" onClick={()=>update({[mode]:plane[mode].slice(0,-1)})}>Undo last point</button>
      <p>{plane.polygon.length} boundary points · {plane.grid_corners.length}/4 grid corners</p>
      {(['horizontal_steps','vertical_steps'] as const).map(key=><label key={key}>{key==='horizontal_steps'?'Horizontal':'Vertical'} grid intervals<input type="number" min="1" max="100" value={plane[key]??''} onChange={e=>update({[key]:e.target.value===''?null:Number(e.target.value)})}/></label>)}
      <label>Angle from horizontal (degrees; blank if unknown)<input type="number" min="0" max="180" value={plane.angle_from_horizontal_deg??''} onChange={e=>update({angle_from_horizontal_deg:e.target.value===''?null:Number(e.target.value)})}/></label>
      <label>Panel measurement notes<textarea value={plane.note} onChange={e=>update({note:e.target.value})}/></label>
      <button type="button" onClick={()=>{change({planes:data.planes.filter((_,i)=>i!==index)});setIndex(0)}}>Remove panel</button>
    </>}
    <h4>3. Record uncertainty before saving</h4><label>Calibration notes<textarea value={data.notes} onChange={e=>change({notes:e.target.value})}/></label>
  </section>
}
