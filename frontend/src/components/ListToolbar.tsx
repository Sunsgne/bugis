import { cn } from "@/lib/utils";

type Props = {
  summary?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
};

export default function ListToolbar({ summary, left, right, className }: Props) {
  return (
    <div className={cn("mb-5 flex flex-wrap items-center justify-between gap-4", className)}>
      <div className="flex flex-wrap items-center gap-3">
        {summary ? <span className="text-sm text-muted-foreground">{summary}</span> : null}
        {left}
      </div>
      {right ? <div className="flex flex-wrap items-center gap-2">{right}</div> : null}
    </div>
  );
}
