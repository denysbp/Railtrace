"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { HOT_AXLE, ReadingPoint } from "@/lib/api";

const TRAINSET_COLORS = ["#1f6fd1", "#d6312b", "#1e9e55", "#8a4fd1", "#e07b00", "#0a9396", "#c2185b", "#5d4037"];

type Point = { t: number; value: number; station: string | null };

/** Groups points by trainset: { "TS-0001": [{t, value}], ... } */
function byTrainset(points: { measured_at: string; value: number; trainset: string; station: string | null }[]) {
  const series = new Map<string, Point[]>();
  for (const p of points) {
    const list = series.get(p.trainset) ?? [];
    list.push({ t: Date.parse(p.measured_at), value: p.value, station: p.station });
    series.set(p.trainset, list);
  }
  return [...series.entries()].sort(([a], [b]) => a.localeCompare(b));
}

/** Highest of AX1..AX8 per (time, trainset). */
function axleMax(axles: ReadingPoint[][]): ReadingPoint[] {
  const best = new Map<string, ReadingPoint>();
  for (const p of axles.flat()) {
    const key = `${p.measured_at}|${p.trainset}`;
    const current = best.get(key);
    if (!current || p.value > current.value) best.set(key, p);
  }
  return [...best.values()].sort((a, b) => a.measured_at.localeCompare(b.measured_at));
}

const hhmm = (t: number) => new Date(t).toISOString().slice(11, 16);

function TimeChart({
  title,
  unit,
  points,
  colors,
  threshold,
}: {
  title: string;
  unit: string;
  points: ReadingPoint[];
  colors: Map<string, string>;
  threshold?: number;
}) {
  const series = byTrainset(points);
  return (
    <section className="card">
      <h2>{title}</h2>
      {series.length === 0 ? (
        <p className="empty">No readings.</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={hhmm}
              tick={{ fontSize: 12 }}
              label={{ value: "UTC", position: "insideBottomRight", offset: -5 }}
            />
            <YAxis unit={` ${unit}`} width={72} domain={["auto", "auto"]} tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(t) => hhmm(Number(t))}
              formatter={(v, name, item) => {
                const station = (item.payload as Point).station;
                return [`${v} ${unit}${station ? ` @ ${station}` : ""}`, name];
              }}
            />
            <Legend />
            {threshold !== undefined && (
              <ReferenceLine
                y={threshold}
                stroke="#b3261e"
                strokeDasharray="4 4"
                label={{ value: `${threshold} ${unit}`, fill: "#b3261e", position: "insideTopLeft" }}
              />
            )}
            {series.map(([trainset, data]) => (
              <Line
                key={trainset}
                name={trainset}
                data={data}
                dataKey="value"
                stroke={colors.get(trainset)}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}

export default function Charts({ speed, axles }: { speed: ReadingPoint[]; axles: ReadingPoint[][] }) {
  const axle = axleMax(axles);
  // Same colour for a trainset in both charts.
  const names = [...new Set([...speed, ...axle].map((p) => p.trainset))].sort();
  const colors = new Map(names.map((n, i) => [n, TRAINSET_COLORS[i % TRAINSET_COLORS.length]]));
  return (
    <div className="grid-2">
      <TimeChart title="Speed" unit="km/h" points={speed} colors={colors} />
      <TimeChart
        title="Axle temperature (highest of AX1–AX8)"
        unit="°C"
        points={axle}
        colors={colors}
        threshold={HOT_AXLE}
      />
    </div>
  );
}
