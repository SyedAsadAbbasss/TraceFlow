import { ArrowRightLeft, GitFork, Merge, RefreshCw, Sparkles, Split, TrendingUp, TriangleAlert, Zap } from 'lucide-react';

// Talks to the backend (FastAPI) and returns the answer as data.
export async function api(path, method = 'GET', body) {
  const res = await fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}

// Indian number format: 100000 becomes ₹1,00,000.
export const money = (n) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

// The server stores UTC times without a "Z". We add it so the browser shows the viewer's local time.
export const when = (ts) =>
  new Date(ts + 'Z').toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

// If the new data is identical to the old data, keep the old object. React then skips the redraw, so the graph does not jump.
export const keepIfSame = (old, next) => (JSON.stringify(old) === JSON.stringify(next) ? old : next);

// Friendly names for the pattern codes the backend uses.
export const PATTERN_LABEL = {
  cycle: 'Circular money movement',
  structuring: 'Structuring',
  fan_in: 'Fan-in (many accounts → one)',
  fan_out: 'Fan-out (one account → many)',
  pass_through: 'Pass-through account',
  amount_spike: 'Amount spike',
  velocity: 'Unusual speed',
};

// Which icon goes next to a reason. Reasons are plain sentences, so we look for a few key words.
const REASON_ICONS = [
  [/\(AI\)/, Sparkles],
  [/money returned/i, RefreshCw],
  [/transfers of/i, Split],
  [/different accounts sent/i, Merge],
  [/sent money to \d+ different/i, GitFork],
  [/sent out within/i, ArrowRightLeft],
  [/usual/i, TrendingUp],
  [/in the last hour/i, Zap],
];
export function reasonIcon(text) {
  const hit = REASON_ICONS.find(([pattern]) => pattern.test(text));
  return hit ? hit[1] : TriangleAlert;
}
