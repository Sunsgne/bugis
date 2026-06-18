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
  LockOutlined,
  SafetyOutlined,
  AuditOutlined,
  RadarChartOutlined,
  BgColorsOutlined,
  CloudUploadOutlined,
  FileTextOutlined,
} from "@ant-design/icons";

const { Sider, Content } = Layout;
const { Paragraph } = Typography;

const NAV = [
  { key: "/settings/brand", icon: <BgColorsOutlined />, label: "品牌外观" },
  { key: "/settings/general", icon: <ThunderboltOutlined />, label: "平台运行" },
  { key: "/settings/config-learn", icon: <FileTextOutlined />, label: "配置管理" },
  { key: "/settings/alarms", icon: <AlertOutlined />, label: "告警阈值" },
  { key: "/settings/baseline", icon: <CloudServerOutlined />, label: "设备基线" },
  { key: "/settings/smtp", icon: <MailOutlined />, label: "邮件 SMTP" },
  { key: "/settings/management", icon: <CloudUploadOutlined />, label: "南向接口" },
  { key: "/settings/snmp", icon: <RadarChartOutlined />, label: "SNMP 采集" },
  { key: "/settings/integration", icon: <ApiOutlined />, label: "北向集成" },
  { key: "/settings/security", icon: <LockOutlined />, label: "安全认证" },
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
      className="settings-layout-card"
      title={
        <span>
          <SettingOutlined style={{ marginRight: 8 }} />
          平台设置
        </span>
      }
    >
      <Paragraph type="secondary" style={{ marginTop: 0 }}>
        集中管理品牌外观、平台运行参数、告警策略、SNMP/邮件、北向集成与用户权限。修改后即时生效。
      </Paragraph>
      <Layout className="settings-layout-inner" style={{ background: "transparent", minHeight: 520 }}>
        <Sider width={200} theme="light" style={{ background: "#fafafa", boxShadow: "4px 0 16px rgba(15, 23, 42, 0.04)" }}>
          <Menu
            mode="inline"
            selectedKeys={[selected]}
            items={NAV}
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
