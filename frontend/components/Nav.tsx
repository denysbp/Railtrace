"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LINE_COLORS } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Lines" },
  { href: "/duties", label: "Duties" },
  { href: "/trainsets/new", label: "Register trainset" },
];

export default function Nav() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  return (
    <header className="nav">
      <div className="nav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">
            {Object.values(LINE_COLORS).map((c) => (
              <i key={c} style={{ background: c }} />
            ))}
          </span>
          Railtrace
        </Link>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={`nav-link${isActive(l.href) ? " active" : ""}`}>
            {l.label}
          </Link>
        ))}
      </div>
    </header>
  );
}
