import { Divider, Typography } from "antd";
import Integrations from "../Integrations";
import IntegrationTokenForm from "./IntegrationTokenForm";
import { useTc } from "@/i18n/useTc";

export default function IntegrationSettings() {
  const { tc } = useTc();
  return (
    <div>
      <Typography.Title level={5} style={{ marginTop: 0 }}>{tc('北向集成')}</Typography.Title>
      <IntegrationTokenForm />
      <Divider />
      <Integrations embedded />
    </div>
  );
}
