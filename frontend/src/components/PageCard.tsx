import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  title?: React.ReactNode;
  description?: React.ReactNode;
  extra?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
};

export default function PageCard({ title, description, extra, children, className }: Props) {
  return (
    <Card className={cn("w-full min-w-0 border-0 bg-card shadow-sm", className)}>
      {(title || extra) && (
        <CardHeader className="flex flex-col gap-4 space-y-0 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            {title ? <CardTitle className="text-base">{title}</CardTitle> : null}
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {extra ? <div className="flex shrink-0 flex-wrap items-center gap-2">{extra}</div> : null}
        </CardHeader>
      )}
      <CardContent className={title || extra ? undefined : "pt-6"}>{children}</CardContent>
    </Card>
  );
}
