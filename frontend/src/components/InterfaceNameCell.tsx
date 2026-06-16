import { Tooltip, Typography } from "antd";
import { formatInterfaceShort, formatInterfaceTooltip } from "../utils/networkDisplay";

type Props = {
  name: string;
  copyable?: boolean;
};

export default function InterfaceNameCell({ name, copyable = true }: Props) {
  const short = formatInterfaceShort(name);
  const text = (
    <Typography.Text code={copyable} copyable={copyable ? { text: name } : false}>
      {short}
    </Typography.Text>
  );
  if (short === name) return text;
  return <Tooltip title={formatInterfaceTooltip(name)}>{text}</Tooltip>;
}
