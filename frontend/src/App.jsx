import React, { useState } from 'react'

const API = 'http://127.0.0.1:8000'

function Card({pick, onDecide}){
  const it = pick.item
  const f = pick.fees
  return (
    <div className="card">
      <div className="header">
        <div>
          <h3 className="title">{pick.type}: {it.name}</h3>
          <p className="subtitle">{it.restaurant} • {it.cuisine}</p>
        </div>
        <div className="row">
          <span className="pill">{it.rating}★</span>
          <span className="pill">{it.eta_min}m</span>
          <span className="pill">₹{f.total}</span>
        </div>
      </div>
      <div className="row" style={{marginBottom:8}}>
        {it.tags?.slice(0,3).map(t => <span key={t} className="pill">{t}</span>)}
        {it.veg ? <span className="pill">Veg</span> : <span className="pill">Non-veg</span>}
        <span className="pill">Spice {it.spice}/5</span>
      </div>
      <p className="why">{pick.why}</p>
      <div className="row" style={{marginTop:12}}>
        <button className="btn" onClick={() => onDecide(it.id)}>Decide this</button>
      </div>
    </div>
  )
}

export default function App(){
  const [budget, setBudget] = useState(300)
  const [vegOnly, setVegOnly] = useState(true)
  const [spice, setSpice] = useState(2.0)
  const [lowOil, setLowOil] = useState(false)
  const [novelty, setNovelty] = useState(0.3)
  const [eta, setEta] = useState(30)
  const [picks, setPicks] = useState([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  async function getPicks(){
    setLoading(true); setMsg('')
    try{
      const url = new URL(API + '/recommend')
      url.searchParams.set('budget', budget)
      url.searchParams.set('veg_only', vegOnly)
      url.searchParams.set('spice', spice)
      url.searchParams.set('low_oil', lowOil)
      url.searchParams.set('novelty', novelty)
      url.searchParams.set('eta_limit', eta)
      const res = await fetch(url)
      const data = await res.json()
      setPicks(data.picks || [])
      if(!data.picks || data.picks.length===0){
        setMsg(data.note || 'No picks. Loosen constraints.')
      }
    }catch(e){
      setMsg('Error contacting API. Is backend running on 8000?')
    }finally{
      setLoading(false)
    }
  }

  async function decide(itemId){
    try{
      await fetch(API + '/feedback', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({item_id:itemId, outcome:'selected'})
      })
      alert('Decided. Open your food app and order this pick! History updated for smarter variety next time.')
    }catch(e){
      alert('Could not send feedback, but you can still order the item.')
    }
  }

  return (
    <div className="container">
      <div className="card" style={{marginBottom:16}}>
        <h2 style={{marginTop:0}}>Eat-Decider</h2>
        <p className="why">Tell me your constraints and I’ll propose 3 no-regret picks: Safe, Value, and Adventure — with all-in pricing and a one-line why.</p>
        <div className="row" style={{gap:16, flexWrap:'wrap', marginTop:12}}>
          <div className="field" style={{minWidth:120}}>
            <label>Budget (₹, all-in)</label>
            <input type="number" value={budget} onChange={e=>setBudget(parseInt(e.target.value||0))}/>
          </div>
          <div className="field" style={{minWidth:140}}>
            <label>ETA limit (minutes)</label>
            <input type="number" value={eta} onChange={e=>setEta(parseInt(e.target.value||0))}/>
          </div>
          <div className="field" style={{minWidth:160}}>
            <label>Spice preference (0–5)</label>
            <input type="number" step="0.5" min="0" max="5" value={spice} onChange={e=>setSpice(parseFloat(e.target.value||0))}/>
          </div>
          <div className="field" style={{minWidth:160}}>
            <label>Novelty (0–1)</label>
            <input type="number" step="0.1" min="0" max="1" value={novelty} onChange={e=>setNovelty(parseFloat(e.target.value||0))}/>
          </div>
          <div className="field" style={{minWidth:120}}>
            <label>Veg only?</label>
            <select value={vegOnly ? 'yes':'no'} onChange={e=>setVegOnly(e.target.value==='yes')}>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <div className="field" style={{minWidth:120}}>
            <label>Low-oil mode</label>
            <select value={lowOil ? 'yes':'no'} onChange={e=>setLowOil(e.target.value==='yes')}>
              <option value="no">Off</option>
              <option value="yes">On</option>
            </select>
          </div>
          <div className="field" style={{alignSelf:'flex-end'}}>
            <button className="btn" onClick={getPicks} disabled={loading}>{loading?'Thinking…':'Get Picks'}</button>
          </div>
        </div>
        {msg && <p className="why" style={{marginTop:8}}>{msg}</p>}
      </div>

      <div className="grid">
        {picks.map(p => <Card key={p.type} pick={p} onDecide={decide} />)}
      </div>
    </div>
  )
}
