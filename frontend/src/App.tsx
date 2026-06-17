import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  MapPin,
  Server,
  Cable,
  ClipboardList,
  Cloud,
  Share2,
  FileText,
  Network,
  Gauge,
  LineChart,
  Bell,
  Settings,
  LogOut,
  Menu,
  ChevronRight,
  KeyRound,
} from "lucide-react";
import { useMemo, useState, useEffect } from "react";
import PortalApp from "./portal/PortalApp";
import { isTenantAccount, useAuth } from "./auth";
import { api, getToken, fetchStreamTicket } from "./api/client";
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
import Controllers from "./pages/Controllers";
import ControlPlane from "./pages/ControlPlane";
import ConfigManagement from "./pages/ConfigManagement";
import Notifications from "./pages/Notifications";
import UsersPage from "./pages/Users";
import Audit from "./pages/Audit";
import SettingsLayout from "./pages/settings/SettingsLayout";
import GeneralSettings from "./pages/settings/GeneralSettings";
import AlarmSettings from "./pages/settings/AlarmSettings";
import BaselineSettings from "./pages/settings/BaselineSettings";
import SmtpSettings from "./pages/settings/SmtpSettings";
import SnmpSettingsTab from "./pages/settings/SnmpSettingsTab";
import ManagementSettings from "./pages/settings/ManagementSettings";
import BrandSettings from "./pages/settings/BrandSettings";
import IntegrationSettings from "./pages/settings/IntegrationSettings";
import SecuritySettings from "./pages/settings/SecuritySettings";
import { nav, action } from "./constants/uiCopy";
import { useBrand } from "./context/BrandContext";
import { BrandLogo } from "./components/BrandLogo";
import ChangePasswordDialog from "./components/ChangePasswordDialog";
import OperationalBanner from "./components/OperationalBanner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

type NavItem = { key: string; label: string; icon: React.ReactNode };
type NavGroup = { label: string; items: NavItem[] };

const MENU: NavGroup[] = [
  {
    label: nav.groups.overview,
    items: [{ key: "/", label: nav.items.dashboard, icon: <LayoutDashboard className="h-4 w-4" /> }],
  },
  {
    label: nav.groups.resources,
    items: [{ key: "/tenants", label: nav.items.tenants, icon: <Users className="h-4 w-4" /> }],
  },
  {
    label: nav.groups.circuits,
    items: [
      { key: "/circuits", label: nav.items.circuits, icon: <Cable className="h-4 w-4" /> },
      { key: "/work-orders", label: nav.items.workOrders, icon: <ClipboardList className="h-4 w-4" /> },
    ],
  },
  {
    label: nav.groups.network,
    items: [
      { key: "/sites", label: nav.items.sites, icon: <MapPin className="h-4 w-4" /> },
      { key: "/devices", label: nav.items.devices, icon: <Server className="h-4 w-4" /> },
      { key: "/topology", label: nav.items.topology, icon: <Network className="h-4 w-4" /> },
      { key: "/controllers", label: nav.items.controllers, icon: <Cloud className="h-4 w-4" /> },
      { key: "/control-plane", label: nav.items.controlPlane, icon: <Share2 className="h-4 w-4" /> },
      { key: "/config", label: nav.items.config, icon: <FileText className="h-4 w-4" /> },
    ],
  },
  {
    label: nav.groups.ops,
    items: [
      { key: "/monitoring", label: nav.items.monitoring, icon: <LineChart className="h-4 w-4" /> },
      { key: "/alarms", label: nav.items.alarms, icon: <Bell className="h-4 w-4" /> },
      { key: "/capacity", label: nav.items.capacity, icon: <Gauge className="h-4 w-4" /> },
    ],
  },
  {
    label: nav.groups.system,
    items: [{ key: "/settings", label: nav.items.settings, icon: <Settings className="h-4 w-4" /> }],
  },
];

const ROUTE_KEYS = MENU.flatMap((g) => g.items.map((i) => i.key));

const PAGE_TITLE: Record<string, string> = MENU.reduce((acc, g) => {
  g.items.forEach((i) => {
    acc[i.key] = i.label;
  });
  return acc;
}, {} as Record<string, string>);

function selectedMenuKey(pathname: string): string {
  if (pathname.startsWith("/settings")) return "/settings";
  const match = ROUTE_KEYS.filter((k) => k !== "/")
    .sort((a, b) => b.length - a.length)
    .find((k) => pathname.startsWith(k));
  if (match) return match;
  return pathname === "/" ? "/" : ROUTE_KEYS.find((k) => k === pathname) || "/";
}

function AlarmBell({ onClick }: { onClick: () => void }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    async function loadOnce() {
      try {
        const { data } = await api.get("/alarms/summary");
        setCount(data.active || 0);
      } catch {
        /* ignore */
      }
    }

    async function connectSse() {
      try {
        const ticket = await fetchStreamTicket();
        if (cancelled || !("EventSource" in window)) return;
        es = new EventSource(`/api/v1/stream/events?ticket=${encodeURIComponent(ticket)}`);
        es.addEventListener("snapshot", (e: MessageEvent) => {
          try {
            const d = JSON.parse(e.data);
            setCount(d.active_alarms || 0);
          } catch {
            /* ignore */
          }
        });
        es.onerror = () => {
          es?.close();
          es = null;
          if (!poll) poll = setInterval(loadOnce, 8000);
        };
      } catch {
        if (!poll) poll = setInterval(loadOnce, 8000);
      }
    }

    if (getToken()) {
      connectSse();
    } else {
      loadOnce();
      poll = setInterval(loadOnce, 8000);
    }

    return () => {
      cancelled = true;
      es?.close();
      if (poll) clearInterval(poll);
    };
  }, []);

  return (
    <Button variant="ghost" size="icon" className="relative" onClick={onClick}>
      <Bell className={cn("h-5 w-5", count > 0 && "text-destructive")} />
      {count > 0 ? (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-white">
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </Button>
  );
}

function Shell() {
  const navTo = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const { brand } = useBrand();
  const selected = useMemo(() => selectedMenuKey(loc.pathname), [loc.pathname]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

  const sidebar = (
    <aside className="flex h-full w-60 shrink-0 flex-col bg-slate-950 text-slate-100 shadow-[4px_0_24px_rgba(0,0,0,0.12)]">
      <div className="flex h-14 items-center gap-2 px-4">
        <BrandLogo brand={brand} variant="sidebar" height={24} />
        <span className="truncate text-sm font-semibold tracking-wide">{brand.product_name}</span>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {MENU.map((group) => (
          <div key={group.label} className="mb-4">
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = selected === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      navTo(item.key);
                      setMobileOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-slate-300 hover:bg-white/10 hover:text-white",
                    )}
                  >
                    {item.icon}
                    <span className="truncate">{item.label}</span>
                    {active ? <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-70" /> : null}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <div className="hidden lg:block">{sidebar}</div>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="relative h-full w-60">{sidebar}</div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between bg-card px-4 shadow-[0_1px_0_rgba(15,23,42,0.04)] lg:px-6">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)}>
              <Menu className="h-5 w-5" />
            </Button>
            <h1 className="text-base font-semibold text-foreground">
              {PAGE_TITLE[selected] || brand.header_title}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <AlarmBell onClick={() => navTo("/alarms")} />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2 px-2">
                  <span className="hidden max-w-[120px] truncate sm:inline">{user?.full_name || user?.username}</span>
                  <Badge variant="secondary" className="font-normal">
                    {user?.role}
                  </Badge>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setChangePasswordOpen(true)}>
                  <KeyRound className="mr-2 h-4 w-4" />
                  {action.changePassword}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  {action.logout}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <ChangePasswordDialog open={changePasswordOpen} onClose={() => setChangePasswordOpen(false)} />
          </div>
        </header>

        <main className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-auto bg-slate-100/80">
          <OperationalBanner />
          <div className="flex min-h-0 flex-1 flex-col p-4 lg:p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tenants" element={<Tenants />} />
            <Route path="/sites" element={<Sites />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/controllers" element={<Controllers />} />
            <Route path="/control-plane" element={<ControlPlane />} />
            <Route path="/catalog" element={<Navigate to="/circuits" replace />} />
            <Route path="/circuits" element={<Circuits />} />
            <Route path="/work-orders" element={<WorkOrders />} />
            <Route path="/config" element={<ConfigManagement />} />
            <Route path="/topology" element={<Topology />} />
            <Route path="/capacity" element={<Capacity />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/alarms" element={<Alarms />} />
            <Route path="/settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="brand" replace />} />
              <Route path="brand" element={<BrandSettings />} />
              <Route path="general" element={<GeneralSettings />} />
              <Route path="alarms" element={<AlarmSettings />} />
              <Route path="baseline" element={<BaselineSettings />} />
              <Route path="smtp" element={<SmtpSettings />} />
              <Route path="management" element={<ManagementSettings />} />
              <Route path="snmp" element={<SnmpSettingsTab />} />
              <Route path="integration" element={<IntegrationSettings />} />
              <Route path="security" element={<SecuritySettings />} />
              <Route path="notifications" element={<Notifications embedded />} />
              <Route path="users" element={<UsersPage embedded />} />
              <Route path="audit" element={<Audit embedded />} />
            </Route>
            <Route path="/notifications" element={<Navigate to="/settings/notifications" replace />} />
            <Route path="/integrations" element={<Navigate to="/settings/integration" replace />} />
            <Route path="/users" element={<Navigate to="/settings/users" replace />} />
            <Route path="/audit" element={<Navigate to="/settings/audit" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const { user, ready, isTenantUser } = useAuth();

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const tenant = isTenantUser || isTenantAccount(user);

  return (
    <Routes>
      <Route
        path="/login"
        element={
          user ? <Navigate to={tenant ? "/portal" : "/"} replace /> : <Login />
        }
      />
      <Route
        path="/portal/*"
        element={
          user ? tenant ? <PortalApp /> : <Navigate to="/" replace /> : <Navigate to="/login" replace />
        }
      />
      <Route
        path="/*"
        element={
          user ? tenant ? <Navigate to="/portal" replace /> : <Shell /> : <Navigate to="/login" replace />
        }
      />
    </Routes>
  );
}
