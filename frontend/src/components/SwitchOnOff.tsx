import { Switch, type SwitchProps } from "antd";
import { useTranslation } from "react-i18next";

/** Switch with localized On/Off labels (common.on / common.off). */
export default function SwitchOnOff(props: SwitchProps) {
  const { t } = useTranslation();
  return (
    <Switch
      checkedChildren={t("common.on")}
      unCheckedChildren={t("common.off")}
      {...props}
    />
  );
}
