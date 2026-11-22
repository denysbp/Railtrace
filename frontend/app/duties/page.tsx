import Link from "next/link";
import LineBadge from "@/components/LineBadge";
import {
  apiGet,
  Duty,
  DutyStations,
  fmtTime,
  HOT_AXLE,
  Line,
  maxAxle,
  Summary,
} from "@/lib/api";

type Search = Promise<{ date?: string; line?: string }>;

export default async function DutiesPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const date = params.date || new Date().toISOString().slice(0, 10);
  const line = params.line || "";

  const query = new URLSearchParams({ date });
  if (line) query.set("line", line);

  const [lines, duties] = await Promise.all([
    apiGet<Line[]>("/lines"),
    apiGet<Duty[]>(`/duties?${query}`),
  ]);

  // Per duty: summary (trainsets, measurements, axle maxima) and the line code.
  const rows = await Promise.all(
    duties.map(async (duty) => {
      const [summary, stations] = await Promise.all([
        apiGet<Summary>(`/duties/${encodeURIComponent(duty.code)}/summary`),
        apiGet<DutyStations>(`/duties/${encodeURIComponent(duty.code)}/stations`),
      ]);
      return { duty, summary, line: stations.line, maxAxle: maxAxle(summary.metrics) };
    }),
  );

  const hotCount = rows.filter((r) => r.maxAxle !== null && r.maxAxle >= HOT_AXLE).length;

  return (
    <>
      <div className="page-head">
        <h1>Duties</h1>
        <p>Planned services for a day. Times in UTC.</p>
      </div>

      <section className="card">
        <form className="inline" method="get">
          <label>
            Date
            <input type="date" name="date" defaultValue={date} required />
          </label>
          <label>
            Line
            <select name="line" defaultValue={line}>
              <option value="">All lines</option>
              {lines.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Filter</button>
        </form>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>
            {rows.length} {rows.length === 1 ? "duty" : "duties"} on {date}
            {line && <> · line {line}</>}
          </h2>
          {hotCount > 0 && (
            <span className="badge hot-badge">
              {hotCount} with axle ≥ {HOT_AXLE} °C
            </span>
          )}
        </div>
        {rows.length === 0 ? (
          <p className="empty">No duties for this filter.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Line</th>
                  <th>Planned start</th>
                  <th>Planned end</th>
                  <th>Trainsets</th>
                  <th className="num">Measurements</th>
                  <th className="num">Max axle temp</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ duty, summary, line, maxAxle }) => {
                  const hot = maxAxle !== null && maxAxle >= HOT_AXLE;
                  return (
                    <tr key={duty.code} className={hot ? "hot" : undefined}>
                      <td>
                        <Link href={`/duties/${encodeURIComponent(duty.code)}`}>{duty.code}</Link>
                      </td>
                      <td><LineBadge code={line} /></td>
                      <td>{fmtTime(duty.planned_start)}</td>
                      <td>{fmtTime(duty.planned_end)}</td>
                      <td>{summary.trainsets.join(", ") || <span className="muted">—</span>}</td>
                      <td className="num">{summary.measurements}</td>
                      <td className={`num${hot ? " hot-text" : ""}`}>
                        {maxAxle !== null ? `${maxAxle.toFixed(1)} °C` : <span className="muted">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
