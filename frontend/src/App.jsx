import { useEffect, useRef, useState } from 'react';
import AlertDetail from './AlertDetail.jsx';
import AlertList from './AlertList.jsx';
import MoneyGraph from './MoneyGraph.jsx';
import StatCards from './StatCards.jsx';
import TopBar from './TopBar.jsx';
import { api, keepIfSame } from './lib.js';

// The whole page. It owns the data, asks the backend for fresh data every 2.5 seconds, and passes it to the parts.
export default function App() {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const selectedRef = useRef(null); // the latest selection, so the timer never reads an old value

  // Loads stats, the alert list, and the selected alert with its graph. The newest alert is selected if none is.
  async function refresh() {
    try {
      const [s, list] = await Promise.all([api('/stats'), api('/alerts?status=open')]);
      let id = selectedRef.current;
      if (!list.some((a) => a.id === id)) id = list.length ? list[0].id : null;
      selectedRef.current = id;
      setStats((old) => keepIfSame(old, s));
      setAlerts((old) => keepIfSame(old, list));
      setSelectedId(id);
      if (id === null) {
        setDetail(null);
        setGraph(null);
      } else {
        const d = await api('/alerts/' + id);
        const g = await api('/graph?account_id=' + encodeURIComponent(d.account_id));
        if (selectedRef.current === id) {
          setDetail((old) => keepIfSame(old, d));
          setGraph((old) => keepIfSame(old, g));
        }
      }
      setError('');
    } catch (e) {
      setError('Cannot reach the backend: ' + e.message);
    }
  }

  // Start polling when the page opens, stop when it closes.
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, []);

  // The user clicked an alert card.
  function select(id) {
    selectedRef.current = id;
    setSelectedId(id);
    refresh();
  }

  // Runs one action (a demo button or a status change), then reloads. Shows an error if it fails.
  async function run(action) {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  // Demo button: add a laundering ring, then jump to its alert.
  const inject = () =>
    run(async () => {
      const r = await api('/demo/inject-ring', 'POST');
      select((r.alerts.find((a) => a.pattern === 'cycle') || r.alerts[0]).id);
    });

  // Demo button: delete everything and start again.
  const reset = () =>
    run(async () => {
      if (!window.confirm('Delete all transactions and alerts?')) return;
      await api('/demo/reset', 'POST');
      selectedRef.current = null;
      await refresh();
    });

  // Mark the selected alert reviewed or dismissed. It leaves the open list, so the next one is selected.
  const setStatus = (status) =>
    run(async () => {
      await api('/alerts/' + selectedRef.current, 'PATCH', { status });
      selectedRef.current = null;
      await refresh();
    });

  return (
    <>
      <TopBar live={!error} busy={busy} onInject={inject} onReset={reset} />
      <main className="page">
        {error && <div className="error" role="alert">{error}</div>}
        <StatCards stats={stats} />
        <div className="columns">
          <AlertList alerts={alerts} selectedId={selectedId} onSelect={select} />
          <AlertDetail detail={detail} busy={busy} onStatus={setStatus} />
        </div>
        <MoneyGraph graph={graph} />
      </main>
    </>
  );
}
