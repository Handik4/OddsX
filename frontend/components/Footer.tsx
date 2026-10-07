import { CONTRACT_ADDRESS, EXPLORER_URL } from "@/lib/config";

const LINKS = [
  { label: "GitHub", href: "https://github.com/Handik4/OddsX" },
  { label: "Docs", href: "https://github.com/Handik4/OddsX#readme" },
  {
    label: "GenLayer Explorer",
    href: CONTRACT_ADDRESS ? `${EXPLORER_URL}/address/${CONTRACT_ADDRESS}` : EXPLORER_URL,
  },
];

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-6 md:flex-row">
        <p className="text-center text-sm text-slate-500 md:text-left">
          <span className="font-semibold text-slate-900">OddsX Clearinghouse</span>
          <span className="mx-2 text-slate-300">·</span>© 2026 OddsX. Built on GenLayer.
        </p>
        <nav aria-label="Footer" className="flex items-center gap-6 text-sm">
          {LINKS.map((l) => (
            <a
              key={l.label}
              href={l.href}
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 transition-colors hover:text-slate-900"
            >
              {l.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
