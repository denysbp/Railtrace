import Link from "next/link";
import { apiGet, Line, LINE_COLORS } from "@/lib/api";
import LineBadge from "@/components/LineBadge";
import LineStrip from "@/components/LineStrip";

export default async function LinesPage() {
  const lines = await apiGet<Line[]>("/lines");
  return (
    <>
      <div className="page-head">
        <h1>Lines</h1>
        <p>Click a line to see its duties.</p>
      </div>
      {lines.map((line) => (
        <Link key={line.code} href={`/duties?line=${line.code}`} className="card line-card">
          <div className="card-head">
            <h2 style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <LineBadge code={line.code} />
              {line.name}
              <span className="muted">· {line.stations.length} stations</span>
            </h2>
            <span className="go">Duties →</span>
          </div>
          <LineStrip color={LINE_COLORS[line.code] ?? "#888"} stops={line.stations} />
        </Link>
      ))}
    </>
  );
}
