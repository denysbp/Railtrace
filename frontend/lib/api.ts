// Types mirror backend/app/schemas.

export type Station = { code: string; name: string };
export type Line = { code: string; name: string; stations: Station[] };

export type Assignment = {
  id: number;
  trainset_id: number;
  duty_id: number;
  started_at: string;
  ended_at: string;
};

export type Duty = {
  id: number;
  code: string;
  line_id: number;
  planned_start: string;
  planned_end: string;
};

export type DutyWithAssignments = Duty & { assignments: Assignment[] };

export type ReadingPoint = {
  measured_at: string;
  value: number;
  trainset: string;
  station: string | null;
};
export type Readings = { duty: string; metric: string; points: ReadingPoint[] };

export type HourlyBucket = { hour: string; count: number; value: number; coverage: number };
export type Hourly = { duty: string; metric: string; buckets: HourlyBucket[] };

export type Summary = {
  duty: string;
  trainsets: string[];
  measurements: number;
  metrics: Record<string, number>;
};

export type StationRollup = { station: string; name: string; reports: number; max_axle: number | null };
export type DutyStations = { duty: string; line: string; stations: StationRollup[] };

export const METRICS = ["SPD", "KWH", "AX1", "AX2", "AX3", "AX4", "AX5", "AX6", "AX7", "AX8"];
export const AXLE_METRICS = METRICS.filter((m) => m.startsWith("AX"));
export const HOT_AXLE = 80; // °C

export const LINE_COLORS: Record<string, string> = {
  AZ: "#1f6fd1", // blue
  AM: "#e8b500", // yellow
  VD: "#1e9e55", // green
  VM: "#d6312b", // red
};

/** Max axle temperature from a summary's metrics (AX1..AX8), or null. */
export function maxAxle(metrics: Record<string, number>): number | null {
  const values = AXLE_METRICS.map((m) => metrics[m]).filter((v) => v !== undefined);
  return values.length ? Math.max(...values) : null;
}

/** Server-side fetch to the FastAPI backend. */
export async function apiGet<T>(path: string): Promise<T> {
  const base = process.env.API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/v1${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, await errorDetail(res));
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, detail: string) {
    super(`${status}: ${detail}`);
  }
}

/** Turns a FastAPI error body into readable text (string detail or pydantic list). */
export async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((e: { loc?: unknown[]; msg: string }) => {
          const field = e.loc?.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${e.msg}` : e.msg;
        })
        .join("; ");
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText;
  }
}

/** Client-side request through the /api proxy. Returns an error message or null. */
export async function apiSend(method: string, path: string, body: unknown): Promise<string | null> {
  try {
    const res = await fetch(`/api${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) return null;
    return `Error ${res.status} ${res.statusText}: ${await errorDetail(res)}`;
  } catch (e) {
    return `Could not reach the API: ${(e as Error).message}`;
  }
}

// All times are shown and entered in UTC.
export function fmtTime(iso: string): string {
  return iso.slice(11, 16);
}
export function fmtDateTime(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}
/** ISO (UTC) -> value for <input type="datetime-local"> */
export function toInput(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16);
}
/** <input type="datetime-local"> value, read as UTC -> ISO */
export function fromInput(value: string): string {
  return `${value}:00Z`;
}
