import { Activity, Play, RotateCcw } from 'lucide-react';

// Top bar: app name, tagline, a "Live" dot while the page is polling, and the two demo buttons.
export default function TopBar({ live, busy, onInject, onReset }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo"><Activity size={22} /></div>
        <div>
          <h1>TraceFlow</h1>
          <p>AI Fraud &amp; AML Monitoring</p>
        </div>
      </div>
      <div className="topbar-right">
        <span className={'live ' + (live ? 'on' : 'off')}>
          <span className="dot" /> {live ? 'Live' : 'Offline'}
        </span>
        <button className="btn danger" onClick={onInject} disabled={busy}>
          <Play size={16} /> Inject laundering ring
        </button>
        <button className="btn subtle" onClick={onReset} disabled={busy}>
          <RotateCcw size={16} /> Reset demo
        </button>
      </div>
    </header>
  );
}
