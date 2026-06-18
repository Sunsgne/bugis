import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Button, Dropdown, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  Cable,
  LayoutDashboard,
  LineChart,
  LogOut,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { BrandLogo } from "../components/BrandLogo";
import { useBrand } from "../context/BrandContext";
import PortalAccount from "./PortalAccount";
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
  { key: "/portal/account", label: "账号与安全", icon: <ShieldCheck size={16} /> },
];

export default function PortalApp() {
  const { user, logout, isTenantUser } = useAuth();
  const { brand } = useBrand();
  const nav = useNavigate();
  const loc = useLocation();
  const [me, setMe] = useState<PortalMe | null>(null);
  const accent = brand.accent_color || "#ff6600";

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
      <Sider
        width={232}
        theme="dark"
        breakpoint="lg"
        collapsedWidth={0}
        style={{ background: "linear-gradient(180deg, #0f172a 0%, #111827 100%)" }}
      >
        <div
          style={{
            padding: "20px 20px 18px",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Space align="center" size={10} style={{ marginBottom: 12 }}>
            <BrandLogo brand={brand} variant="sidebar" height={26} />
            <Typography.Text strong style={{ color: "#fff", fontSize: 15 }}>
              {brand.product_name}
            </Typography.Text>
          </Space>
          <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 11, letterSpacing: ".08em", textTransform: "uppercase" }}>
            客户自助门户
          </div>
          <div style={{ color: "rgba(255,255,255,0.85)", fontSize: 13, marginTop: 6, fontWeight: 500 }}>
            {me?.tenant_name || "加载中…"}
          </div>
          {me?.tenant_code ? (
            <Tag style={{ marginTop: 8, border: "none", color: "#fff", background: accent }}>
              {me.tenant_code}
            </Tag>
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
            borderBottom: "1px solid #eef0f4",
            boxShadow: "0 1px 0 rgba(15,23,42,0.04)",
            borderTop: `3px solid ${accent}`,
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
                    key: "account",
                    label: "账号与安全",
                    icon: <UserCog size={14} />,
                    onClick: () => nav("/portal/account"),
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
            <Route path="/account" element={<PortalAccount />} />
            <Route path="*" element={<Navigate to="/portal" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
