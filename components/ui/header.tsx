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
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur">
      <div className="shell flex min-h-[64px] flex-col gap-1 border-b border-black/8 py-4 sm:flex-row sm:items-center">
        <div>
          <Link href="/" className="text-sm font-semibold tracking-[0.3em] text-luka-blue uppercase">
            Luka Ono Analytics
          </Link>
          <p className="text-[10px] uppercase tracking-[0.3em] text-black/45">
            Performance intelligence partner · May 2026
          </p>
        </div>
        <nav className="mt-2 flex flex-wrap gap-4 text-[9px] uppercase tracking-[0.28em] text-black/45 sm:mt-0 sm:ml-auto">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="leading-none px-2 py-1">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
