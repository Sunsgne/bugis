import { Divider, Typography } from "antd";
import Integrations from "../Integrations";
import IntegrationTokenForm from "./IntegrationTokenForm";

export default function IntegrationSettings() {
  return (
    <div>
      <Typography.Title level={5} style={{ marginTop: 0 }}>
        北向集成
      </Typography.Title>
      <IntegrationTokenForm />
      <Divider />
      <Integrations embedded />
    </div>
  );
}
