import { zodResolver } from "@hookform/resolvers/zod";
import { ColumnDef } from "@tanstack/react-table";
import {
  AlertTriangle,
  BookOpen,
  Cable,
  Download,
  KeyRound,
  Network,
  Plus,
  Rocket,
  Search,
  Settings,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";
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
  VENDOR_OPTIONS,
} from "../constants/formOptions";
import { action, page as pageCopy, toast as toastCopy } from "../constants/uiCopy";
import { buildListQuery } from "../utils/table";
import { PageCard, ListToolbar } from "@/components";
import DataTable from "@/components/DataTable";
import DeviceFormDialog, { type DeviceFormValues } from "@/components/DeviceFormDialog";
import FormSelect from "@/components/FormSelect";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const VENDOR_VARIANT: Record<string, "info" | "destructive" | "success" | "warning" | "secondary"> = {
  h3c: "info",
  huawei: "destructive",
  juniper: "success",
  arista: "warning",
  cisco: "secondary",
  frr: "info",
};

const STATUS_VARIANT: Record<string, "success" | "destructive" | "warning" | "secondary"> = {
  online: "success",
  offline: "destructive",
  maintenance: "warning",
  unknown: "secondary",
};

const SVID_SOURCE_VARIANT: Record<string, "destructive" | "warning" | "info"> = {
  legacy: "destructive",
  device: "warning",
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
  if (!list?.length) return <span className="text-muted-foreground">-</span>;
  return (
    <div className="flex flex-wrap gap-1">
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
          <Tooltip key={idx}>
            <TooltipTrigger asChild>
              <Badge variant={SVID_SOURCE_VARIANT[u.source || ""] || "info"}>{label}</Badge>
            </TooltipTrigger>
            <TooltipContent>{tip || label}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
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
      <DialogContent className="flex max-h-[90vh] max-w-xl flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="space-y-1 border-b px-6 py-4 text-left">
          <DialogTitle>{device ? `设备凭证 · ${device.name}` : "设备凭证"}</DialogTitle>
          <DialogDescription>留空密码则保持原值，SNMP Community 与登录密码相互独立。</DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[calc(90vh-8rem)] flex-1">
          <Form {...form}>
            <form
              id="device-cred-form"
              className="space-y-4 px-6 py-5"
              onSubmit={form.handleSubmit(async (v) => {
                if (device) await onSave(device.id, v);
              })}
            >
              <Alert variant="warning">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>敏感字段不会回显</AlertTitle>
                <AlertDescription>留空密码则保持原值。SNMP Community 与登录密码已分离，可分别配置。</AlertDescription>
              </Alert>

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
                      <Input placeholder="admin / netconf" {...field} />
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
                      <Input type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
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
                      <Input type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
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
                        <Input type="number" min={1} max={65535} {...field} />
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
                        <Input type="number" min={1} max={65535} {...field} />
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
                      <Input placeholder="留空则按厂商自动选择" {...field} />
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
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
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
                        <Input
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
                        <Input type="number" min={1} max={65535} {...field} />
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
                          <Input {...field} />
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
                          <Input type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
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
                          <Input type="password" autoComplete="new-password" placeholder="留空不修改" {...field} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>
              ) : null}
            </form>
          </Form>
        </ScrollArea>

        <DialogFooter className="border-t px-6 py-4">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {action.cancel}
          </Button>
          <Button type="submit" form="device-cred-form">
            {action.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Devices() {
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
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [initOpen, setInitOpen] = useState(false);
  const [initDevice, setInitDevice] = useState<Device | null>(null);
  const [initBaseline, setInitBaseline] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const siteName = useCallback((id?: number) => sites.find((s) => s.id === id)?.code || "-", [sites]);

  async function loadIfaces(deviceId: number) {
    setIfacesLoading(true);
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
      setIfaces(data);
    } finally {
      setIfacesLoading(false);
    }
  }

  async function openPorts(device: Device) {
    setDrawerDevice(device);
    setIfaces([]);
    await loadIfaces(device.id);
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
      toast.success("设备已纳管");
      setOpen(false);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
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
      toast.success(toastCopy.saved);
      setCredOpen(false);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/devices/${id}`);
    toast.success(toastCopy.deleted);
    setDeleteId(null);
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
      toast.success(`导入完成 · 新增 ${data.created} · 跳过 ${data.skipped}${learnMsg}`);
      if (data.errors?.length) toast.warning(`${data.errors.length} 行需修正`);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function discover(deviceId: number) {
    const tid = toast.loading("SNMP 接口扫描中…");
    try {
      const { data } = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      toast.dismiss(tid);
      const simCount = data.filter((i) => i.discovered_via === "snmp-sim").length;
      if (simCount === data.length) {
        toast.warning(
          "返回的是模拟数据（设备 SNMP 不可达或 Community 错误）。请检查管理 IP、UDP 161 与 Community 后重试",
        );
      } else if (simCount > 0) {
        toast.warning(`部分接口为模拟数据（${simCount}/${data.length}），请检查 SNMP 配置`);
      } else {
        toast.success(`SNMP 发现 ${data.length} 个接口`);
      }
      setIfaces(data);
    } catch (e: unknown) {
      toast.dismiss(tid);
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function learnConfig(d: Device) {
    const tid = toast.loading(`现网配置学习中 · ${d.name}...`);
    try {
      const { data } = await api.post(`/devices/${d.id}/learn`);
      toast.dismiss(tid);
      if (data.success) {
        const inv = data.inventory;
        toast.success(
          `${d.name} 学习完成 · ${inv?.service_count ?? 0} 个业务 · v${data.snapshot_version}`,
        );
        if (data.svid_scan?.ports_scanned) {
          loadIfaces(d.id);
        }
      } else {
        toast.error(data.error || toastCopy.failed);
      }
      load();
    } catch (e: unknown) {
      toast.dismiss(tid);
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
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
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function confirmInitialize() {
    if (!initDevice) return;
    setInitLoading(true);
    try {
      const { data } = await api.post(`/devices/${initDevice.id}/initialize`);
      toast.success(`${data.device} 初始化完成 · v${data.version} · ${data.transport}`);
      setInitOpen(false);
      setInitDevice(null);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    } finally {
      setInitLoading(false);
    }
  }

  async function check(id: number) {
    const tid = toast.loading("可达性探测 · S-VID 扫描中…");
    try {
      const { data } = await api.post(`/devices/${id}/check`);
      toast.dismiss(tid);
      if (data.reachable) {
        const scan = data.svid_scan;
        const svidCount = scan?.total_s_vids ?? 0;
        const conflictCount = scan?.conflicts?.length ?? 0;
        if (conflictCount > 0) {
          toast.warning(
            `${data.device} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`,
          );
        } else {
          toast.success(
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
        toast.error(`${data.device} 不可达 (${data.mgmt_ip})`);
      }
      load();
    } catch (e: unknown) {
      toast.dismiss(tid);
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  const ifaceColumns = useMemo<ColumnDef<DeviceInterface, unknown>[]>(
    () => [
      { accessorKey: "name", header: "接口", size: 120 },
      {
        accessorKey: "description",
        header: "描述",
        cell: ({ row }) => {
          const d = row.original.description;
          if (!d) return "-";
          if (d.includes("bw(")) {
            return (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="secondary">{d}</Badge>
                </TooltipTrigger>
                <TooltipContent>{d}</TooltipContent>
              </Tooltip>
            );
          }
          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="block max-w-[200px] truncate">{d}</span>
              </TooltipTrigger>
              <TooltipContent>{d}</TooltipContent>
            </Tooltip>
          );
        },
      },
      {
        accessorKey: "speed_mbps",
        header: "速率",
        size: 80,
        cell: ({ row }) => {
          const s = row.original.speed_mbps;
          if (!s) return "-";
          return s >= 1000 ? `${s / 1000}G` : `${s}M`;
        },
      },
      {
        accessorKey: "oper_status",
        header: "Oper",
        size: 70,
        cell: ({ row }) => {
          const s = row.original.oper_status;
          return (
            <Badge variant={s === "up" ? "success" : "secondary"}>{s || "-"}</Badge>
          );
        },
      },
      { accessorKey: "ifindex", header: "ifIndex", size: 70 },
      {
        accessorKey: "discovered_via",
        header: "发现方式",
        size: 90,
        cell: ({ row }) => {
          const d = row.original.discovered_via;
          return d ? <Badge variant="outline">{d}</Badge> : null;
        },
      },
      {
        accessorKey: "used_s_vids",
        header: "S-VID 占用",
        cell: ({ row }) => renderSvidUsage(row.original.used_s_vids),
      },
      {
        accessorKey: "allocated",
        header: "占用",
        size: 70,
        cell: ({ row }) => {
          const a = row.original.allocated;
          const hasSvid = row.original.used_s_vids?.length;
          return a || hasSvid ? <Badge variant="warning">已占用</Badge> : "-";
        },
      },
    ],
    [],
  );

  const columns = useMemo<ColumnDef<Device, unknown>[]>(
    () => [
      {
        accessorKey: "name",
        header: "名称",
        size: 140,
        cell: ({ row }) => <span className="block max-w-[140px] truncate">{row.original.name}</span>,
      },
      {
        accessorKey: "vendor",
        header: "厂商",
        size: 120,
        cell: ({ row }) => {
          const v = row.original.vendor;
          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant={VENDOR_VARIANT[v] || "secondary"}>
                  {labelForOption(VENDOR_OPTIONS, v)}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>{labelForOption(VENDOR_OPTIONS, v)}</TooltipContent>
            </Tooltip>
          );
        },
      },
      {
        accessorKey: "model",
        header: "型号",
        size: 120,
        cell: ({ row }) => (
          <span className="block max-w-[120px] truncate">{row.original.model || "-"}</span>
        ),
      },
      {
        accessorKey: "role",
        header: "角色",
        size: 120,
        cell: ({ row }) => {
          const r = row.original.role;
          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline">{labelForOption(DEVICE_ROLE_OPTIONS, r)}</Badge>
              </TooltipTrigger>
              <TooltipContent>{labelForOption(DEVICE_ROLE_OPTIONS, r)}</TooltipContent>
            </Tooltip>
          );
        },
      },
      {
        accessorKey: "overlay_tech",
        header: "Overlay",
        size: 130,
        cell: ({ row }) => {
          const o = row.original.overlay_tech;
          return (
            <Badge variant={o === "vxlan_evpn" ? "info" : "secondary"}>
              {o === "vxlan_evpn" ? "VXLAN-EVPN" : "SR-MPLS-EVPN"}
            </Badge>
          );
        },
      },
      { accessorKey: "mgmt_ip", header: "管理IP", size: 120 },
      {
        id: "transport",
        header: "南向",
        size: 96,
        cell: ({ row }) => (
          <Badge variant="outline">
            {labelForOption(MANAGEMENT_TRANSPORT_OPTIONS, row.original.management_transport || "auto")}
          </Badge>
        ),
      },
      {
        id: "credentials",
        header: "凭证",
        size: 88,
        cell: ({ row }) =>
          row.original.password_set || row.original.username ? (
            <Badge variant="success">已配置</Badge>
          ) : (
            <Badge variant="secondary">未配置</Badge>
          ),
      },
      {
        id: "snmp",
        header: "SNMP",
        size: 88,
        cell: ({ row }) =>
          row.original.snmp_enabled === false ? (
            <Badge variant="secondary">关闭</Badge>
          ) : (
            <Badge variant="info">{row.original.snmp_version || "2c"}</Badge>
          ),
      },
      { accessorKey: "loopback_ip", header: "Loopback", size: 120 },
      { accessorKey: "bgp_asn", header: "ASN", size: 80 },
      {
        id: "site",
        header: "站点",
        size: 80,
        cell: ({ row }) => siteName(row.original.site_id),
      },
      {
        accessorKey: "status",
        header: "状态",
        size: 90,
        cell: ({ row }) => {
          const s = row.original.status;
          return <Badge variant={STATUS_VARIANT[s] || "secondary"}>{s}</Badge>;
        },
      },
      {
        id: "actions",
        header: "操作",
        size: 300,
        cell: ({ row }) => {
          const r = row.original;
          return (
            <div className="flex flex-wrap gap-x-2 gap-y-1">
              <Button variant="link" size="sm" className="h-auto p-0" onClick={() => openPorts(r)}>
                端口
              </Button>
              <Button variant="link" size="sm" className="h-auto gap-1 p-0" onClick={() => openCredEdit(r)}>
                <KeyRound className="h-3.5 w-3.5" />
                凭证
              </Button>
              <Button variant="link" size="sm" className="h-auto gap-1 p-0" onClick={() => learnConfig(r)}>
                <BookOpen className="h-3.5 w-3.5" />
                现网学习
              </Button>
              <Button variant="link" size="sm" className="h-auto gap-1 p-0" onClick={() => initialize(r)}>
                <Rocket className="h-3.5 w-3.5" />
                初始化
              </Button>
              <Button variant="link" size="sm" className="h-auto p-0" onClick={() => check(r.id)}>
                检测
              </Button>
              <Button variant="link" size="sm" className="h-auto gap-1 p-0" onClick={() => discover(r.id)}>
                <Network className="h-3.5 w-3.5" />
                SNMP 发现
              </Button>
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 text-destructive hover:text-destructive"
                onClick={() => setDeleteId(r.id)}
              >
                {action.delete}
              </Button>
            </div>
          );
        },
      },
    ],
    [siteName],
  );

  function runSearch() {
    setPage(1);
    load(1, pageSize, search);
  }

  return (
    <PageCard
      title={pageCopy.devices}
      extra={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to="/settings/management">
              <Settings className="mr-1.5 h-4 w-4" />
              南向接口设置
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/settings/snmp">
              <Settings className="mr-1.5 h-4 w-4" />
              SNMP 全局设置
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="mr-1.5 h-4 w-4" />
            {action.export} CSV
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
          <Button variant="outline" size="sm" onClick={() => importRef.current?.click()}>
            <Upload className="mr-1.5 h-4 w-4" />
            {action.import} CSV
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2 rounded-md border px-3 py-1.5">
                <Switch checked={learnOnImport} onCheckedChange={setLearnOnImport} id="learn-import" />
                <label htmlFor="learn-import" className="cursor-pointer text-sm">
                  {learnOnImport ? "导入即学习" : "仅导入"}
                </label>
              </div>
            </TooltipTrigger>
            <TooltipContent>导入后自动拉取现网 running-config 并解析业务/VLAN 占用</TooltipContent>
          </Tooltip>
          <Button size="sm" onClick={openCreateModal}>
            <Plus className="mr-1.5 h-4 w-4" />
            纳管设备
          </Button>
        </div>
      }
    >
      <ListToolbar
        summary={`共 ${total.toLocaleString()} 台设备`}
        left={
          <div className="flex w-full max-w-sm items-center gap-2">
            <Input
              placeholder="搜索设备名称、主机名或管理 IP"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <Button variant="outline" size="icon" onClick={runSearch}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      <DataTable
        columns={columns}
        data={rows}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        emptyText="暂无设备 · 从导入或纳管开始"
      />

      <Sheet open={!!drawerDevice} onOpenChange={(o) => !o && setDrawerDevice(null)}>
        <SheetContent side="right" className="flex w-full flex-col sm:max-w-3xl">
          <SheetHeader className="space-y-0 pb-4">
            <SheetTitle>{drawerDevice ? `端口清单 · ${drawerDevice.name}` : "端口清单"}</SheetTitle>
          </SheetHeader>
          {drawerDevice ? (
            <div className="mb-4 flex gap-2">
              <Button variant="outline" size="sm" onClick={() => check(drawerDevice.id)}>
                <Cable className="mr-1.5 h-4 w-4" />
                检测 S-VID
              </Button>
              <Button size="sm" onClick={() => discover(drawerDevice.id)}>
                <Network className="mr-1.5 h-4 w-4" />
                SNMP 发现
              </Button>
            </div>
          ) : null}
          {ifaces.some((i) => i.discovered_via === "snmp-sim") ? (
            <Alert variant="warning" className="mb-4">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>部分端口为模拟数据</AlertTitle>
              <AlertDescription>
                发现方式显示 snmp-sim 表示未从设备读到真实 IF-MIB（常见于 Community 错误或 UDP 161 不可达）。Dry-run
                仅影响配置下发，不影响 SNMP 采集。请确认设备 SNMP Community 与平台「SNMP 采集」设置一致后重新发现。
              </AlertDescription>
            </Alert>
          ) : null}
          <div className="min-h-0 flex-1 overflow-auto">
            <DataTable
              columns={ifaceColumns}
              data={ifaces}
              loading={ifacesLoading}
              pageSize={20}
              pageSizeOptions={[20, 50, 100]}
              emptyText="暂无端口数据"
            />
          </div>
        </SheetContent>
      </Sheet>

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

      <Dialog open={initOpen} onOpenChange={(o) => !o && !initLoading && setInitOpen(o)}>
        <DialogContent className="flex max-h-[90vh] max-w-4xl flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl">
          <DialogHeader className="space-y-1 border-b px-6 py-4 text-left">
            <DialogTitle>
              {initDevice ? `基线初始化 · ${initDevice.name} (${initDevice.vendor})` : "基线初始化"}
            </DialogTitle>
            <DialogDescription>
              标准基线预览（管理 / Loopback / Underlay / EVPN Overlay）· 确认后 dry-run 下发并归档初始化快照
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[calc(82vh-108px)] flex-1 px-6 py-4">
            <ConfigPreviewPre>{initBaseline}</ConfigPreviewPre>
          </ScrollArea>
          <DialogFooter className="border-t px-6 py-4">
            <Button type="button" variant="outline" disabled={initLoading} onClick={() => setInitOpen(false)}>
              {action.cancel}
            </Button>
            <Button type="button" disabled={initLoading} onClick={confirmInitialize}>
              {initLoading ? "下发中…" : "下发基线配置"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteId != null} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {action.confirm}
              {action.delete}？
            </AlertDialogTitle>
            <AlertDialogDescription>此操作不可撤销，将永久删除该设备及其关联数据。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{action.cancel}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteId != null && void remove(deleteId)}
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              {action.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageCard>
  );
}
