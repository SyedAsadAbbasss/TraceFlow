import { Activity, Banknote, Bell, ShieldAlert } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { money } from './lib.js';

// One number with a label and an icon.
function Card({ icon: Icon, label, value, tone }) {
  return (
    <div className={'card stat ' + (tone || '')}>
      <div className="stat-icon"><Icon size={20} /></div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="muted">{label}</div>
      </div>
    </div>
  );
}

// Turns "alerts per hour" into chart rows. One single hour would draw no area, so we add an empty hour before it.
function chartRows(stats) {
  const rows = stats.alerts_over_time.map((r) => ({ t: new Date(r.hour + ':00:00Z').getTime(), n: r.n }));
  if (rows.length === 1) rows.unshift({ t: rows[0].t - 3600e3, n: 0 });
  return rows.map((r) => ({ hour: new Date(r.t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), alerts: r.n }));
}

// The four summary numbers plus a small "alerts over time" chart.
export default function StatCards({ stats }) {
  const open = stats ? Object.values(stats.open_alerts).reduce((a, b) => a + b, 0) : '–';
  const rows = stats ? chartRows(stats) : [];
  return (
    <>
      <div className="stats">
        <Card icon={Activity} label="Transactions processed" value={stats ? stats.transactions.toLocaleString('en-IN') : '–'} />
        <Card icon={Bell} label="Open alerts" value={open} />
        <Card icon={ShieldAlert} label="High-risk alerts" value={stats ? stats.open_alerts.high : '–'} tone="danger" />
        <Card icon={Banknote} label="₹ at risk" value={stats ? money(stats.amount_at_risk) : '–'} />
      </div>
      <section className="card">
        <h2>Alerts over time</h2>
        {rows.length === 0 ? (
          <p className="muted">No alerts yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={rows} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="hour" tick={{ fill: 'var(--muted)', fontSize: 12 }} stroke="var(--line)" />
              <YAxis allowDecimals={false} tick={{ fill: 'var(--muted)', fontSize: 12 }} stroke="var(--line)" />
              <Tooltip />
              <Area type="monotone" dataKey="alerts" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.18} strokeWidth={2} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </section>
    </>
  );
}
