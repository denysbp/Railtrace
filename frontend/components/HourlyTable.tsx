"use client";

import { useEffect, useState } from "react";
import { errorDetail, fmtDateTime, Hourly, METRICS } from "@/lib/api";

export default function HourlyTable({ code }: { code: string }) {
  const [metric, setMetric] = useState("SPD");
  const [data, setData] = useState<Hourly | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetch(`/api/duties/${encodeURIComponent(code)}/hourly?metric=${metric}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Error ${res.status}: ${await errorDetail(res)}`);
        return res.json();
      })
      .then((json: Hourly) => !cancelled && setData(json))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [code, metric]);

  return (
    <>
      <div className="card-head">
        <h2>Hourly</h2>
        <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {METRICS.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      {data && data.metric === metric && (
        data.buckets.length === 0 ? (
          <p className="empty">No hourly data for {metric}.</p>
        ) : (
          <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Hour (UTC)</th>
                <th className="num">Reports</th>
                <th className="num">{metric}</th>
                <th className="num">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {data.buckets.map((b) => (
                <tr key={b.hour}>
                  <td>{fmtDateTime(b.hour)}</td>
                  <td className="num">{b.count}</td>
                  <td className="num">{b.value.toFixed(2)}</td>
                  <td className="num">{(b.coverage * 100).toFixed(1)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )
      )}
    </>
  );
}
