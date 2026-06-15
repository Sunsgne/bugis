import { cn } from "@/lib/utils";

const STATUS: Record<string, { dot: string; ring: string; label: string }> = {
  online: { dot: "bg-emerald-500", ring: "border-emerald-200 bg-emerald-50 text-emerald-800", label: "在线" },
  offline: { dot: "bg-rose-500", ring: "border-rose-200 bg-rose-50 text-rose-800", label: "离线" },
  maintenance: { dot: "bg-amber-500", ring: "border-amber-200 bg-amber-50 text-amber-800", label: "维护" },
  unknown: { dot: "bg-slate-400", ring: "border-slate-200 bg-slate-50 text-slate-600", label: "未知" },
};

type Props = {
  status: string;
  className?: string;
};

export default function StatusDot({ status, className }: Props) {
  const cfg = STATUS[status] || STATUS.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        cfg.ring,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", cfg.dot)} />
      {cfg.label}
    </span>
  );
}
