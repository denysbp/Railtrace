"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiSend, Assignment, fromInput, toInput } from "@/lib/api";

function Row({ a, onSaved }: { a: Assignment; onSaved: () => void }) {
  const [start, setStart] = useState(toInput(a.started_at));
  const [end, setEnd] = useState(toInput(a.ended_at));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const changed = start !== toInput(a.started_at) || end !== toInput(a.ended_at);

  async function save() {
    setSaving(true);
    const err = await apiSend("PATCH", `/assignments/${a.id}`, {
      started_at: fromInput(start),
      ended_at: fromInput(end),
    });
    setSaving(false);
    setError(err);
    if (!err) onSaved();
  }

  return (
    <>
      <tr>
        <td>{a.id}</td>
        <td>{a.trainset_id}</td>
        <td><input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required /></td>
        <td><input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required /></td>
        <td>
          <button className="secondary" onClick={save} disabled={!changed || saving || !start || !end}>
            {saving ? "Saving…" : "Save"}
          </button>
        </td>
      </tr>
      {error && (
        <tr>
          <td colSpan={5}><div className="error">{error}</div></td>
        </tr>
      )}
    </>
  );
}

export default function Assignments({ code, assignments }: { code: string; assignments: Assignment[] }) {
  const router = useRouter();
  const [trainset, setTrainset] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    const err = await apiSend("POST", `/duties/${encodeURIComponent(code)}/assignments`, {
      trainset: trainset.trim(),
      started_at: fromInput(start),
      ended_at: fromInput(end),
    });
    setSaving(false);
    setError(err);
    if (!err) {
      setMessage(`Assignment for ${trainset.trim()} added.`);
      setTrainset("");
      setStart("");
      setEnd("");
      router.refresh();
    }
  }

  function saved() {
    setMessage("Assignment updated.");
    router.refresh();
  }

  return (
    <>
      <div className="card-head">
        <h2>Assignments</h2>
        <span className="muted">Times in UTC</span>
      </div>
      {assignments.length === 0 ? (
        <p className="empty">No assignments.</p>
      ) : (
        <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Trainset ID</th>
              <th>Start</th>
              <th>End</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              // key includes the times so the row resets after a refresh
              <Row key={`${a.id}-${a.started_at}-${a.ended_at}`} a={a} onSaved={saved} />
            ))}
          </tbody>
        </table>
        </div>
      )}

      <hr className="divider" />
      <h3>Add assignment</h3>
      <form className="inline" onSubmit={add}>
        <label>
          Trainset serial
          <input value={trainset} onChange={(e) => setTrainset(e.target.value)} placeholder="TS-0001" required />
        </label>
        <label>
          Start (UTC)
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
        </label>
        <label>
          End (UTC)
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required />
        </label>
        <button type="submit" disabled={saving}>{saving ? "Adding…" : "Add"}</button>
      </form>
      {error && <div className="error">{error}</div>}
      {message && <p className="ok">{message}</p>}
    </>
  );
}
