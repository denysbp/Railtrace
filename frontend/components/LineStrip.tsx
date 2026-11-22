export type Stop = {
  code: string;
  name: string;
  hot?: boolean;
  note?: string;
  title?: string;
};

/** Stations of a line in order, on a continuous track in the line's colour. */
export default function LineStrip({ color, stops }: { color: string; stops: Stop[] }) {
  return (
    <div className="strip-scroll">
      <ol className="strip" style={{ "--line": color } as React.CSSProperties}>
        {stops.map((s) => (
          <li key={s.code} className={`stop${s.hot ? " hot" : ""}`} title={s.title ?? s.name}>
            <span className="dot" />
            <span className="stop-code">{s.code}</span>
            <span className="stop-name">{s.name}</span>
            {s.note && <span className="stop-note">{s.note}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
