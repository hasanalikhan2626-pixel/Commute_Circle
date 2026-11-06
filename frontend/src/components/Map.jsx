// Port of the prototype's SVG map: area dots, pickup route to campus, member markers.
import { useMeta } from '../meta'

const BB = { la0: 24.775, la1: 24.95, lo0: 67.01, lo1: 67.215 }
const MW = 560, MH = 420
const clampX = (v) => Math.max(8, Math.min(MW - 8, v))
const clampY = (v) => Math.max(8, Math.min(MH - 8, v))
const X = (lon) => clampX(20 + ((lon - BB.lo0) / (BB.lo1 - BB.lo0)) * (MW - 40))
const Y = (lat) => clampY(20 + ((BB.la1 - lat) / (BB.la1 - BB.la0)) * (MH - 40))
const sa = (a) => a.replace('Gulshan-e-Iqbal', 'Gulshan').replace('Gulistan-e-Johar', 'Johar')

/**
 * group:   [{coords:[lat,lng], area, me, pickup}]  members in pickup order
 * others:  [[lat,lng]] other students (dots only, no names)
 * bubbles: [{area, coords, n, u}] admin demand map
 */
export default function Map({ group = [], others = [], bubbles = null, label }) {
  const meta = useMeta()
  if (!meta) return null
  const campus = [meta.campus.lat, meta.campus.lng]
  const lines = []
  for (let i = 1; i < 6; i++) {
    lines.push(<line key={'h' + i} x1="0" x2={MW} y1={(i * MH) / 6} y2={(i * MH) / 6} stroke="var(--road)" strokeWidth=".5" />)
    lines.push(<line key={'v' + i} y1="0" y2={MH} x1={(i * MW) / 6} x2={(i * MW) / 6} stroke="var(--road)" strokeWidth=".5" />)
  }
  const ordered = [...group].sort((a, b) => (a.pickup || 0) - (b.pickup || 0))
  const path = ordered.length
    ? ordered.map((o, i) => `${i ? 'L' : 'M'}${X(o.coords[1])} ${Y(o.coords[0])}`).join(' ') + ` L${X(campus[1])} ${Y(campus[0])}`
    : null
  const seen = new Set()
  const cx = X(campus[1]), cy = Y(campus[0])
  return (
    <svg className="map" viewBox={`0 0 ${MW} ${MH}`} role="img" aria-label={label || (bubbles ? 'Map of members by area' : 'Map of your group and the route to campus')}>
      {lines}
      {!bubbles && Object.values(meta.areas).map(([la, lo], i) => <circle key={i} cx={X(lo)} cy={Y(la)} r="3" fill="var(--road)" />)}
      {bubbles && bubbles.map((b) => {
        const r = 6 + b.n * 4
        return (
          <g key={b.area}>
            <circle cx={X(b.coords[1])} cy={Y(b.coords[0])} r={r} fill="var(--accent)" fillOpacity=".18" stroke="var(--accent)" />
            {b.u > 0 && <circle cx={X(b.coords[1])} cy={Y(b.coords[0])} r={6 + b.u * 4} fill="var(--bad)" fillOpacity=".55" />}
            <text x={X(b.coords[1]) + r + 4} y={Y(b.coords[0]) + 4} fontSize="11" fill="var(--muted)">{sa(b.area)}</text>
          </g>
        )
      })}
      {others.map(([la, lo], i) => <circle key={'o' + i} cx={X(lo)} cy={Y(la)} r="5" fill="var(--surface)" stroke="var(--muted)" strokeWidth="1.5" />)}
      {path && <path d={path} fill="none" stroke="var(--accent)" strokeWidth="3" strokeDasharray="7 5" strokeLinecap="round" />}
      {ordered.map((o, i) => (
        <g key={'g' + i}>
          <circle cx={X(o.coords[1])} cy={Y(o.coords[0])} r={o.me ? 11 : 9} fill={o.me ? 'var(--sign)' : 'var(--accent)'} stroke="var(--surface)" strokeWidth="2" />
          {o.pickup ? <text x={X(o.coords[1])} y={Y(o.coords[0]) + 4} textAnchor="middle" fontSize="11" fontWeight="700" fill={o.me ? '#3a2a00' : 'var(--accent-ink)'}>{o.pickup}</text> : null}
        </g>
      ))}
      {ordered.map((o, i) => {
        if (seen.has(o.area)) return null
        seen.add(o.area)
        return <text key={'l' + i} x={X(o.coords[1]) + 14} y={Y(o.coords[0]) - 10} fontSize="12" fontWeight="600" fill="var(--ink)">{sa(o.area)}</text>
      })}
      <rect x={cx - 11} y={cy - 11} width="22" height="22" rx="5" fill="var(--ink)" />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize="10" fontWeight="700" fill="var(--bg)">BIC</text>
      <text x={cx + 16} y={cy + 18} fontSize="12" fontWeight="700" fill="var(--ink)">Campus</text>
    </svg>
  )
}
