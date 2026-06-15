import { Card } from "antd";
import type { CardProps } from "antd";

export default function PageCard({ className, ...props }: CardProps) {
  return (
    <Card
      className={["page-card", className].filter(Boolean).join(" ")}
      bordered={false}
      {...props}
    />
  );
}
