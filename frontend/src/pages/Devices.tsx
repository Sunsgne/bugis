import { zodResolver } from "@hookform/resolvers/zod";
import {
  ApiOutlined,
  BookOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  DownloadOutlined,
  KeyOutlined,
  NodeIndexOutlined,
  PlusOutlined,
  RadarChartOutlined,
  RocketOutlined,
  SearchOutlined,
  SettingOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Drawer,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { api } from "../api/client";
import type {
  Device,
  DeviceInterface,
  ManagementDefaults,
  Paginated,
  Site,
  SnmpDefaults,
  SvidUsage,
} from "../api/types";
import { ConfigPreviewPre } from "../utils/configPreview";
import {
  DEVICE_ROLE_OPTIONS,
  labelForOption,
  MANAGEMENT_TRANSPORT_OPTIONS,
  SNMP_V3_SECURITY_OPTIONS,
  SNMP_VERSION_OPTIONS,
} from "../constants/formOptions";
import { action, page as pageCopy, toast as toastCopy } from "../constants/uiCopy";
import { buildListQuery, dataTableProps, tablePagination } from "../utils/table";
import { PageCard } from "@/components";
import ListToolbar from "../components/ListToolbar";
import DeviceFormDialog, { type DeviceFormValues } from "@/components/DeviceFormDialog";
import FormSelect from "@/components/FormSelect";
import { Alert as UiAlert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
import { Input as UiInput } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Switch as UiSwitch } from "@/components/ui/switch";
import { Button as UiButton } from "@/components/ui/button";

const VENDOR_SHORT: Record<string, string> = {
  h3c: "H3C",
  huawei: "Huawei",
  juniper: "Juniper",
  arista: "Arista",
  cisco: "Cisco",
  frr: "FRR",
};

const DEVICE_STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  maintenance: "orange",
  unknown: "default",
};

const DEVICE_STATUS_LABEL: Record<string, string> = {
  online: "在线",
  offline: "离线",
  maintenance: "维护",
  unknown: "未知",
};

const SVID_SOURCE_COLOR: Record<string, string> = {
  legacy: "red",
  device: "orange",
};

const FALLBACK_SNMP: SnmpDefaults = {
  enabled: true,
  port: 161,
  community: "bugis-ro",
  version: "2c",
};

const FALLBACK_MGMT: ManagementDefaults = {
  netconf_port: 830,
  ssh_port: 22,
  username: "admin",
  management_transport: "auto",
  netconf_timeout: 30,
  ssh_timeout: 30,
  snmp: FALLBACK_SNMP,
};

const credSchema = z.object({
  management_transport: z.string(),
  username: z.string().optional(),
  password: z.string().optional(),
  enable_password: z.string().optional(),
  netconf_port: z.coerce.number(),
  ssh_port: z.coerce.number(),
  netmiko_device_type: z.string().optional(),
  snmp_enabled: z.boolean(),
  snmp_community: z.string().optional(),
  snmp_port: z.coerce.number(),
  snmp_version: z.string(),
  snmp_v3_username: z.string().optional(),
  snmp_v3_security_level: z.string().optional(),
  snmp_v3_auth_password: z.string().optional(),
  snmp_v3_priv_password: z.string().optional(),
});

type CredFormValues = z.infer<typeof credSchema>;

function renderSvidUsage(list?: SvidUsage[] | null) {
  if (!list?.length) return <Typography.Text type="secondary">—</Typography.Text>;
  return (
    <Space size={[4, 4]} wrap>
      {list.map((u, idx) => {
        const label =
          u.access_mode === "access"
            ? "untagged"
            : u.c_vid
              ? `S:${u.s_vid}/C:${u.c_vid}`
              : `S:${u.s_vid}`;
        const tip = [u.circuit_code && `专线 ${u.circuit_code}`, u.source && `来源 ${u.source}`, u.note]
          .filter(Boolean)
          .join(" · ");
        return (
          <Tooltip key={idx} title={tip || label}>
            <Tag color={SVID_SOURCE_COLOR[u.source || ""] || "blue"}>{label}</Tag>
          </Tooltip>
        );
      })}
    </Space>
  );
}

type CredentialEditDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device: Device | null;
  mgmtDefaults: ManagementDefaults;
  snmpDefaults: SnmpDefaults;
  onSave: (deviceId: number, values: CredFormValues) => Promise<void>;
};

function CredentialEditDialog({
  open,
  onOpenChange,
  device,
  mgmtDefaults,
  snmpDefaults,
  onSave,
}: CredentialEditDialogProps) {
  const form = useForm<CredFormValues>({
    resolver: zodResolver(credSchema) as Resolver<CredFormValues>,
    defaultValues: {
      management_transport: "auto",
      snmp_enabled: true,
      snmp_port: snmpDefaults.port,
      snmp_version: snmpDefaults.version,
      snmp_v3_security_level: "authPriv",
      netconf_port: mgmtDefaults.netconf_port,
      ssh_port: mgmtDefaults.ssh_port,
    },
  });

  const watchSnmpVersion = form.watch("snmp_version");

  useEffect(() => {
    if (open && device) {
      form.reset({
        management_transport: device.management_transport || "auto",
        username: device.username || "",
        netconf_port: device.netconf_port ?? mgmtDefaults.netconf_port,
        ssh_port: device.ssh_port ?? mgmtDefaults.ssh_port,
        netmiko_device_type: device.netmiko_device_type || "",
        password: "",
        enable_password: "",
        snmp_enabled: device.snmp_enabled !== false,
        snmp_community: "",
        snmp_port: device.snmp_port ?? snmpDefaults.port,
        snmp_version: device.snmp_version || snmpDefaults.version,
        snmp_v3_username: device.snmp_v3_username || "",
        snmp_v3_security_level: device.snmp_v3_security_level || "authPriv",
        snmp_v3_auth_password: "",
        snmp_v3_priv_password: "",
      });
    }
  }, [open, device, mgmtDefaults, snmpDefaults, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,900px)] max-w-xl flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 text-left">
          <DialogTitle>{device ? `设备凭证 · ${device.name}` : "设备凭证"}</DialogTitle>
          <DialogDescription>留空密码则保持原值，SNMP Community 与登录密码相互独立。</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <Form {...form}>
            <form
              id="device-cred-form"
              className="space-y-4 px-6 py-5"
              onSubmit={form.handleSubmit(async (v) => {
                if (device) await onSave(device.id, v);
              })}
            >
              <UiAlert variant="warning">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>敏感字段不会回显</AlertTitle>
                <AlertDescription>留空密码则保持原值。SNMP Community 与登录密码已分离，可分别配置。</AlertDescription>
              </UiAlert>

              <FormField
                control={form.control}
                name="management_transport"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>配置下发传输</FormLabel>
                    <FormControl>
                      <FormSelect value={field.value} onValueChange={field.onChange} options={MANAGEMENT_TRANSPORT_OPTIONS} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>用户名</FormLabel>
                    <FormControl>
                      <UiInput placeholder="admin / netconf" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>登录密码 (NETCONF / SSH)</FormLabel>
                    <FormControl>
                      <UiInput type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="enable_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Enable 密码</FormLabel>
                    <FormControl>
                      <UiInput type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="netconf_port"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>NETCONF 端口</FormLabel>
                      <FormControl>
                        <UiInput type="number" min={1} max={65535} {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="ssh_port"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SSH 端口</FormLabel>
                      <FormControl>
                        <UiInput type="number" min={1} max={65535} {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="netmiko_device_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Netmiko 设备类型 (可选)</FormLabel>
                    <FormControl>
                      <UiInput placeholder="留空则按厂商自动选择" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />

              <Separator />

              <FormField
                control={form.control}
                name="snmp_enabled"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                    <FormLabel className="mt-0">启用 SNMP</FormLabel>
                    <FormControl>
                      <UiSwitch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="snmp_community"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Community (v2c)</FormLabel>
                      <FormControl>
                        <UiInput
                          placeholder={
                            device?.snmp_community_set ? "已配置 · 留空不修改" : snmpDefaults.community
                          }
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="snmp_port"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>UDP 端口</FormLabel>
                      <FormControl>
                        <UiInput type="number" min={1} max={65535} {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="snmp_version"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>版本</FormLabel>
                      <FormControl>
                        <FormSelect value={field.value} onValueChange={field.onChange} options={SNMP_VERSION_OPTIONS} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              {watchSnmpVersion === "3" ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="snmp_v3_username"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>SNMPv3 用户名</FormLabel>
                        <FormControl>
                          <UiInput {...field} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="snmp_v3_security_level"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>安全级别</FormLabel>
                        <FormControl>
                          <FormSelect
                            value={field.value || "authPriv"}
                            onValueChange={field.onChange}
                            options={SNMP_V3_SECURITY_OPTIONS}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="snmp_v3_auth_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>认证密码</FormLabel>
                        <FormControl>
                          <UiInput type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="snmp_v3_priv_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>加密密码</FormLabel>
                        <FormControl>
                          <UiInput type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>
              ) : null}
            </form>
          </Form>
        </div>

        <DialogFooter className="shrink-0 border-t px-6 py-4">
          <UiButton type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {action.cancel}
          </UiButton>
          <UiButton type="submit" form="device-cred-form">
            {action.save}
          </UiButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Devices() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [credOpen, setCredOpen] = useState(false);
  const [credDevice, setCredDevice] = useState<Device | null>(null);
  const [snmpDefaults, setSnmpDefaults] = useState<SnmpDefaults>(FALLBACK_SNMP);
  const [mgmtDefaults, setMgmtDefaults] = useState<ManagementDefaults>(FALLBACK_MGMT);
  const [learnOnImport, setLearnOnImport] = useState(true);
  const [drawerDevice, setDrawerDevice] = useState<Device | null>(null);
  const [ifaces, setIfaces] = useState<DeviceInterface[]>([]);
  const [ifacesLoading, setIfacesLoading] = useState(false);
  const [initOpen, setInitOpen] = useState(false);
  const [initDevice, setInitDevice] = useState<Device | null>(null);
  const [initBaseline, setInitBaseline] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const siteName = useCallback((id?: number) => sites.find((s) => s.id === id)?.code || "-", [sites]);

  async function loadIfaces(deviceId: number, refresh = false) {
    setIfacesLoading(true);
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`, {
        params: refresh ? { scan: true } : undefined,
      });
      setIfaces(data);
    } finally {
      setIfacesLoading(false);
    }
  }

  async function openPorts(device: Device) {
    setDrawerDevice(device);
    setIfaces([]);
    await loadIfaces(device.id, true);
  }

  async function load(p = page, ps = pageSize, q = search) {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([
        api.get<Paginated<Device>>(`/devices${buildListQuery({ page: p, page_size: ps, q: q || undefined })}`),
        api.get<Site[]>("/sites"),
      ]);
      setRows(d.data.items);
      setTotal(d.data.total);
      setSites(s.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize]);

  async function openCreateModal() {
    let mgmt = FALLBACK_MGMT;
    try {
      const { data } = await api.get<ManagementDefaults>("/system/management-defaults");
      mgmt = data;
      setMgmtDefaults(data);
      setSnmpDefaults(data.snmp);
    } catch {
      setMgmtDefaults(FALLBACK_MGMT);
      setSnmpDefaults(FALLBACK_SNMP);
    }
    setOpen(true);
  }

  async function onCreate(values: DeviceFormValues) {
    const payload: Record<string, unknown> = { ...values };
    if (!payload.password) delete payload.password;
    if (!payload.snmp_enabled) {
      payload.snmp_community = null;
    } else if (payload.snmp_community === snmpDefaults.community) {
      payload.snmp_community = null;
    }
    try {
      await api.post("/devices", payload);
      message.success("设备已纳管");
      setOpen(false);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  function openCredEdit(d: Device) {
    setCredDevice(d);
    setCredOpen(true);
  }

  async function saveCred(deviceId: number, v: CredFormValues) {
    const payload: Record<string, unknown> = {
      management_transport: v.management_transport,
      username: v.username || null,
      netconf_port: v.netconf_port,
      ssh_port: v.ssh_port,
      netmiko_device_type: v.netmiko_device_type || null,
      snmp_enabled: v.snmp_enabled,
      snmp_port: v.snmp_port,
      snmp_version: v.snmp_version,
      snmp_v3_username: v.snmp_v3_username || null,
      snmp_v3_security_level: v.snmp_v3_security_level || null,
      snmp_v3_auth_protocol: credDevice?.snmp_v3_auth_protocol || "SHA",
      snmp_v3_priv_protocol: credDevice?.snmp_v3_priv_protocol || "AES",
    };
    if (v.password) payload.password = v.password;
    if (v.enable_password) payload.enable_password = v.enable_password;
    if (v.snmp_community) payload.snmp_community = v.snmp_community;
    if (v.snmp_v3_auth_password) payload.snmp_v3_auth_password = v.snmp_v3_auth_password;
    if (v.snmp_v3_priv_password) payload.snmp_v3_priv_password = v.snmp_v3_priv_password;
    try {
      await api.patch(`/devices/${deviceId}`, payload);
      message.success(toastCopy.saved);
      setCredOpen(false);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/devices/${id}`);
    message.success(toastCopy.deleted);
    load();
  }

  async function exportCsv() {
    const { data } = await api.get("/bulk/devices/export", { responseType: "text" });
    const blob = new Blob([data], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "devices.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function importCsv(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/bulk/devices/import", fd, {
        params: { learn: learnOnImport },
      });
      const learnMsg =
        data.learn_enabled && data.learn
          ? ` · 现网学习 ${data.learn.success}/${data.learn.total} 成功`
          : "";
      message.success(`导入完成 · 新增 ${data.created} · 跳过 ${data.skipped}${learnMsg}`);
      if (data.errors?.length) message.warning(`${data.errors.length} 行需修正`);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function discover(deviceId: number) {
    const hide = message.loading("SNMP 接口扫描中…", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      hide();
      const simCount = data.filter((i) => i.discovered_via === "snmp-sim").length;
      const svidCount = data.filter((i) => i.used_s_vids?.length).length;
      if (simCount === data.length) {
        message.warning(
          "返回的是模拟数据（设备 SNMP 不可达或 Community 错误）。请检查管理 IP、UDP 161 与 Community 后重试",
        );
      } else if (simCount > 0) {
        message.warning(`部分接口为模拟数据（${simCount}/${data.length}），请检查 SNMP 配置`);
      } else {
        message.success(`SNMP 发现 ${data.length} 个接口 · ${svidCount} 个端口有 S-VID 占用`);
      }
      if (svidCount === 0 && simCount < data.length) {
        message.info("S-VID 需从 running-config 解析，请执行「现网学习」后重新检测");
      }
      setIfaces(data);
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function learnConfig(d: Device) {
    const hide = message.loading(`现网配置学习中 · ${d.name}...`, 0);
    try {
      const { data } = await api.post(`/devices/${d.id}/learn`);
      hide();
      if (data.success) {
        const inv = data.inventory;
        message.success(
          `${d.name} 学习完成 · ${inv?.service_count ?? 0} 个业务 · v${data.snapshot_version}`,
        );
        if (data.svid_scan?.ports_scanned || drawerDevice?.id === d.id) {
          await loadIfaces(d.id, true);
        }
      } else {
        message.error(data.error || toastCopy.failed);
      }
      load();
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function initialize(d: Device) {
    try {
      const { data: bl } = await api.get<{ content: string }>(`/devices/${d.id}/baseline`);
      setInitDevice(d);
      setInitBaseline(bl.content);
      setInitOpen(true);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function confirmInitialize() {
    if (!initDevice) return;
    setInitLoading(true);
    try {
      const { data } = await api.post(`/devices/${initDevice.id}/initialize`);
      message.success(`${data.device} 初始化完成 · v${data.version} · ${data.transport}`);
      setInitOpen(false);
      setInitDevice(null);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    } finally {
      setInitLoading(false);
    }
  }

  async function check(id: number) {
    const hide = message.loading("可达性探测 · S-VID 扫描中…", 0);
    try {
      const { data } = await api.post(`/devices/${id}/check`);
      hide();
      if (data.reachable) {
        const scan = data.svid_scan;
        const svidCount = scan?.total_s_vids ?? 0;
        const conflictCount = scan?.conflicts?.length ?? 0;
        if (conflictCount > 0) {
          message.warning(
            `${data.device} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`,
          );
        } else {
          message.success(
            `${data.device} 可达 (${data.latency_ms}ms) · 已扫描 ${svidCount} 个 S-VID 占用`,
          );
        }
        if (drawerDevice?.id === id && scan?.ports?.length) {
          const ports = scan.ports as Array<{
            interface: string;
            s_vids: SvidUsage[];
            allocated: boolean;
          }>;
          const byName = Object.fromEntries(ports.map((row) => [row.interface, row]));
          setIfaces((existing) => {
            const merged = existing.map((iface) => {
              const hit = byName[iface.name];
              if (!hit) return iface;
              return { ...iface, used_s_vids: hit.s_vids, allocated: hit.allocated };
            });
            for (const row of ports) {
              if (!merged.some((i) => i.name === row.interface)) {
                merged.push({
                  id: -1,
                  device_id: id,
                  name: row.interface,
                  admin_up: true,
                  allocated: row.allocated,
                  used_s_vids: row.s_vids,
                } as DeviceInterface);
              }
            }
            return merged;
          });
        }
      } else {
        message.error(`${data.device} 不可达 (${data.mgmt_ip})`);
      }
      load();
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  const ifaceHasSvid = ifaces.some((i) => (i.used_s_vids?.length ?? 0) > 0);

  const stats = useMemo(() => {
    const online = rows.filter((r) => r.status === "online").length;
    const offline = rows.filter((r) => r.status === "offline").length;
    return { online, offline };
  }, [rows]);

  function runSearch() {
    setPage(1);
    load(1, pageSize, search);
  }

  return (
    <PageCard
      title={pageCopy.devices}
      description="多厂商 Fabric 纳管 · SNMP / NETCONF / SSH"
      extra={
        <Space wrap>
          <Link to="/settings/management">
            <Button icon={<SettingOutlined />}>南向</Button>
          </Link>
          <Link to="/settings/snmp">
            <Button icon={<SettingOutlined />}>SNMP</Button>
          </Link>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            导出 CSV
          </Button>
          <input
            ref={importRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void importCsv(file);
              e.target.value = "";
            }}
          />
          <Button icon={<UploadOutlined />} onClick={() => importRef.current?.click()}>
            导入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            纳管设备
          </Button>
        </Space>
      }
    >
      <ListToolbar
        summary={`共 ${total.toLocaleString()} 台设备${total > pageSize ? " · 已分页" : ""}`}
        left={
          <>
            <Input.Search
              allowClear
              placeholder="搜索名称或管理 IP"
              style={{ width: 260 }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onSearch={runSearch}
              enterButton={<SearchOutlined />}
            />
            <Space size={4}>
              <Typography.Text type="secondary">导入即学习</Typography.Text>
              <Switch checked={learnOnImport} onChange={setLearnOnImport} size="small" />
            </Space>
          </>
        }
      />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="设备总数" value={total} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="在线" value={stats.online} valueStyle={{ color: "#3f8600" }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="离线" value={stats.offline} valueStyle={{ color: stats.offline ? "#cf1322" : undefined }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="当前页"
              value={rows.length}
              suffix={total > pageSize ? `/ ${pageSize}` : undefined}
            />
          </Card>
        </Col>
      </Row>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        locale={{ emptyText: "暂无设备 · 从导入或纳管开始" }}
        {...dataTableProps(1180, rows.length > 0)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={[
          {
            title: "设备",
            dataIndex: "name",
            width: 180,
            ellipsis: true,
            render: (name: string, d: Device) => (
              <Tooltip
                title={
                  [d.hostname, d.loopback_ip && `Loopback ${d.loopback_ip}`, d.bgp_asn && `AS ${d.bgp_asn}`]
                    .filter(Boolean)
                    .join(" · ") || name
                }
              >
                <div>
                  <div style={{ fontWeight: 500 }}>{name}</div>
                  {d.model ? (
                    <Typography.Text type="secondary" ellipsis style={{ fontSize: 12 }}>
                      {d.model}
                    </Typography.Text>
                  ) : null}
                </div>
              </Tooltip>
            ),
          },
          {
            title: "厂商",
            dataIndex: "vendor",
            width: 96,
            render: (v: string) => <Tag>{VENDOR_SHORT[v] || v}</Tag>,
          },
          {
            title: "角色",
            dataIndex: "role",
            width: 72,
            render: (r: string) => labelForOption(DEVICE_ROLE_OPTIONS, r).split(" ")[0],
          },
          {
            title: "管理 IP",
            dataIndex: "mgmt_ip",
            width: 130,
            render: (ip: string) => <Typography.Text code>{ip}</Typography.Text>,
          },
          {
            title: "站点",
            width: 88,
            ellipsis: true,
            render: (_: unknown, r: Device) => siteName(r.site_id),
          },
          {
            title: "凭证",
            width: 56,
            align: "center",
            render: (_: unknown, r: Device) =>
              r.password_set || r.username ? (
                <CheckCircleOutlined style={{ color: "#52c41a" }} />
              ) : (
                <CloseCircleOutlined style={{ color: "#d9d9d9" }} />
              ),
          },
          {
            title: "SNMP",
            width: 72,
            render: (_: unknown, r: Device) =>
              r.snmp_enabled === false ? (
                <Typography.Text type="secondary">—</Typography.Text>
              ) : (
                <Tag color="geekblue">v{r.snmp_version || "2c"}</Tag>
              ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 88,
            render: (s: string) => (
              <Tag color={DEVICE_STATUS_COLOR[s] || "default"}>
                {DEVICE_STATUS_LABEL[s] || s}
              </Tag>
            ),
          },
          {
            title: "操作",
            width: 320,
            className: "table-actions",
            render: (_: unknown, r: Device) => (
              <Space wrap>
                <Tooltip title="端口清单与 S-VID 占用">
                  <Button size="small" type="primary" icon={<ApiOutlined />} onClick={() => openPorts(r)}>
                    端口
                  </Button>
                </Tooltip>
                <Tooltip title="编辑登录 / SNMP 凭证">
                  <Button size="small" icon={<KeyOutlined />} onClick={() => openCredEdit(r)} />
                </Tooltip>
                <Tooltip title="现网配置学习">
                  <Button size="small" icon={<BookOutlined />} onClick={() => learnConfig(r)} />
                </Tooltip>
                <Tooltip title="基线初始化">
                  <Button size="small" icon={<RocketOutlined />} onClick={() => initialize(r)} />
                </Tooltip>
                <Tooltip title="可达性探测与 S-VID 扫描">
                  <Button size="small" icon={<RadarChartOutlined />} onClick={() => check(r.id)} />
                </Tooltip>
                <Tooltip title="SNMP 接口发现">
                  <Button size="small" icon={<NodeIndexOutlined />} onClick={() => discover(r.id)} />
                </Tooltip>
                <Popconfirm
                  title="确认删除该设备?"
                  description="此操作不可撤销，将永久删除该设备及其关联数据。"
                  onConfirm={() => remove(r.id)}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={drawerDevice ? `端口清单 · ${drawerDevice.name}` : "端口清单"}
        width="min(96vw, 1280px)"
        open={!!drawerDevice}
        onClose={() => setDrawerDevice(null)}
        destroyOnClose
        extra={
          drawerDevice ? (
            <Space wrap>
              <Button size="small" icon={<RadarChartOutlined />} onClick={() => check(drawerDevice.id)}>
                检测 S-VID
              </Button>
              <Button size="small" icon={<NodeIndexOutlined />} onClick={() => discover(drawerDevice.id)}>
                SNMP 发现
              </Button>
              <Button size="small" icon={<BookOutlined />} onClick={() => learnConfig(drawerDevice)}>
                现网学习
              </Button>
              <Button size="small" type="link" onClick={() => loadIfaces(drawerDevice.id, true)}>
                刷新占用
              </Button>
            </Space>
          ) : null
        }
      >
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          IF-MIB 端口与 S-VID 占用 · SNMP 发现接口，现网学习或检测刷新 VLAN 占用
        </Typography.Paragraph>

        {ifaces.some((i) => i.discovered_via === "snmp-sim") ? (
          <Alert
            type="warning"
            showIcon
            message="部分端口为模拟数据"
            description="snmp-sim 表示未从设备读到真实 IF-MIB。请确认 SNMP Community 与 UDP 161 可达后重新发现。"
            style={{ marginBottom: 12 }}
          />
        ) : null}

        {!ifacesLoading && ifaces.length > 0 && !ifaceHasSvid ? (
          <Alert
            type="info"
            showIcon
            message="暂无 S-VID 占用数据"
            description="S-VID 从 running-config（service-instance / dot1q 等）解析，SNMP 仅提供端口清单。请先执行「现网学习」拉取配置，再点「检测 S-VID」或「刷新占用」。"
            style={{ marginBottom: 12 }}
          />
        ) : null}

        <Table
          rowKey={(r) => `${r.device_id}-${r.name}`}
          size="small"
          loading={ifacesLoading}
          dataSource={ifaces}
          locale={{ emptyText: "暂无端口数据 · 先执行 SNMP 发现" }}
          pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ["20", "50", "100"] }}
          scroll={{ x: 960 }}
          columns={[
            {
              title: "接口",
              dataIndex: "name",
              width: 160,
              ellipsis: true,
              render: (name: string) => (
                <Tooltip title={name}>
                  <Typography.Text code ellipsis style={{ maxWidth: 140 }}>
                    {name}
                  </Typography.Text>
                </Tooltip>
              ),
            },
            {
              title: "描述",
              dataIndex: "description",
              width: 220,
              ellipsis: true,
              render: (d?: string) =>
                d ? (
                  <Tooltip title={d}>
                    <Typography.Text type="secondary" ellipsis style={{ maxWidth: 200 }}>
                      {d}
                    </Typography.Text>
                  </Tooltip>
                ) : (
                  "—"
                ),
            },
            {
              title: "速率",
              dataIndex: "speed_mbps",
              width: 72,
              render: (s?: number) => {
                if (!s) return "—";
                return <Tag>{s >= 1000 ? `${s / 1000}G` : `${s}M`}</Tag>;
              },
            },
            {
              title: "状态",
              dataIndex: "oper_status",
              width: 72,
              render: (s?: string) => (
                <Tag color={s === "up" ? "green" : "default"}>{s || "—"}</Tag>
              ),
            },
            {
              title: "ifIndex",
              dataIndex: "ifindex",
              width: 72,
              render: (v?: number) => (v != null ? v : "—"),
            },
            {
              title: "来源",
              dataIndex: "discovered_via",
              width: 88,
              render: (d?: string) => (d ? <Tag>{d}</Tag> : "—"),
            },
            {
              title: "S-VID 占用",
              dataIndex: "used_s_vids",
              width: 220,
              render: (list?: SvidUsage[]) => renderSvidUsage(list),
            },
            {
              title: "占用",
              dataIndex: "allocated",
              width: 72,
              render: (_: unknown, row: DeviceInterface) =>
                row.allocated || row.used_s_vids?.length ? (
                  <Tag color="orange">已占用</Tag>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </Drawer>

      <DeviceFormDialog
        open={open}
        onOpenChange={setOpen}
        sites={sites}
        mgmtDefaults={mgmtDefaults}
        snmpDefaults={snmpDefaults}
        onSubmit={onCreate}
      />

      <CredentialEditDialog
        open={credOpen}
        onOpenChange={setCredOpen}
        device={credDevice}
        mgmtDefaults={mgmtDefaults}
        snmpDefaults={snmpDefaults}
        onSave={saveCred}
      />

      <Modal
        title={initDevice ? `基线初始化 · ${initDevice.name} (${initDevice.vendor})` : "基线初始化"}
        open={initOpen}
        onCancel={() => !initLoading && setInitOpen(false)}
        onOk={confirmInitialize}
        okText={initLoading ? "下发中…" : "下发基线配置"}
        confirmLoading={initLoading}
        width={960}
        destroyOnClose
      >
        <Typography.Paragraph type="secondary">
          标准基线预览（管理 / Loopback / Underlay / EVPN Overlay）· 确认后 dry-run 下发并归档初始化快照
        </Typography.Paragraph>
        <ConfigPreviewPre>{initBaseline}</ConfigPreviewPre>
      </Modal>
    </PageCard>
  );
}
