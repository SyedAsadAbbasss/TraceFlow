import { CheckCheck, FileText, X } from 'lucide-react';
import { PATTERN_LABEL, money, reasonIcon, when } from './lib.js';

// Details of the selected alert: score, the reasons in plain English, related transactions and the action buttons.
export default function AlertDetail({ detail, busy, onStatus }) {
  if (!detail) {
    return (
      <section className="card">
        <h2>Why was it flagged?</h2>
        <p className="muted">Select an alert to see the reasons.</p>
      </section>
    );
  }
  return (
    <section className="card">
      <div className="detail-head">
        <div className={'score-badge ' + detail.level}>
          <span className="num">{detail.score}</span>
          <span>/ 100 · {detail.level.toUpperCase()}</span>
        </div>
        <div>
          <h2>{PATTERN_LABEL[detail.pattern] || detail.pattern}</h2>
          <p className="muted">{detail.account_name} · {detail.account_id} · {when(detail.created_at)}</p>
        </div>
      </div>

      <h3>Why it was flagged</h3>
      <ul className="reasons">
        {detail.reasons.map((reason) => {
          const Icon = reasonIcon(reason);
          return (
            <li key={reason}>
              <Icon size={18} />
              <span>{reason}</span>
            </li>
          );
        })}
      </ul>

      <div className="actions">
        <button className="btn" disabled={busy} onClick={() => onStatus('reviewed')}><CheckCheck size={16} /> Mark reviewed</button>
        <button className="btn subtle" disabled={busy} onClick={() => onStatus('dismissed')}><X size={16} /> Dismiss</button>
        <a className="btn subtle" href={`/api/alerts/${detail.id}/sar.pdf`} target="_blank" rel="noopener"><FileText size={16} /> SAR report (PDF)</a>
      </div>
      <p className="muted small">An analyst makes the final decision. The system never blocks anyone by itself.</p>

      <h3>Related transactions (24 h)</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Time</th><th>From → To</th><th className="num">Amount</th><th>Channel</th><th className="num">Risk</th></tr>
          </thead>
          <tbody>
            {detail.transactions.map((t) => (
              <tr key={t.id}>
                <td>{when(t.ts)}</td>
                <td>{t.from_account} → {t.to_account}</td>
                <td className="num">{money(t.amount)}</td>
                <td>{t.channel}</td>
                <td className="num">{t.risk_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
