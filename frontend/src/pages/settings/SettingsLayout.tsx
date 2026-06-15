import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Card, Layout, Menu, Typography } from "antd";
import {
  SettingOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  CloudServerOutlined,
  MailOutlined,
  ApiOutlined,
  BellOutlined,
  SafetyOutlined,
  AuditOutlined,
  RadarChartOutlined,
} from "@ant-design/icons";

const { Sider, Content } = Layout;
const { Paragraph } = Typography;

const NAV = [
  { key: "/settings/general", icon: <ThunderboltOutlined />, label: "平台运行" },
  { key: "/settings/alarms", icon: <AlertOutlined />, label: "告警阈值" },
  { key: "/settings/baseline", icon: <CloudServerOutlined />, label: "设备基线" },
  { key: "/settings/smtp", icon: <MailOutlined />, label: "邮件 SMTP" },
  { key: "/settings/snmp", icon: <RadarChartOutlined />, label: "SNMP 采集" },
  { key: "/settings/integration", icon: <ApiOutlined />, label: "北向集成" },
  { key: "/settings/notifications", icon: <BellOutlined />, label: "通知渠道" },
  { key: "/settings/users", icon: <SafetyOutlined />, label: "用户权限" },
  { key: "/settings/audit", icon: <AuditOutlined />, label: "操作审计" },
];

export default function SettingsLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const selected = NAV.find((n) => loc.pathname.startsWith(n.key))?.key || "/settings/general";

  return (
    <Card
      title={
        <span>
          <SettingOutlined style={{ marginRight: 8 }} />
          系统设置
        </span>
      }
    >
      <Paragraph type="secondary" style={{ marginTop: 0 }}>
        集中管理平台运行参数、告警策略、SNMP/邮件、北向集成与用户权限。修改后即时生效。
      </Paragraph>
      <Layout style={{ background: "transparent", minHeight: 520 }}>
        <Sider width={200} theme="light" style={{ borderRight: "1px solid #f0f0f0", background: "#fafafa" }}>
          <Menu
            mode="inline"
            selectedKeys={[selected]}
            items={NAV}
            onClick={(e) => nav(e.key)}
            style={{ border: "none", background: "transparent" }}
          />
        </Sider>
        <Content style={{ padding: "0 0 0 24px", minWidth: 0 }}>
          <Outlet />
        </Content>
      </Layout>
    </Card>
  );
}
