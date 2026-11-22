import { notFound } from "next/navigation";
import {
  ApiError,
  apiGet,
  AXLE_METRICS,
  DutyStations,
  DutyWithAssignments,
  fmtDateTime,
  HOT_AXLE,
  LINE_COLORS,
  maxAxle,
  Readings,
  Summary,
} from "@/lib/api";
import Charts from "@/components/Charts";
import HourlyTable from "@/components/HourlyTable";
import Assignments from "@/components/Assignments";
import LineBadge from "@/components/LineBadge";
import LineStrip from "@/components/LineStrip";

export default async function DutyPage({ params }: { params: Promise<{ code: string }> }) {
  const { code: raw } = await params;
  const code = decodeURIComponent(raw);
  const base = `/duties/${encodeURIComponent(code)}`;

  let duty: DutyWithAssignments;
  try {
    duty = await apiGet<DutyWithAssignments>(base);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const [summary, stations, speed, ...axles] = await Promise.all([
    apiGet<Summary>(`${base}/summary`),
    apiGet<DutyStations>(`${base}/stations`),
    apiGet<Readings>(`${base}/readings?metric=SPD`),
    ...AXLE_METRICS.map((m) => apiGet<Readings>(`${base}/readings?metric=${m}`)),
  ]);

  const color = LINE_COLORS[stations.line] ?? "#888";
  const dutyMax = maxAxle(summary.metrics);

  const hotStations = stations.stations.filter((s) => s.max_axle !== null && s.max_axle >= HOT_AXLE).length;
  const isHot = (v: number | null | undefined) => v !== null && v !== undefined && v >= HOT_AXLE;
  const num = (v: number | undefined, digits: number) => (v !== undefined ? v.toFixed(digits) : "—");

  return (
    <>
      <div className="page-head">
        <h1>
          <LineBadge code={stations.line} large /> {duty.code}
        </h1>
        <p>
          Planned {fmtDateTime(duty.planned_start)} → {fmtDateTime(duty.planned_end).slice(11)} UTC
        </p>
      </div>

      <section className="card">
        <h2>Summary</h2>
        <div className="stats">
          <div className="stat"><span>Trainsets</span><b>{summary.trainsets.join(", ") || "—"}</b></div>
          <div className="stat"><span>Measurements</span><b>{summary.measurements}</b></div>
          <div className="stat"><span>Mean speed</span><b>{num(summary.metrics.SPD, 2)} km/h</b></div>
          <div className="stat"><span>Energy</span><b>{num(summary.metrics.KWH, 2)} kWh</b></div>
          <div className={`stat${isHot(dutyMax) ? " hot" : ""}`}>
            <span>Max axle temperature</span>
            <b>{dutyMax !== null ? `${dutyMax.toFixed(1)} °C` : "—"}</b>
          </div>
        </div>
        <div className="stats compact">
          {AXLE_METRICS.map((m) => (
            <div key={m} className={`stat${isHot(summary.metrics[m]) ? " hot" : ""}`}>
              <span>{m} max</span>
              <b>{num(summary.metrics[m], 1)}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Stations</h2>
          {hotStations > 0 && (
            <span className="badge hot-badge">
              {hotStations} {hotStations === 1 ? "station" : "stations"} with axle ≥ {HOT_AXLE} °C
            </span>
          )}
        </div>
        <p className="hint">Highest axle temperature recorded at each station. Red: {HOT_AXLE} °C or more.</p>
        <LineStrip
          color={color}
          stops={stations.stations.map((s) => ({
            code: s.station,
            name: s.name,
            hot: isHot(s.max_axle),
            note: s.max_axle !== null ? `${s.max_axle.toFixed(1)} °C` : "—",
            title: `${s.name}: ${s.reports} reports, max axle ${s.max_axle ?? "—"} °C`,
          }))}
        />
      </section>

      <Charts speed={speed.points} axles={axles.map((r) => r.points)} />

      <section className="card">
        <HourlyTable code={code} />
      </section>

      <section className="card">
        <Assignments code={code} assignments={duty.assignments} />
      </section>
    </>
  );
}
