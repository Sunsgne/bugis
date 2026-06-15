import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type SelectOption = { value: string; label: string };

type Props = {
  value?: string | null;
  onValueChange: (value: string) => void;
  options: readonly SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  allowClear?: boolean;
};

export default function FormSelect({
  value,
  onValueChange,
  options,
  placeholder = "请选择",
  disabled,
  className,
  allowClear,
}: Props) {
  const resolved = value ?? "";

  return (
    <Select
      value={resolved || undefined}
      onValueChange={(v) => onValueChange(v === "__clear__" ? "" : v)}
      disabled={disabled}
    >
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent position="popper" className="max-h-72">
        {allowClear && resolved ? (
          <SelectItem value="__clear__" className="text-muted-foreground">
            清除选择
          </SelectItem>
        ) : null}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
