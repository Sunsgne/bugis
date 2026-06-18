import { useEffect, useMemo, useState } from "react";
import { useTc } from "@/i18n/useTc";
import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Avatar, Button, Dropdown, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  Cable,
  ChevronDown,
  LayoutDashboard,
  LineChart,
  LogOut,
  Menu as MenuIcon,
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

export default function PortalApp() {
  const { user, logout, isTenantUser } = useAuth();
  const { brand } = useBrand();
  const { t } = useTc();
  const nav = useNavigate();
  const loc = useLocation();
  const [me, setMe] = useState<PortalMe | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const accent = brand.accent_color || "#ff6600";

  const menu = useMemo(
    () => [
      { key: "/portal", label: t("portal.menu.dashboard"), icon: <LayoutDashboard size={16} /> },
      { key: "/portal/circuits", label: t("portal.menu.circuits"), icon: <Cable size={16} /> },
      { key: "/portal/traffic", label: t("portal.menu.traffic"), icon: <LineChart size={16} /> },
      { key: "/portal/account", label: t("portal.menu.account"), icon: <ShieldCheck size={16} /> },
    ],
    [t],
  );

  const roleLabel =
    user?.role === "tenant_admin"
      ? t("portal.roleTenantAdmin")
      : user?.role === "tenant_viewer"
        ? t("portal.roleTenantViewer")
        : me?.tenant_code || t("portal.portalLabel");

  useEffect(() => {
    if (!isTenantUser) return;
    api.get<PortalMe>("/portal/me").then((r) => setMe(r.data)).catch(() => setMe(null));
  }, [isTenantUser]);

  if (!user || !isTenantUser) {
    return <Navigate to="/login" replace />;
  }

  const selected =
    menu
      .map((m) => m.key)
      .sort((a, b) => b.length - a.length)
      .find((k) => loc.pathname === k || loc.pathname.startsWith(`${k}/`)) || "/portal";

  const sidebarHeader = (
    <div style={{ padding: "20px 20px 18px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
      <Space align="center" size={10} style={{ marginBottom: 12 }}>
        <BrandLogo brand={brand} variant="sidebar" height={26} />
        <Typography.Text strong style={{ color: "#fff", fontSize: 15 }}>
          {brand.product_name}
        </Typography.Text>
      </Space>
      <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 11, letterSpacing: ".08em", textTransform: "uppercase" }}>
        {t("portal.selfService")}
      </div>
      <div style={{ color: "rgba(255,255,255,0.85)", fontSize: 13, marginTop: 6, fontWeight: 500 }}>
        {me?.tenant_name || t("portal.loading")}
      </div>
      {me?.tenant_code ? (
        <Tag style={{ marginTop: 8, border: "none", color: "#fff", background: accent }}>
          {me.tenant_code}
        </Tag>
      ) : null}
    </div>
  );

  const sidebar = (
    <div className="portal-sidebar-inner h-full">
      {sidebarHeader}
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selected]}
        items={menu.map((m) => ({
          key: m.key,
          icon: m.icon,
          label: m.label,
          onClick: () => {
            nav(m.key);
            setMobileOpen(false);
          },
        }))}
      />
    </div>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={232}
        theme="dark"
        breakpoint="lg"
        collapsedWidth={0}
        className="portal-desktop-sider"
        style={{ background: "linear-gradient(180deg, #0f172a 0%, #111827 100%)" }}
      >
        {sidebar}
      </Sider>

      {mobileOpen ? (
        <div className="portal-mobile-overlay lg:hidden">
          <div className="portal-mobile-backdrop" onClick={() => setMobileOpen(false)} aria-hidden />
          <Sider
            width={232}
            theme="dark"
            className="portal-mobile-sider"
            style={{ background: "linear-gradient(180deg, #0f172a 0%, #111827 100%)" }}
          >
            {sidebar}
          </Sider>
        </div>
      ) : null}

      <Layout className="min-w-0 flex-1">
        <Header
          className="portal-header"
          style={{
            background: "#fff",
            padding: "0 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #eef0f4",
            boxShadow: "0 1px 0 rgba(15,23,42,0.04)",
            borderTop: `3px solid ${accent}`,
          }}
        >
          <div className="flex min-w-0 items-center gap-2">
            <Button
              type="text"
              className="portal-menu-btn lg:hidden"
              icon={<MenuIcon size={20} />}
              onClick={() => setMobileOpen(true)}
              aria-label="Menu"
            />
            <Typography.Title level={5} className="portal-header-title" style={{ margin: 0 }}>
              {me?.tenant_name
                ? `${me.tenant_name} · ${t("portal.circuitService")}`
                : t("portal.circuitService")}
            </Typography.Title>
          </div>
          <Dropdown
            trigger={["click"]}
            placement="bottomRight"
            menu={{
              items: [
                {
                  key: "account",
                  label: t("portal.menu.account"),
                  icon: <UserCog size={14} />,
                  onClick: () => nav("/portal/account"),
                },
                { type: "divider" },
                {
                  key: "logout",
                  label: t("action.logout"),
                  icon: <LogOut size={14} />,
                  danger: true,
                  onClick: logout,
                },
              ],
            }}
          >
            <button className="portal-user-trigger" type="button">
              <Avatar size={34} style={{ background: accent, color: "#fff", fontWeight: 600, flexShrink: 0 }}>
                {(user.full_name || user.username || "U").charAt(0).toUpperCase()}
              </Avatar>
              <span className="portal-user-meta">
                <span className="portal-user-name">{user.full_name || user.username}</span>
                <span className="portal-user-role">{roleLabel}</span>
              </span>
              <ChevronDown size={15} className="portal-user-caret" />
            </button>
          </Dropdown>
        </Header>
        <Content className="portal-content" style={{ padding: 24, background: "#f5f7fa", minHeight: 280 }}>
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
