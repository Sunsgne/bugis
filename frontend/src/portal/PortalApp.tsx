import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Button, Dropdown, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  Cable,
  Gauge,
  KeyRound,
  LayoutDashboard,
  LineChart,
  LogOut,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import PortalDashboard from "./PortalDashboard";
import PortalCircuits from "./PortalCircuits";
import PortalCircuitDetail from "./PortalCircuitDetail";
import PortalTraffic from "./PortalTraffic";

const { Header, Sider, Content } = Layout;

export interface PortalMe {
  user_id: number;
  username: string;
  full_name?: string;
  tenant_id: number;
  tenant_name: string;
  tenant_code: string;
  role: string;
}

const MENU = [
  { key: "/portal", label: "总览", icon: <LayoutDashboard size={16} /> },
  { key: "/portal/circuits", label: "我的专线", icon: <Cable size={16} /> },
  { key: "/portal/traffic", label: "流量洞察", icon: <LineChart size={16} /> },
];

export default function PortalApp() {
  const { user, logout, isTenantUser } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [me, setMe] = useState<PortalMe | null>(null);
  const [pwdOpen, setPwdOpen] = useState(false);

  useEffect(() => {
    if (!isTenantUser) return;
    api.get<PortalMe>("/portal/me").then((r) => setMe(r.data)).catch(() => setMe(null));
  }, [isTenantUser]);

  if (!user || !isTenantUser) {
    return <Navigate to="/login" replace />;
  }

  const selected = MENU.map((m) => m.key)
    .sort((a, b) => b.length - a.length)
    .find((k) => loc.pathname === k || loc.pathname.startsWith(`${k}/`)) || "/portal";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={220} theme="dark" breakpoint="lg" collapsedWidth={0}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
          <Typography.Text strong style={{ color: "#fff", fontSize: 15 }}>
            客户门户
          </Typography.Text>
          <div style={{ color: "rgba(255,255,255,0.65)", fontSize: 12, marginTop: 4 }}>
            {me?.tenant_name || "加载中…"}
          </div>
          {me?.tenant_code ? (
            <Tag color="blue" style={{ marginTop: 6 }}>{me.tenant_code}</Tag>
          ) : null}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={MENU.map((m) => ({
            key: m.key,
            icon: m.icon,
            label: m.label,
            onClick: () => nav(m.key),
          }))}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Typography.Title level={5} style={{ margin: 0 }}>
            {me?.tenant_name ? `${me.tenant_name} · 专线自助服务` : "专线自助服务"}
          </Typography.Title>
          <Space>
            <Typography.Text type="secondary">{user.full_name || user.username}</Typography.Text>
            <Dropdown
              menu={{
                items: [
                  {
                    key: "pwd",
                    label: "修改密码",
                    icon: <KeyRound size={14} />,
                    onClick: () => setPwdOpen(true),
                  },
                  {
                    key: "logout",
                    label: "退出登录",
                    icon: <LogOut size={14} />,
                    onClick: logout,
                  },
                ],
              }}
            >
              <Button type="text">{user.username}</Button>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ padding: 24, background: "#f5f7fa", minHeight: 280 }}>
          <Routes>
            <Route path="/" element={<PortalDashboard me={me} />} />
            <Route path="/circuits" element={<PortalCircuits />} />
            <Route path="/circuits/:id" element={<PortalCircuitDetail />} />
            <Route path="/traffic" element={<PortalTraffic />} />
            <Route path="*" element={<Navigate to="/portal" replace />} />
          </Routes>
        </Content>
      </Layout>
      <ChangePasswordDialog open={pwdOpen} onClose={() => setPwdOpen(false)} />
    </Layout>
  );
}
