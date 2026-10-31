"use client";
import * as React from "react";

interface Point { date: string; questions: number; answered: number }

/** Stacked daily bars: answered (series 1) + unanswered (series 2). Hover tooltip, legend, table view. */
export function QuestionsChart({ data, days }: { data: Point[]; days: number }) {
  const [hover, setHover] = React.useState<number | null>(null);
  const [table, setTable] = React.useState(false);
  // Fill missing days so the time axis is continuous
  const series = React.useMemo(() => {
    const map = new Map(data.map((d) => [d.date, d]));
    const out: Point[] = [];
    const today = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today); d.setDate(today.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      out.push(map.get(key) || { date: key, questions: 0, answered: 0 });
    }
    return out;
  }, [data, days]);
  const max = Math.max(4, ...series.map((d) => d.questions));
  const niceMax = Math.ceil(max / 4) * 4;
  const W = 720, H = 220, padL = 32, padB = 22, padT = 8;
  const plotW = W - padL - 8, plotH = H - padB - padT;
  const bw = plotW / series.length;
  const barW = Math.max(2, Math.min(18, bw - 3));
  const y = (v: number) => padT + plotH - (v / niceMax) * plotH;
  const ticks = [0, niceMax / 4, niceMax / 2, (3 * niceMax) / 4, niceMax];
  const h = hover !== null ? series[hover] : null;

  return (
    <div className="viz-root">
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: "var(--series-1)" }} />Answered from knowledge</span>
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: "var(--series-2)" }} />Not answered</span>
        <button className="ml-auto text-primary hover:underline" onClick={() => setTable(!table)}>{table ? "Show chart" : "Show table"}</button>
      </div>
      {table ? (
        <div className="max-h-64 overflow-auto text-sm">
          <table className="w-full"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1">Date</th><th>Questions</th><th>Answered</th><th>Not answered</th></tr></thead>
            <tbody>{series.filter((d) => d.questions).map((d) => <tr key={d.date} className="border-t"><td className="py-1">{d.date}</td><td className="tabular-nums">{d.questions}</td><td className="tabular-nums">{d.answered}</td><td className="tabular-nums">{d.questions - d.answered}</td></tr>)}</tbody></table>
        </div>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Questions per day, answered versus not answered" onMouseLeave={() => setHover(null)}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={padL} x2={W - 8} y1={y(t)} y2={y(t)} stroke="hsl(var(--border))" strokeWidth={1} />
                <text x={padL - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="hsl(var(--muted-foreground))">{t}</text>
              </g>
            ))}
            {series.map((d, i) => {
              const x = padL + i * bw + (bw - barW) / 2;
              const un = d.questions - d.answered;
              const yA = y(d.answered), yQ = y(d.questions);
              const gap = d.answered && un ? 2 : 0;
              return (
                <g key={d.date} onMouseEnter={() => setHover(i)}>
                  <rect x={padL + i * bw} y={padT} width={bw} height={plotH} fill="transparent" />
                  {d.answered > 0 && <path d={roundedTop(x, yA, barW, y(0) - yA, un ? 0 : 4)} fill="var(--series-1)" opacity={hover === null || hover === i ? 1 : 0.55} />}
                  {un > 0 && <path d={roundedTop(x, yQ, barW, yA - yQ - gap, 4)} fill="var(--series-2)" opacity={hover === null || hover === i ? 1 : 0.55} />}
                  {(i % Math.ceil(series.length / 8) === 0 || i === series.length - 1) && (
                    <text x={x + barW / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="hsl(var(--muted-foreground))">{d.date.slice(5)}</text>
                  )}
                </g>
              );
            })}
          </svg>
          {h && hover !== null && (
            <div className="pointer-events-none absolute top-0 rounded-md border bg-popover px-3 py-2 text-xs shadow-md"
              style={{ left: `clamp(0px, calc(${((padL + hover * bw) / W) * 100}% - 60px), calc(100% - 150px))` }}>
              <p className="font-medium">{h.date}</p>
              <p className="flex items-center gap-1.5"><span className="size-2 rounded-sm" style={{ background: "var(--series-1)" }} />Answered <b className="ml-auto pl-3 tabular-nums">{h.answered}</b></p>
              <p className="flex items-center gap-1.5"><span className="size-2 rounded-sm" style={{ background: "var(--series-2)" }} />Not answered <b className="ml-auto pl-3 tabular-nums">{h.questions - h.answered}</b></p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number) {
  if (h <= 0) return "";
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}
