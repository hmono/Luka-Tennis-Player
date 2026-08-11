import Link from "next/link";

const navLinks = [
  { label: "Analytics Modules", href: "/" },
  { label: "Career", href: "/career" },
  { label: "Level Comparison", href: "/tennis-level-comparison" },
  { label: "Tactics", href: "/tactics" },
  { label: "Physical", href: "/physical" },
];

const taglineDate = new Date().toLocaleDateString("en-US", {
  month: "long",
  year: "numeric",
});

export default function Header() {
  return (
    <header className="site-header">
      <div className="shell site-header-inner">
        <div>
          <Link href="/" className="site-header-brand-link">
            Luka Ono Analytics
          </Link>
          <p className="site-header-tagline">
            Performance intelligence partner · {taglineDate}
          </p>
        </div>
        <nav className="site-header-nav">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="site-header-nav-link">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
