import { useMemo } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Card, Layout, Menu, Typography } from "antd";
import { useTc } from "@/i18n/useTc";
import {
  SettingOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  CloudServerOutlined,
  MailOutlined,
  ApiOutlined,
  BellOutlined,
  LockOutlined,
  SafetyOutlined,
  AuditOutlined,
  RadarChartOutlined,
  BgColorsOutlined,
  CloudUploadOutlined,
  FileTextOutlined,
  FormOutlined,
} from "@ant-design/icons";

const { Sider, Content } = Layout;
const { Paragraph } = Typography;

export default function SettingsLayout() {
  const { t } = useTc();
  const nav = useNavigate();
  const loc = useLocation();

  const navItems = useMemo(
    () => [
      { key: "/settings/brand", icon: <BgColorsOutlined />, label: t("settings.nav.brand") },
      { key: "/settings/general", icon: <ThunderboltOutlined />, label: t("settings.nav.general") },
      { key: "/settings/config-learn", icon: <FileTextOutlined />, label: t("settings.nav.configLearn") },
      { key: "/settings/alarms", icon: <AlertOutlined />, label: t("settings.nav.alarms") },
      { key: "/settings/alarm-templates", icon: <FormOutlined />, label: t("settings.nav.alarmTemplates") },
      { key: "/settings/baseline", icon: <CloudServerOutlined />, label: t("settings.nav.baseline") },
      { key: "/settings/smtp", icon: <MailOutlined />, label: t("settings.nav.smtp") },
      { key: "/settings/management", icon: <CloudUploadOutlined />, label: t("settings.nav.management") },
      { key: "/settings/snmp", icon: <RadarChartOutlined />, label: t("settings.nav.snmp") },
      { key: "/settings/integration", icon: <ApiOutlined />, label: t("settings.nav.integration") },
      { key: "/settings/security", icon: <LockOutlined />, label: t("settings.nav.security") },
      { key: "/settings/notifications", icon: <BellOutlined />, label: t("settings.nav.notifications") },
      { key: "/settings/users", icon: <SafetyOutlined />, label: t("settings.nav.users") },
      { key: "/settings/audit", icon: <AuditOutlined />, label: t("settings.nav.audit") },
    ],
    [t],
  );

  const selected = navItems.find((n) => loc.pathname.startsWith(n.key))?.key || "/settings/general";

  return (
    <Card
      className="settings-layout-card"
      title={
        <span>
          <SettingOutlined style={{ marginRight: 8 }} />
          {t("settings.title")}
        </span>
      }
    >
      <Paragraph type="secondary" style={{ marginTop: 0 }}>
        {t("settings.intro")}
      </Paragraph>
      <Layout className="settings-layout-inner" style={{ background: "transparent", minHeight: 520 }}>
        <Sider
          width={200}
          theme="light"
          breakpoint="lg"
          collapsedWidth={0}
          className="settings-layout-sider"
          style={{ background: "#fafafa", boxShadow: "4px 0 16px rgba(15, 23, 42, 0.04)" }}
        >
          <Menu
            mode="inline"
            selectedKeys={[selected]}
            items={navItems}
            onClick={(e) => nav(e.key)}
            style={{ border: "none", background: "transparent" }}
          />
        </Sider>
        <Content className="settings-layout-content">
          <Outlet />
        </Content>
      </Layout>
    </Card>
  );
}
