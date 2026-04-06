export default function Footer() {
  return (
    <footer className="border-t border-black/8 bg-white">
      <div className="shell flex flex-col gap-2 py-6 text-xs uppercase tracking-[0.18em] text-black/45 sm:flex-row sm:items-center sm:justify-between">
        <span className="font-semibold tracking-[0.25em]">LUKA ONO · @luka.ono_</span>
        <span>
          Analytical framework: Darren Cahill &amp; Patrick Mouratoglou (tactical) &middot; Olav Aleksander Bu (physiology/biochemistry) &middot; Peter Attia (nutrition)
        </span>
        <span>May 2026</span>
      </div>
    </footer>
  );
}
