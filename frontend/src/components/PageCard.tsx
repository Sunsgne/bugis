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
    <Card className={cn("border-border/60 shadow-sm", className)}>
      {(title || extra) && (
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-4">
          <div className="space-y-1">
            {title ? <CardTitle className="text-base">{title}</CardTitle> : null}
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {extra ? <div className="flex flex-wrap items-center gap-2">{extra}</div> : null}
        </CardHeader>
      )}
      <CardContent className={title || extra ? undefined : "pt-6"}>{children}</CardContent>
    </Card>
  );
}
