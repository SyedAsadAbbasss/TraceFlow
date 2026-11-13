import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { ArrowRight } from 'lucide-react';
import { money, when } from './lib.js';

const RED = '#e5484d';
const GREY = '#8b95a7';

// Reads a CSS colour (like --text) so the text drawn on the canvas follows light and dark mode.
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Names come from the API, and hover tooltips are HTML, so make the text safe first.
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// A short name for under a dot.
const shortName = (name) => (name.length > 16 ? name.slice(0, 15) + '…' : name);

// The key to what the colours and shapes mean.
function Legend() {
  const dot = (size, style) => (
    <i style={{ display: 'inline-block', width: size, height: size, borderRadius: '50%', marginRight: 8, verticalAlign: 'middle', ...style }} />
  );
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 22px', alignItems: 'center', padding: '10px 14px', marginBottom: 10, borderRadius: 12, background: 'var(--bg)', border: '1px solid var(--line)', fontSize: '0.9rem' }}>
      <span>{dot(16, { background: RED })}Part of a money loop (cycle)</span>
      <span>{dot(16, { background: GREY, border: '3px solid var(--text)' })}Flagged account (the alert you are viewing)</span>
      <span>{dot(9, { background: GREY })}Normal account</span>
      <span><ArrowRight size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />Direction the money moved</span>
      <span className="muted">Moving dots show money going round the loop. Hover for details.</span>
    </div>
  );
}

// The money-flow graph. Each dot is an account, each arrow a transfer. Accounts and arrows on a money loop are red.
export default function MoneyGraph({ graph, transactions }) {
  const box = useRef(null);
  const fg = useRef(null);
  const [width, setWidth] = useState(900);
  const [picked, setPicked] = useState(null);

  // Keep the canvas as wide as its card.
  useEffect(() => {
    const fit = () => box.current && setWidth(box.current.clientWidth);
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);

  // Turn the backend's answer into the shape the graph library wants. Also work out what each account sent and received,
  // and when each transfer happened (the time is known for transfers listed in the alert's related transactions).
  const data = useMemo(() => {
    if (!graph) return { nodes: [], links: [] };
    const latest = {};
    for (const t of transactions || []) {
      const key = t.from_account + '>' + t.to_account;
      if (!latest[key] || t.ts > latest[key]) latest[key] = t.ts;
    }
    const sent = {};
    const received = {};
    for (const e of graph.edges) {
      sent[e.from] = (sent[e.from] || 0) + e.amount;
      received[e.to] = (received[e.to] || 0) + e.amount;
    }
    return {
      nodes: graph.nodes.map((n) => ({ ...n, sent: sent[n.id] || 0, received: received[n.id] || 0 })),
      links: graph.edges.map((e) => ({ source: e.from, target: e.to, amount: e.amount, in_cycle: e.in_cycle, time: latest[e.from + '>' + e.to] })),
    };
  }, [graph, transactions]);

  // Spread the accounts out so names and amounts do not overlap.
  useEffect(() => {
    fg.current?.d3Force('link')?.distance(240);
    fg.current?.d3Force('charge')?.strength(-900);
  }, [data]);

  // Draw one account: a dot with its name underneath. Loop accounts are big and red, normal ones small and grey.
  // The account we are looking at gets an outline ring.
  function drawNode(node, ctx, scale) {
    const r = node.in_cycle ? 9 : 4.5;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = node.in_cycle ? RED : GREY;
    ctx.fill();
    if (node.focus) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
      ctx.lineWidth = 2.5 / scale;
      ctx.strokeStyle = cssVar('--text');
      ctx.stroke();
    }
    const labelY = node.y + r + (node.focus ? 10 : 4) / scale;
    ctx.font = `${node.in_cycle ? 'bold ' : ''}${14 / scale}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.lineWidth = 4 / scale;
    ctx.strokeStyle = cssVar('--card'); // a soft outline so lines do not cut through the name
    ctx.strokeText(shortName(node.name), node.x, labelY);
    ctx.fillStyle = cssVar('--text');
    ctx.fillText(shortName(node.name), node.x, labelY);
  }

  // Write the amount (for example ₹47,654) on the middle of each arrow, on a small background box.
  function drawAmount(link, ctx, scale) {
    const a = link.source;
    const b = link.target;
    const cp = link.__controlPoints; // the library's curve point; missing if the line is straight
    const x = cp ? 0.25 * a.x + 0.5 * cp[0] + 0.25 * b.x : (a.x + b.x) / 2;
    const y = cp ? 0.25 * a.y + 0.5 * cp[1] + 0.25 * b.y : (a.y + b.y) / 2;
    const text = money(link.amount);
    ctx.font = `bold ${12 / scale}px sans-serif`;
    const w = ctx.measureText(text).width + 10 / scale;
    const h = 18 / scale;
    ctx.beginPath();
    ctx.roundRect(x - w / 2, y - h / 2, w, h, 4 / scale);
    ctx.fillStyle = cssVar('--card');
    ctx.fill();
    ctx.lineWidth = 1 / scale;
    ctx.strokeStyle = link.in_cycle ? RED : cssVar('--line');
    ctx.stroke();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = link.in_cycle ? RED : cssVar('--muted');
    ctx.fillText(text, x, y);
  }

  return (
    <section className="card">
      <h2>Money flow</h2>
      <Legend />
      <div ref={box} className="graph-box" style={{ height: 640 }}>
        {graph ? (
          <ForceGraph2D
            ref={fg}
            graphData={data}
            width={width}
            height={640}
            backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={drawNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, node.in_cycle ? 14 : 10, 0, 2 * Math.PI);
              ctx.fill();
            }}
            nodeLabel={(n) => `<b>${esc(n.name)}</b> (${esc(n.id)})<br/>Received ${money(n.received)} · Sent ${money(n.sent)}<br/><i>from the transfers shown</i>`}
            linkLabel={(l) => `${money(l.amount)} · ${l.time ? esc(when(l.time)) : 'time not in this view'}`}
            linkCurvature={0.2}
            linkColor={(l) => (l.in_cycle ? RED : GREY)}
            linkWidth={(l) => (l.in_cycle ? 3.5 : 1)}
            linkDirectionalArrowLength={(l) => (l.in_cycle ? 10 : 6)}
            linkDirectionalArrowRelPos={0.8}
            linkDirectionalArrowColor={(l) => (l.in_cycle ? RED : GREY)}
            linkDirectionalParticles={(l) => (l.in_cycle ? 3 : 0)}
            linkDirectionalParticleWidth={4}
            linkDirectionalParticleSpeed={0.006}
            linkDirectionalParticleColor={() => RED}
            linkCanvasObjectMode={() => 'after'}
            linkCanvasObject={drawAmount}
            autoPauseRedraw={false}
            enableNodeDrag={false}
            warmupTicks={40}
            cooldownTime={2500}
            onEngineStop={() => fg.current?.zoomToFit(400, 60)}
            onNodeClick={(node) => setPicked(node)}
          />
        ) : (
          <p className="muted pad">Select an alert to see who sent money to whom.</p>
        )}
      </div>
      {picked && (
        <p className="picked">
          <strong>{picked.name}</strong> ({picked.id}){picked.in_cycle ? ' · part of a money loop' : ''}
        </p>
      )}
    </section>
  );
}
