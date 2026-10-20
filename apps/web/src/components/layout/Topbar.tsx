import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/eval", label: "Evaluation" },
  { href: "/about", label: "About" },
];

export function Topbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-ink">
          Next Signal
        </Link>
        <nav className="flex items-center gap-6">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3 hover:text-signal"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
