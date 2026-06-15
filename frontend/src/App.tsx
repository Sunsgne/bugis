import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Spin, Dropdown, Avatar, Tag, Badge, Space } from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  ClusterOutlined,
  ApiOutlined,
  ProfileOutlined,
  LineChartOutlined,
  EnvironmentOutlined,
  UserOutlined,
  LogoutOutlined,
  AlertOutlined,
  DeploymentUnitOutlined,
  PartitionOutlined,
  ApiOutlined as IntegrationIcon,
  AuditOutlined,
  SafetyOutlined,
  AppstoreOutlined,
  CloudServerOutlined,
  BellOutlined,
  ShareAltOutlined,
  FileTextOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { api, getToken } from "./api/client";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Tenants from "./pages/Tenants";
import Sites from "./pages/Sites";
import Devices from "./pages/Devices";
import Circuits from "./pages/Circuits";
import WorkOrders from "./pages/WorkOrders";
import Monitoring from "./pages/Monitoring";
import Alarms from "./pages/Alarms";
import Capacity from "./pages/Capacity";
import Topology from "./pages/Topology";
import Integrations from "./pages/Integrations";
import Audit from "./pages/Audit";
import Users from "./pages/Users";
import Catalog from "./pages/Catalog";
import Controllers from "./pages/Controllers";
import ControlPlane from "./pages/ControlPlane";
import ConfigManagement from "./pages/ConfigManagement";
import Notifications from "./pages/Notifications";
import Settings from "./pages/Settings";
import { nav } from "./constants/uiCopy";
import { useBrand } from "./context/BrandContext";
import { BrandLogo } from "./components/BrandLogo";
import type { MenuProps } from "antd";

const { Header, Sider, Content } = Layout;

type MenuItem = Required<MenuProps>["items"][number];

const MENU: MenuItem[] = [
  {
    type: "group",
    label: nav.groups.overview,
    children: [{ key: "/", icon: <DashboardOutlined />, label: nav.items.dashboard }],
  },
  {
    type: "group",
    label: nav.groups.resources,
    children: [
      { key: "/tenants", icon: <TeamOutlined />, label: nav.items.tenants },
      { key: "/sites", icon: <EnvironmentOutlined />, label: nav.items.sites },
      { key: "/devices", icon: <ClusterOutlined />, label: nav.items.devices },
    ],
  },
  {
    type: "group",
    label: nav.groups.circuits,
    children: [
      { key: "/catalog", icon: <AppstoreOutlined />, label: nav.items.catalog },
      { key: "/circuits", icon: <ApiOutlined />, label: nav.items.circuits },
      { key: "/work-orders", icon: <ProfileOutlined />, label: nav.items.workOrders },
    ],
  },
  {
    type: "group",
    label: nav.groups.network,
    children: [
      { key: "/controllers", icon: <CloudServerOutlined />, label: nav.items.controllers },
      { key: "/control-plane", icon: <ShareAltOutlined />, label: nav.items.controlPlane },
      { key: "/config", icon: <FileTextOutlined />, label: nav.items.config },
      { key: "/topology", icon: <PartitionOutlined />, label: nav.items.topology },
    ],
  },
  {
    type: "group",
    label: nav.groups.ops,
    children: [
      { key: "/capacity", icon: <DeploymentUnitOutlined />, label: nav.items.capacity },
      { key: "/monitoring", icon: <LineChartOutlined />, label: nav.items.monitoring },
      { key: "/alarms", icon: <AlertOutlined />, label: nav.items.alarms },
    ],
  },
  {
    type: "group",
    label: nav.groups.system,
    children: [
      { key: "/settings", icon: <SettingOutlined />, label: nav.items.settings },
      { key: "/notifications", icon: <BellOutlined />, label: nav.items.notifications },
      { key: "/integrations", icon: <IntegrationIcon />, label: nav.items.integrations },
      { key: "/users", icon: <SafetyOutlined />, label: nav.items.users },
      { key: "/audit", icon: <AuditOutlined />, label: nav.items.audit },
    ],
  },
];

const ROUTE_KEYS = MENU.flatMap((g) =>
  g && "children" in g && g.children ? g.children.map((c) => (c as { key: string }).key) : []
);

function selectedMenuKey(pathname: string): string {
  const match = ROUTE_KEYS.filter((k) => k !== "/")
    .sort((a, b) => b.length - a.length)
    .find((k) => pathname.startsWith(k));
  if (match) return match;
  return pathname === "/" ? "/" : ROUTE_KEYS.find((k) => k === pathname) || "/";
}

function AlarmBell({ onClick }: { onClick: () => void }) {
  const [count, setCount] = useState(0);
  const [live, setLive] = useState(false);

  useEffect(() => {
    const token = getToken();
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    async function loadOnce() {
      try {
        const { data } = await api.get("/alarms/summary");
        setCount(data.active || 0);
      } catch {
        /* ignore */
      }
    }

    if (token && "EventSource" in window) {
      es = new EventSource(`/api/v1/stream/events?token=${encodeURIComponent(token)}`);
      es.addEventListener("snapshot", (e: MessageEvent) => {
        try {
          const d = JSON.parse(e.data);
          setCount(d.active_alarms || 0);
          setLive(true);
        } catch {
          /* ignore */
        }
      });
      es.onerror = () => {
        // Fall back to polling if the stream drops.
        setLive(false);
        if (!poll) poll = setInterval(loadOnce, 8000);
      };
    } else {
      loadOnce();
      poll = setInterval(loadOnce, 8000);
    }

    return () => {
      es?.close();
      if (poll) clearInterval(poll);
    };
  }, []);

  return (
    <Badge count={count} size="small" offset={[-2, 2]} title={live ? "SSE 实时" : "轮询同步"}>
      <AlertOutlined
        style={{ fontSize: 20, cursor: "pointer", color: count ? "#cf1322" : undefined }}
        onClick={onClick}
      />
    </Badge>
  );
}

function Shell() {
  const navTo = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const { brand } = useBrand();
  const selected = selectedMenuKey(loc.pathname);

  return (
    <Layout style={{ height: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark">
        <div className="app-logo">
          <BrandLogo brand={brand} variant="sidebar" height={24} />
          <span>{brand.product_name}</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={MENU}
          onClick={(e) => navTo(e.key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingInline: 24,
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {brand.header_title}
          </div>
          <Space size="large">
          <AlarmBell onClick={() => navTo("/alarms")} />
          <Dropdown
            menu={{
              items: [
                  { key: "logout", icon: <LogoutOutlined />, label: "退出", onClick: logout },
              ],
            }}
          >
            <span style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
              <Avatar size="small" icon={<UserOutlined />} />
              {user?.full_name || user?.username}
              <Tag color="blue">{user?.role}</Tag>
            </span>
          </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 16, overflow: "auto" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tenants" element={<Tenants />} />
            <Route path="/sites" element={<Sites />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/controllers" element={<Controllers />} />
            <Route path="/control-plane" element={<ControlPlane />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/circuits" element={<Circuits />} />
            <Route path="/work-orders" element={<WorkOrders />} />
            <Route path="/config" element={<ConfigManagement />} />
            <Route path="/topology" element={<Topology />} />
            <Route path="/capacity" element={<Capacity />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/alarms" element={<Alarms />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/users" element={<Users />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  const { user, ready } = useAuth();

  if (!ready) {
    return (
      <div style={{ height: "100vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/*" element={user ? <Shell /> : <Navigate to="/login" replace />} />
    </Routes>
  );
}
