"use client";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { NotificationItem } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

export function NotificationBell({ dark = false }: { dark?: boolean }) {
  const [data, setData] = useState<{ unread: number; items: NotificationItem[] }>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const load = useCallback(() => api.notifications().then(setData).catch(() => {}), []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && data.unread) { await api.markRead(); setTimeout(load, 600); }
  }
  return (
    <div ref={box} className="relative">
      <button onClick={toggle} aria-label={`Notifications, ${data.unread} unread`} className={`relative rounded-lg p-2 transition ${dark ? "text-white/70 hover:bg-white/10 hover:text-white" : "text-ink-soft hover:bg-alice-100"}`}>
        <Bell className="h-5 w-5" />
        {data.unread > 0 && <span className="absolute right-0.5 top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-signal-red px-1 text-[10px] font-bold text-white">{data.unread > 9 ? "9+" : data.unread}</span>}
      </button>
      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-2 w-[340px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-alice-200 bg-white text-ink shadow-lift lg:bottom-auto lg:left-auto lg:right-0 lg:top-full lg:mb-0 lg:mt-2">
          <p className="border-b border-alice-200 px-4 py-3 font-display text-sm font-bold">Notifications</p>
          <ul className="max-h-[360px] divide-y divide-alice-200/70 overflow-y-auto">
            {data.items.length === 0 && <li className="px-4 py-8 text-center text-sm text-ink-soft">Nothing yet.</li>}
            {data.items.map((n) => (
              <li key={n.id}><Link href={n.link || "/dashboard"} onClick={() => setOpen(false)} className={`block px-4 py-3 transition hover:bg-port-50/60 ${n.read ? "" : "bg-port-50/40"}`}>
                <p className="text-sm font-semibold">{n.title}</p>{n.body && <p className="mt-0.5 line-clamp-2 text-[13px] text-ink-soft">{n.body}</p>}<p className="mt-1 text-xs text-ink-faint">{timeAgo(n.created_at)}</p>
              </Link></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
