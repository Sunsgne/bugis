import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Spin, Dropdown, Avatar, Tag } from "antd";
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
} from "@ant-design/icons";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Tenants from "./pages/Tenants";
import Sites from "./pages/Sites";
import Devices from "./pages/Devices";
import Circuits from "./pages/Circuits";
import WorkOrders from "./pages/WorkOrders";
import Monitoring from "./pages/Monitoring";

const { Header, Sider, Content } = Layout;

const MENU = [
  { key: "/", icon: <DashboardOutlined />, label: "运营总览" },
  { key: "/tenants", icon: <TeamOutlined />, label: "租户管理" },
  { key: "/sites", icon: <EnvironmentOutlined />, label: "数据中心" },
  { key: "/devices", icon: <ClusterOutlined />, label: "设备管理" },
  { key: "/circuits", icon: <ApiOutlined />, label: "专线管理" },
  { key: "/work-orders", icon: <ProfileOutlined />, label: "工单流转" },
  { key: "/monitoring", icon: <LineChartOutlined />, label: "监控大屏" },
];

function Shell() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const selected = MENU.find(
    (m) => m.key === loc.pathname || (m.key !== "/" && loc.pathname.startsWith(m.key))
  );

  return (
    <Layout style={{ height: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark">
        <div className="app-logo">
          <span className="dot" />
          <span>Bugis 专线运营</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected?.key || "/"]}
          items={MENU}
          onClick={(e) => nav(e.key)}
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
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            DCI / EVPN 专线开通与运营平台
          </div>
          <Dropdown
            menu={{
              items: [
                { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: logout },
              ],
            }}
          >
            <span style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
              <Avatar size="small" icon={<UserOutlined />} />
              {user?.full_name || user?.username}
              <Tag color="blue">{user?.role}</Tag>
            </span>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16, overflow: "auto" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tenants" element={<Tenants />} />
            <Route path="/sites" element={<Sites />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/circuits" element={<Circuits />} />
            <Route path="/work-orders" element={<WorkOrders />} />
            <Route path="/monitoring" element={<Monitoring />} />
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
