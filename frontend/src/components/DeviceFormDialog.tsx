import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import { useEffect } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import FormSelect from "@/components/FormSelect";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  DEVICE_ROLE_OPTIONS,
  MANAGEMENT_TRANSPORT_OPTIONS,
  OVERLAY_OPTIONS,
  SNMP_V3_SECURITY_OPTIONS,
  SNMP_VERSION_OPTIONS,
  VENDOR_OPTIONS,
} from "@/constants/formOptions";
import type { ManagementDefaults, Site, SnmpDefaults } from "@/api/types";
import { action } from "@/constants/uiCopy";

const portField = z.coerce.number().int().min(1, "端口范围 1–65535").max(65535, "端口范围 1–65535");

const schema = z.object({
  name: z.string().min(1, "请输入设备名称"),
  vendor: z.string(),
  model: z.string().optional(),
  role: z.string(),
  overlay_tech: z.string(),
  mgmt_ip: z.string().min(1, "请输入管理 IP"),
  loopback_ip: z.string().optional(),
  bgp_asn: z.coerce.number().nullable().optional(),
  site_id: z.coerce.number().nullable().optional(),
  sr_node_sid: z.coerce.number().nullable().optional(),
  is_route_reflector: z.boolean().optional(),
  management_transport: z.string(),
  username: z.string().optional(),
  password: z.string().optional(),
  enable_password: z.string().optional(),
  netconf_port: portField,
  ssh_port: portField,
  netmiko_device_type: z.string().optional(),
  snmp_enabled: z.boolean(),
  snmp_community: z.string().optional(),
  snmp_port: portField.optional(),
  snmp_version: z.string().optional(),
  snmp_v3_username: z.string().optional(),
  snmp_v3_security_level: z.string().optional(),
  snmp_v3_auth_password: z.string().optional(),
  snmp_v3_priv_password: z.string().optional(),
});

export type DeviceFormValues = z.infer<typeof schema>;

const VENDOR_AUTH_HINT: Record<string, string> = {
  h3c: "默认 NETCONF 830 / SSH 22；账号常为 admin 或 netconf",
  huawei: "默认 NETCONF 830；账号常为 netconf 或 huawei",
  juniper: "默认 NETCONF 830；账号常为 netconf",
  arista: "默认 SSH/eAPI；部分场景用 admin",
  cisco: "IOS-XR NETCONF 830；账号常为 admin / cisco",
  frr: "SSH 22，vtysh CLI；账号为 Linux 用户",
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sites: Site[];
  mgmtDefaults: ManagementDefaults;
  snmpDefaults: SnmpDefaults;
  onSubmit: (values: DeviceFormValues) => Promise<void>;
};

export default function DeviceFormDialog({
  open,
  onOpenChange,
  sites,
  mgmtDefaults,
  snmpDefaults,
  onSubmit,
}: Props) {
  const form = useForm<DeviceFormValues>({
    resolver: zodResolver(schema) as Resolver<DeviceFormValues>,
    defaultValues: {
      vendor: "h3c",
      role: "leaf",
      overlay_tech: "vxlan_evpn",
      management_transport: mgmtDefaults.management_transport,
      netconf_port: mgmtDefaults.netconf_port,
      ssh_port: mgmtDefaults.ssh_port,
      username: mgmtDefaults.username,
      snmp_enabled: mgmtDefaults.snmp.enabled,
      snmp_port: mgmtDefaults.snmp.port,
      snmp_community: "",
      snmp_version: mgmtDefaults.snmp.version,
      snmp_v3_security_level: "authPriv",
      is_route_reflector: false,
    },
  });

  const watchVendor = form.watch("vendor");
  const watchSnmpEnabled = form.watch("snmp_enabled");
  const watchSnmpVersion = form.watch("snmp_version");

  useEffect(() => {
    if (open) {
      form.reset({
        vendor: "h3c",
        role: "leaf",
        overlay_tech: "vxlan_evpn",
        management_transport: mgmtDefaults.management_transport,
        netconf_port: mgmtDefaults.netconf_port,
        ssh_port: mgmtDefaults.ssh_port,
        username: mgmtDefaults.username,
        snmp_enabled: mgmtDefaults.snmp.enabled,
        snmp_port: mgmtDefaults.snmp.port,
        snmp_community: "",
        snmp_version: mgmtDefaults.snmp.version,
        snmp_v3_security_level: "authPriv",
        is_route_reflector: false,
      });
    }
  }, [open, mgmtDefaults, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,900px)] max-w-3xl flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 text-left">
          <DialogTitle>纳管设备</DialogTitle>
          <DialogDescription>填写设备基础信息与南向凭证，SNMP 与登录密码相互独立。</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <Form {...form}>
            <form
              id="device-create-form"
              className="space-y-6 px-6 py-5"
              onSubmit={form.handleSubmit(async (v) => {
                await onSubmit(v);
              })}
            >
              <Alert variant="info">
                <Info className="h-4 w-4" />
                <AlertTitle>远程登录凭证说明</AlertTitle>
                <AlertDescription>
                  <strong>配置下发 / 初始化</strong> 使用 NETCONF 或 SSH CLI（可在下方自定义传输方式与端口）。
                  <strong> SNMP 发现</strong> 独立配置 Community / v3 认证。全局默认见{" "}
                  <Link to="/settings/management" className="text-primary underline-offset-2 hover:underline">
                    南向接口
                  </Link>{" "}
                  与{" "}
                  <Link to="/settings/snmp" className="text-primary underline-offset-2 hover:underline">
                    SNMP 采集
                  </Link>
                  。
                </AlertDescription>
              </Alert>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem className="sm:col-span-1">
                      <FormLabel>名称 *</FormLabel>
                      <FormControl>
                        <Input placeholder="BJ-LEAF-01" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="vendor"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>厂商</FormLabel>
                      <FormControl>
                        <FormSelect value={field.value} onValueChange={field.onChange} options={VENDOR_OPTIONS} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="model"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>型号</FormLabel>
                      <FormControl>
                        <Input placeholder="S6850 / CE12800 / MX204 …" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="role"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>角色</FormLabel>
                      <FormControl>
                        <FormSelect value={field.value} onValueChange={field.onChange} options={DEVICE_ROLE_OPTIONS} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="overlay_tech"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Overlay</FormLabel>
                      <FormControl>
                        <FormSelect value={field.value} onValueChange={field.onChange} options={OVERLAY_OPTIONS} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="mgmt_ip"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>管理 IP *</FormLabel>
                      <FormControl>
                        <Input placeholder="10.1.0.11" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="loopback_ip"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Loopback</FormLabel>
                      <FormControl>
                        <Input placeholder="10.1.255.11" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="bgp_asn"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>BGP ASN</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          value={field.value ?? ""}
                          onChange={(e) => field.onChange(e.target.value === "" ? null : Number(e.target.value))}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="site_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>数据中心</FormLabel>
                      <FormControl>
                        <FormSelect
                          allowClear
                          value={field.value != null ? String(field.value) : ""}
                          onValueChange={(v) => field.onChange(v ? Number(v) : null)}
                          options={sites.map((s) => ({ value: String(s.id), label: `${s.code} · ${s.name}` }))}
                          placeholder="选择站点"
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="sr_node_sid"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SR Node-SID</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          value={field.value ?? ""}
                          onChange={(e) => field.onChange(e.target.value === "" ? null : Number(e.target.value))}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="is_route_reflector"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                      <FormLabel className="mt-0">路由反射器</FormLabel>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="text-sm font-semibold">南向登录凭证</h3>
                {watchVendor && VENDOR_AUTH_HINT[watchVendor] ? (
                  <p className="text-sm text-muted-foreground">{VENDOR_AUTH_HINT[watchVendor]}</p>
                ) : null}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <FormField
                    control={form.control}
                    name="management_transport"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>配置下发传输</FormLabel>
                        <FormControl>
                          <FormSelect
                            value={field.value}
                            onValueChange={field.onChange}
                            options={MANAGEMENT_TRANSPORT_OPTIONS}
                          />
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
                        <FormLabel>登录密码</FormLabel>
                        <FormControl>
                          <Input type="password" autoComplete="new-password" placeholder="NETCONF / SSH" {...field} />
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
                          <Input type="password" autoComplete="new-password" placeholder="可选" {...field} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="netconf_port"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>NETCONF 端口</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={1}
                            max={65535}
                            value={field.value ?? ""}
                            onChange={(e) =>
                              field.onChange(e.target.value === "" ? undefined : Number(e.target.value))
                            }
                          />
                        </FormControl>
                        <FormMessage />
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
                          <Input
                            type="number"
                            min={1}
                            max={65535}
                            value={field.value ?? ""}
                            onChange={(e) =>
                              field.onChange(e.target.value === "" ? undefined : Number(e.target.value))
                            }
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="netmiko_device_type"
                    render={({ field }) => (
                      <FormItem className="sm:col-span-2">
                        <FormLabel>Netmiko 设备类型</FormLabel>
                        <FormControl>
                          <Input placeholder="留空则按厂商自动选择" {...field} />
                        </FormControl>
                        <FormDescription>覆盖 SSH CLI 驱动，如 hp_comware、cisco_xr</FormDescription>
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">SNMP 采集</h3>
                    <p className="text-sm text-muted-foreground">
                      默认 Community <code className="rounded bg-muted px-1">{snmpDefaults.community}</code> · UDP{" "}
                      {snmpDefaults.port}
                    </p>
                  </div>
                  <FormField
                    control={form.control}
                    name="snmp_enabled"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-2 space-y-0">
                        <FormLabel className="mt-0">启用</FormLabel>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>

                {watchSnmpEnabled ? (
                  <Accordion type="single" collapsible defaultValue="snmp">
                    <AccordionItem value="snmp" className="border-none">
                      <AccordionTrigger className="py-2 text-sm text-muted-foreground hover:no-underline">
                        高级参数（留空则使用平台默认）
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="grid gap-4 pt-2 sm:grid-cols-2 lg:grid-cols-4">
                          <FormField
                            control={form.control}
                            name="snmp_community"
                            render={({ field }) => (
                              <FormItem className="sm:col-span-2">
                                <FormLabel>Community</FormLabel>
                                <FormControl>
                                  <Input placeholder={snmpDefaults.community} {...field} />
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
                                  <Input
                                    type="number"
                                    min={1}
                                    max={65535}
                                    value={field.value ?? ""}
                                    onChange={(e) =>
                                      field.onChange(e.target.value === "" ? undefined : Number(e.target.value))
                                    }
                                  />
                                </FormControl>
                                <FormMessage />
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
                                  <FormSelect
                                    value={field.value || "2c"}
                                    onValueChange={field.onChange}
                                    options={SNMP_VERSION_OPTIONS}
                                  />
                                </FormControl>
                              </FormItem>
                            )}
                          />
                          {watchSnmpVersion === "3" ? (
                            <>
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
                                      <Input type="password" autoComplete="new-password" {...field} />
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
                                      <Input type="password" autoComplete="new-password" {...field} />
                                    </FormControl>
                                  </FormItem>
                                )}
                              />
                            </>
                          ) : null}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                ) : null}
              </div>
            </form>
          </Form>
        </div>

        <DialogFooter className="shrink-0 border-t px-6 py-4">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {action.cancel}
          </Button>
          <Button type="submit" form="device-create-form">
            {action.create}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
