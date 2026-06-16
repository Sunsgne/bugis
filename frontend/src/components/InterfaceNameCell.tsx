import { Tooltip, Typography } from "antd";
import { formatInterfaceShort, formatInterfaceTooltip } from "../utils/networkDisplay";

type Props = {
  name: string;
  /** Copy full interface name; defaults to `name`. */
  copyText?: string;
  copyable?: boolean;
};

export default function InterfaceNameCell({
  name,
  copyText,
  copyable = true,
}: Props) {
  const fullName = copyText ?? name;
  const short = formatInterfaceShort(name);
  const text = (
    <Typography.Text
      code={copyable}
      copyable={copyable ? { text: fullName } : false}
      style={{ whiteSpace: "nowrap", marginBottom: 0 }}
    >
      {short}
    </Typography.Text>
  );
  const wrapped =
    short === name && fullName === name ? (
      text
    ) : (
      <Tooltip title={formatInterfaceTooltip(fullName)}>{text}</Tooltip>
    );
  return <span style={{ display: "inline-flex", alignItems: "center", whiteSpace: "nowrap" }}>{wrapped}</span>;
}
