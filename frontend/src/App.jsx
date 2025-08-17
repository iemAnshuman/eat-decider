import React, { useState } from 'react'
const API = 'http://127.0.0.1:8000'
const TOP_LIMIT = 20  // ask backend for top 20 ranked items

// Simple card for a pick
function Card({ pick, onDecide }) {
  const it = pick.item
  const f = pick.fees
  return (
    <div className="card">
      <div className="header">
        <div>
          {/* rank chip + title */}
          <h3 className="title">
            <span className="pill" style={{ marginRight: 8 }}>{pick.type}</span>
            {it.name}
          </h3>
          <p className="subtitle">{it.restaurant} • {it.cuisine}</p>
        </div>
        <div className="row">
          <span className="pill">{it.rating}★</span>
          <span className="pill">{it.eta_min}m</span>
          <span className="pill">₹{f.total}</span>
        </div>
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        {it.tags?.slice(0, 3).map(t => <span key={t} className="pill">{t}</span>)}
        {it.veg ? <span className="pill">Veg</span> : <span className="pill">Non-veg</span>}
        <span className="pill">Spice {it.spice}/5</span>
      </div>
      <p className="why">{pick.why}</p>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn" onClick={() => onDecide(it.id)}>Decide this</button>
      </div>
    </div>
  )
}

export default function App() {
  // Decision controls
  const [budget, setBudget] = useState(300)
  const [vegOnly, setVegOnly] = useState(true)
  const [spice, setSpice] = useState(2.0)
  const [lowOil, setLowOil] = useState(false)
  const [novelty, setNovelty] = useState(0.3)
  const [eta, setEta] = useState(30)

  // Search intent
  const [query, setQuery] = useState('biryani')
  const [location, setLocation] = useState('Kandoli, Dehradun') // human-readable place

  const [picks, setPicks] = useState([])
  const [total, setTotal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  async function getPicks() {
    setLoading(true); setMsg(''); setTotal(null)
    try {
      const url = new URL(API + '/recommend')
      // Required knobs
      url.searchParams.set('budget', String(budget))
      url.searchParams.set('veg_only', String(vegOnly))
      url.searchParams.set('spice', String(spice))
      url.searchParams.set('low_oil', String(lowOil))
      url.searchParams.set('novelty', String(novelty))
      url.searchParams.set('eta_limit', String(eta))
      // Ranked list size
      url.searchParams.set('limit', String(TOP_LIMIT))
      // Intent
      if (query && query.trim().length > 0) url.searchParams.set('q', query.trim())
      if (location && location.trim().length > 0) url.searchParams.set('place', location.trim())

      const res = await fetch(url)
      const data = await res.json()
      setPicks(data.picks || [])
      setTotal(data.total_candidates ?? null)
      if (!data.picks || data.picks.length === 0) {
        setMsg(data.note || 'No picks. Loosen constraints or broaden the query.')
      }
    } catch (e) {
      setMsg('Error contacting API. Is backend running on 8000?')
    } finally {
      setLoading(false)
    }
  }

  async function decide(itemId) {
    try {
      await fetch(API + '/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, outcome: 'selected' })
      })
      alert('Decided. Order in your app; history updated for smarter variety.')
    } catch (e) {
      alert('Feedback failed; still okay to order manually.')
    }
  }

  return (
    <div className="container">
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>Eat-Decider</h2>
        <p className="why">
          Ranked recommendations (highest score first). Type what you’re craving and where you are.
          I’ll quietly use ONDC + your local list under the hood.
        </p>

        <div className="row" style={{ gap: 16, flexWrap: 'wrap', marginTop: 12 }}>
          <div className="field" style={{ minWidth: 220 }}>
            <label>What are you craving? (query)</label>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') getPicks() }}
              placeholder="biryani / paneer / dosa / pizza ..."
            />
          </div>

          <div className="field" style={{ minWidth: 240 }}>
            <label>Where? (city/area)</label>
            <input
              value={location}
              onChange={e => setLocation(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') getPicks() }}
              placeholder="e.g., Kandoli, Dehradun"
            />
          </div>

          <div className="field" style={{ minWidth: 120 }}>
            <label>Budget (₹, all-in)</label>
            <input
              type="number"
              value={budget}
              onChange={e => setBudget(parseInt(e.target.value || 0))}
            />
          </div>

          <div className="field" style={{ minWidth: 140 }}>
            <label>ETA limit (minutes)</label>
            <input
              type="number"
              value={eta}
              onChange={e => setEta(parseInt(e.target.value || 0))}
            />
          </div>

          <div className="field" style={{ minWidth: 160 }}>
            <label>Spice preference (0–5)</label>
            <input
              type="number" step="0.5" min="0" max="5"
              value={spice}
              onChange={e => setSpice(parseFloat(e.target.value || 0))}
            />
          </div>

          <div className="field" style={{ minWidth: 160 }}>
            <label>Novelty (0–1)</label>
            <input
              type="number" step="0.1" min="0" max="1"
              value={novelty}
              onChange={e => setNovelty(parseFloat(e.target.value || 0))}
            />
          </div>

          <div className="field" style={{ minWidth: 120 }}>
            <label>Veg only?</label>
            <select
              value={vegOnly ? 'yes' : 'no'}
              onChange={e => setVegOnly(e.target.value === 'yes')}
            >
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>

          <div className="field" style={{ minWidth: 120 }}>
            <label>Low-oil mode</label>
            <select
              value={lowOil ? 'yes' : 'no'}
              onChange={e => setLowOil(e.target.value === 'yes')}
            >
              <option value="no">Off</option>
              <option value="yes">On</option>
            </select>
          </div>

          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button className="btn" onClick={getPicks} disabled={loading}>
              {loading ? 'Thinking…' : `Get Top ${TOP_LIMIT}`}
            </button>
          </div>
        </div>

        {/* small status line */}
        {(picks.length > 0 || total) && (
          <p className="why" style={{ marginTop: 8 }}>
            Showing top {picks.length}{total ? ` of ${total}` : ''} ranked results.
          </p>
        )}
        {msg && <p className="why" style={{ marginTop: 8 }}>{msg}</p>}
      </div>

      <div className="grid">
        {picks.map(p => <Card key={p.item.id + p.type} pick={p} onDecide={decide} />)}
      </div>
    </div>
  )
}
