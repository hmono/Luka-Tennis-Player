import Link from "next/link";

const navLinks = [
  { label: "Analytics Modules", href: "/" },
  { label: "Career", href: "/career" },
  { label: "Level Comparison", href: "/tennis-level-comparison" },
  { label: "Tactics", href: "/tactics" },
  { label: "Physical", href: "/physical" },
];

export default function Header() {
  return (
    <header style={{
      position: "sticky",
      top: 0,
      zIndex: 20,
      background: "rgba(255,255,255,0.95)",
      backdropFilter: "blur(8px)",
      borderBottom: "1px solid rgba(0,0,0,0.08)",
    }}>
      <div className="shell" style={{ display: "flex", alignItems: "center", minHeight: "64px", padding: "12px 48px", flexWrap: "wrap", gap: "8px" }}>
        <div>
          <Link href="/" style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "10px",
            letterSpacing: "0.3em",
            textTransform: "uppercase",
            color: "var(--luka-blue)",
            textDecoration: "none",
            fontWeight: 600,
          }}>
            Luka Ono Analytics
          </Link>
          <p style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "9px",
            letterSpacing: "0.3em",
            textTransform: "uppercase",
            color: "rgba(0,0,0,0.45)",
            marginTop: "2px",
          }}>
            Performance intelligence partner · May 2026
          </p>
        </div>
        <nav style={{ marginLeft: "auto", display: "flex", flexWrap: "wrap", gap: "16px" }}>
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: "9px",
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              color: "rgba(0,0,0,0.45)",
              textDecoration: "none",
              padding: "4px 8px",
            }}>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
