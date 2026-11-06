import { useState } from 'react'
import { api, rs } from '../api'
import { useToast } from './Toast'
import { useLoad } from './ui'

const LIKERT = ['Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree']

// Evaluation surveys (proposal 14.8): spending before/after, SUS usability, safety perception.
export default function Surveys() {
  const [s, , reload] = useLoad(() => api('/api/surveys'))
  const [open, setOpen] = useState(null)
  if (!s) return null
  const done = Object.keys(s.done)
  return (
    <section className="card stack">
      <div><h3>Help evaluate CommuteCircle</h3>
        <p className="hint" style={{ margin: 0 }}>A few short questions for the project’s research. Answers are pseudonymised; see the privacy notice.</p></div>
      {s.due.length === 0 && <p className="hint" style={{ margin: 0 }}>{done.length ? 'Thank you, you’re all done.' : `More questions open after ${s.min_trips} trips with your circle (you have ${s.trips}).`}</p>}
      {s.due.includes('spend_before') && <Spend kind="spend_before" label="Before CommuteCircle, about how much did you spend a month getting to campus?" onDone={reload} />}
      {s.due.includes('spend_after') && <Spend kind="spend_after" label="Now, travelling with your circle, about how much do you spend a month?" onDone={reload} />}
      {s.due.includes('sus') && (open === 'sus' ? <Likert kind="sus" items={s.sus_items} onDone={() => { setOpen(null); reload() }} />
        : <button className="btn" onClick={() => setOpen('sus')}>How easy is CommuteCircle to use? (10 questions)</button>)}
      {s.due.includes('safety') && (open === 'safety' ? <Likert kind="safety" items={s.safety_items} onDone={() => { setOpen(null); reload() }} />
        : <button className="btn" onClick={() => setOpen('safety')}>How safe do you feel? (3 questions)</button>)}
      {!s.due.includes('sus') && !s.due.includes('safety') && s.trips < s.min_trips && done.length > 0 && null}
    </section>
  )
}

function Spend({ kind, label, onDone }) {
  const [v, setV] = useState('')
  const toast = useToast()
  const save = async () => {
    try { await api(`/api/surveys/${kind}`, { method: 'POST', body: { amount_pkr: Number(v) } }); toast(`Saved: ${rs(Number(v))} a month`); onDone() } catch (e) { toast(e.message) }
  }
  return (
    <div><p className="q">{label}</p>
      <div className="row" style={{ flexWrap: 'nowrap' }}><input type="number" min="0" step="500" placeholder="Amount in Rs per month" aria-label={label} value={v} onChange={(e) => setV(e.target.value)} />
        <button className="btn primary" disabled={v === ''} onClick={save}>Save</button></div></div>
  )
}

function Likert({ kind, items, onDone }) {
  const [a, setA] = useState(Array(items.length).fill(0))
  const toast = useToast()
  const save = async () => {
    if (a.includes(0)) { toast('Please answer every statement'); return }
    try { const r = await api(`/api/surveys/${kind}`, { method: 'POST', body: { answers: a } }); toast(kind === 'sus' ? `Thanks! Usability score ${r.score}/100` : 'Thanks for your answers'); onDone() } catch (e) { toast(e.message) }
  }
  return (
    <div className="stack" style={{ gap: 12 }}>
      {items.map((q, i) => (
        <div key={i}><p style={{ margin: '0 0 6px' }}>{i + 1}. {q}</p>
          <div className="opts" role="radiogroup" aria-label={q}>{LIKERT.map((l, n) => (
            <button key={l} className="opt sm" role="radio" aria-checked={a[i] === n + 1} aria-pressed={a[i] === n + 1} title={l}
              onClick={() => setA(a.map((x, j) => (j === i ? n + 1 : x)))}>{n + 1}<span className="hint" style={{ marginLeft: 4 }}>{n === 0 || n === 4 ? l : ''}</span></button>))}</div></div>
      ))}
      <div><button className="btn primary" onClick={save}>Send answers</button></div>
    </div>
  )
}
