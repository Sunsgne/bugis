import { cn } from "@/lib/utils";

const STATUS: Record<string, { dot: string; label: string }> = {
  online: { dot: "bg-emerald-500", label: "在线" },
  offline: { dot: "bg-red-500", label: "离线" },
  maintenance: { dot: "bg-amber-500", label: "维护" },
  unknown: { dot: "bg-slate-400", label: "未知" },
};

type Props = {
  status: string;
  className?: string;
};

export default function StatusDot({ status, className }: Props) {
  const cfg = STATUS[status] || STATUS.unknown;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", className)}>
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", cfg.dot)} />
      <span className="text-muted-foreground">{cfg.label}</span>
    </span>
  );
}
