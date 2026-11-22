import { LINE_COLORS } from "@/lib/api";

export default function LineBadge({ code, large }: { code: string; large?: boolean }) {
  const background = LINE_COLORS[code] ?? "#888";
  // texto escuro no amarelo para manter contraste
  const color = code === "AM" ? "#1a1a1a" : "#fff";
  return (
    <span className={`badge${large ? " badge-lg" : ""}`} style={{ background, color }}>
      {code}
    </span>
  );
}
