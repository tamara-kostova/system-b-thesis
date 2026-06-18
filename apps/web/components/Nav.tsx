"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/chat", label: "Chat" },
  { href: "/datasets", label: "Datasets" },
  { href: "/concepts", label: "Concepts" },
  { href: "/apply", label: "Apply" },
  { href: "/my-applications", label: "My Applications" },
  { href: "/spe", label: "My SPEs" },
  { href: "/review", label: "Review" },
  { href: "/register", label: "Register" },
  { href: "/logs", label: "Audit Log" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="bg-slate-900">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <Link href="/" className="text-lg font-semibold text-white tracking-tight">
          Secure<span className="text-blue-400">Health</span>
        </Link>
        <div className="flex items-center gap-6">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`text-sm transition-colors ${
                pathname === l.href
                  ? "text-white font-medium border-b-2 border-blue-400 pb-0.5"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
