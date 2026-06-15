import { Typography } from "antd";
import type { ReactNode } from "react";

type Props = {
  left?: ReactNode;
  right?: ReactNode;
  summary?: string;
};

export default function ListToolbar({ left, right, summary }: Props) {
  return (
    <div className="list-toolbar">
      <div className="list-toolbar__left">{left}</div>
      <div className="list-toolbar__right">
        {summary ? <Typography.Text type="secondary">{summary}</Typography.Text> : null}
        {right}
      </div>
    </div>
  );
}
