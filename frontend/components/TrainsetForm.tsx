"use client";

import { useState } from "react";
import { apiSend, Line } from "@/lib/api";

export default function TrainsetForm({ lines }: { lines: Line[] }) {
  const [serial, setSerial] = useState("");
  const [line, setLine] = useState(lines[0]?.code ?? "");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    const err = await apiSend("POST", "/trainsets", { serial: serial.trim(), line });
    setSaving(false);
    setError(err);
    if (!err) {
      setMessage(`Trainset ${serial.trim()} registered on line ${line}.`);
      setSerial("");
    }
  }

  return (
    <>
      <form className="stack" onSubmit={submit}>
        <label>
          Serial
          <input value={serial} onChange={(e) => setSerial(e.target.value)} placeholder="TS-0001" maxLength={20} required />
        </label>
        <label>
          Home line
          <select value={line} onChange={(e) => setLine(e.target.value)} required>
            {lines.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code})
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={saving} style={{ alignSelf: "flex-start" }}>{saving ? "Saving…" : "Register"}</button>
      </form>
      {error && <div className="error">{error}</div>}
      {message && <p className="ok">{message}</p>}
    </>
  );
}
