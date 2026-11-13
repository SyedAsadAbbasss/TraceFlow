import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const RED = '#e5484d';
const GREY = '#8b95a7';

// Reads a CSS colour (like --text) so the text drawn on the canvas follows light and dark mode.
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// The money-flow graph. Each dot is an account, each arrow a transfer. Accounts and arrows on a money loop are red.
export default function MoneyGraph({ graph }) {
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

  // Turn the backend's answer into the shape the graph library wants.
  const data = useMemo(
    () => ({
      nodes: graph ? graph.nodes.map((n) => ({ ...n })) : [],
      links: graph ? graph.edges.map((e) => ({ source: e.from, target: e.to, amount: e.amount, in_cycle: e.in_cycle })) : [],
    }),
    [graph]
  );

  // Spread the accounts out a bit so names and amounts do not overlap.
  useEffect(() => {
    fg.current?.d3Force('link')?.distance(130);
    fg.current?.d3Force('charge')?.strength(-400);
  }, [data]);

  // Draw one account: a circle with its name underneath. The account we are looking at has an outline.
  function drawNode(node, ctx, scale) {
    const r = node.focus ? 9 : 6;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = node.in_cycle ? RED : GREY;
    ctx.fill();
    if (node.focus) {
      ctx.lineWidth = 2 / scale;
      ctx.strokeStyle = cssVar('--text');
      ctx.stroke();
    }
    ctx.font = `${13 / scale}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = cssVar('--text');
    ctx.fillText(node.name, node.x, node.y + r + 3 / scale);
  }

  // Write the amount (for example ₹46k) in the middle of each arrow.
  function drawAmount(link, ctx, scale) {
    const x = (link.source.x + link.target.x) / 2;
    const y = (link.source.y + link.target.y) / 2;
    const text = '₹' + Math.round(link.amount / 1000) + 'k';
    ctx.font = `bold ${12 / scale}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 4 / scale;
    ctx.strokeStyle = cssVar('--card');
    ctx.strokeText(text, x, y);
    ctx.fillStyle = link.in_cycle ? RED : cssVar('--muted');
    ctx.fillText(text, x, y);
  }

  return (
    <section className="card">
      <h2>Money flow</h2>
      <div className="legend">
        <span><i className="swatch red" /> On a money loop (cycle)</span>
        <span><i className="swatch grey" /> Other transfers of ₹10,000 or more</span>
        <span className="muted">Click an account to see its name</span>
      </div>
      <div ref={box} className="graph-box">
        {graph ? (
          <ForceGraph2D
            ref={fg}
            graphData={data}
            width={width}
            height={520}
            backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={drawNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 12, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkColor={(l) => (l.in_cycle ? RED : GREY)}
            linkWidth={(l) => (l.in_cycle ? 3 : 1)}
            linkDirectionalArrowLength={8}
            linkDirectionalArrowRelPos={0.85}
            linkCanvasObjectMode={() => 'after'}
            linkCanvasObject={drawAmount}
            onNodeClick={(node) => setPicked(node)}
            cooldownTicks={120}
            onEngineStop={() => fg.current?.zoomToFit(400, 90)}
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
