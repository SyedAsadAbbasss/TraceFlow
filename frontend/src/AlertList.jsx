import { ShieldCheck } from 'lucide-react';
import LevelChip from './LevelChip.jsx';
import { PATTERN_LABEL, when } from './lib.js';

// The list of open alerts. Click a card to select it. Shows an "all clear" message when there are none.
export default function AlertList({ alerts, selectedId, onSelect }) {
  return (
    <section className="card">
      <h2>Alerts</h2>
      {alerts === null ? (
        <p className="muted">Loading…</p>
      ) : alerts.length === 0 ? (
        <div className="empty">
          <ShieldCheck size={36} />
          <strong>All clear — no suspicious activity</strong>
        </div>
      ) : (
        <div className="list">
          {alerts.map((a) => (
            <button key={a.id} className={'alert-card' + (a.id === selectedId ? ' selected' : '')} aria-pressed={a.id === selectedId} onClick={() => onSelect(a.id)}>
              <div className="alert-top">
                <LevelChip level={a.level} />
                <strong>{PATTERN_LABEL[a.pattern] || a.pattern}</strong>
                <span className="score">{a.score}</span>
              </div>
              <div>{a.account_name} <span className="muted">· {a.account_id}</span></div>
              <div className="muted small">{when(a.created_at)}</div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
