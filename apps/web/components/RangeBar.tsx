import type { Projection } from "@/lib/api";

/** Floor-to-ceiling band with a median tick and a gold marker at the risk-adjusted score. */
export function RangeBar({
  projection,
  score,
  max,
  out,
}: {
  projection: Projection | null;
  score: number | null;
  max: number;
  out?: boolean;
}) {
  if (!projection) return <div className="range range--empty">No projection</div>;
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  const { floor, median, ceiling } = projection;

  return (
    <div
      className={`range${out ? " range--out" : ""}`}
      role="img"
      aria-label={`Floor ${floor.toFixed(1)}, median ${median.toFixed(1)}, ceiling ${ceiling.toFixed(1)} points`}
    >
      <div className="range__band" style={{ left: pct(floor), width: `calc(${pct(ceiling)} - ${pct(floor)})` }} />
      <div className="range__median" style={{ left: pct(median) }} />
      {score !== null && <div className="range__score" style={{ left: pct(score) }} />}
    </div>
  );
}
