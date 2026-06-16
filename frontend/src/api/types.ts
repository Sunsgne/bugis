export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Site {
  id: number;
  name: string;
  code: string;
  region?: string;
  address?: string;
  bgp_asn?: number;
  underlay_prefix?: string;
  description?: string;
  delivery_mode?: string;
  controller_id?: number;
}

export interface Controller {
  id: number;
  name: string;
  type: string;
  base_url: string;
  username?: string;
  verify_tls: number;
  description?: string;
}

export interface Tenant {
  id: number;
  name: string;
  code: string;
  type: string;
  status: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  cloud_account?: string;
  description?: string;
  circuits_total?: number;
}

export interface SvidUsage {
  s_vid?: number | null;
  c_vid?: number | null;
  access_mode?: string;
  circuit_code?: string | null;
  source?: string;
  note?: string | null;
  description?: string | null;
  rate_limit_mbps?: number | null;
  vni?: number | null;
  vsi_name?: string | null;
  tenant_name?: string | null;
  tenant_code?: string | null;
  circuit_name?: string | null;
  bandwidth_mbps?: number | null;
}

export interface DevicePortBinding {
  interface_name: string;
  binding_type: "platform" | "device";
  tenant_id?: number | null;
  tenant_name?: string | null;
  tenant_code?: string | null;
  business_name?: string | null;
  circuit_id?: number | null;
  circuit_code?: string | null;
  circuit_name?: string | null;
  circuit_status?: string | null;
  endpoint_label?: string | null;
  access_mode?: string;
  s_vid?: number | null;
  c_vid?: number | null;
  vni?: number | null;
  vsi_name?: string | null;
  description?: string | null;
  rate_limit_mbps?: number | null;
  bandwidth_mbps?: number | null;
  source?: string;
  note?: string | null;
}

export interface DevicePortBindings {
  device_id: number;
  device: string;
  total_bindings: number;
  platform_bindings: number;
  device_only_bindings: number;
  bound_interfaces: number;
  unbound_interfaces: string[];
  items: DevicePortBinding[];
}

export interface DeviceInterface {
  id: number;
  device_id: number;
  name: string;
  description?: string;
  speed_mbps?: number;
  admin_up: boolean;
  allocated: boolean;
  used_s_vids?: SvidUsage[] | null;
  ifindex?: number;
  oper_status?: string;
  discovered_via?: string;
}

export interface SnmpDefaults {
  enabled: boolean;
  port: number;
  community: string;
  version: string;
}

export interface ManagementDefaults {
  netconf_port: number;
  ssh_port: number;
  username: string;
  management_transport: string;
  netconf_timeout: number;
  ssh_timeout: number;
  snmp: SnmpDefaults;
  mgmt_ip_primary_label?: string;
  mgmt_ip_backup_label?: string;
}

export interface Device {
  id: number;
  name: string;
  hostname?: string;
  vendor: string;
  model?: string;
  os_version?: string;
  role: string;
  overlay_tech: string;
  status: string;
  mgmt_ip: string;
  mgmt_ip_backup?: string;
  mgmt_ip_primary_label?: string;
  mgmt_ip_backup_label?: string;
  mgmt_ip_active?: string;
  mgmt_ip_active_role?: "primary" | "backup";
  last_reachability_at?: string;
  last_reachability_latency_ms?: number;
  last_reachability_method?: string;
  management_transport?: string;
  netconf_port?: number;
  ssh_port?: number;
  username?: string;
  password_set?: boolean;
  enable_password_set?: boolean;
  netmiko_device_type?: string;
  loopback_ip?: string;
  bgp_asn?: number;
  sr_node_sid?: number;
  is_route_reflector: boolean;
  site_id?: number;
  snmp_enabled?: boolean;
  snmp_port?: number;
  snmp_version?: string;
  snmp_community_set?: boolean;
  snmp_v3_username?: string;
  snmp_v3_security_level?: string;
  snmp_v3_auth_protocol?: string;
  snmp_v3_priv_protocol?: string;
  snmp_v3_auth_password_set?: boolean;
  snmp_v3_priv_password_set?: boolean;
  interfaces?: DeviceInterface[];
}

export interface CircuitEndpoint {
  id: number;
  circuit_id: number;
  device_id: number;
  label: string;
  interface_name: string;
  access_mode?: string;
  vlan_id?: number;
  inner_vlan_id?: number;
  ip_address?: string;
  gateway_ip?: string;
}

export interface Circuit {
  id: number;
  name: string;
  code: string;
  tenant_id: number;
  service_type: string;
  status: string;
  vni?: number;
  vsi_name?: string;
  vlan_id?: number;
  vrf_name?: string;
  route_distinguisher?: string;
  route_target?: string;
  esi?: string;
  bandwidth_mbps: number;
  mtu: number;
  sla_target?: string;
  cos?: string;
  description?: string;
  egress_country?: string;
  egress_site_id?: number;
  ipt_public_ip?: string;
  ipt_nat_enabled?: number;
  endpoints: CircuitEndpoint[];
  path_mode?: string;
  path_hops?: { device_id: number; sequence: number; device_name?: string; sr_node_sid?: number }[];
  segment_list?: number[];
}

export interface ConfigJob {
  id: number;
  work_order_id: number;
  device_id: number;
  status: string;
  operation: string;
  transport: string;
  rendered_config?: string;
  rollback_config?: string;
  output?: string;
}

export interface WorkOrderEvent {
  id: number;
  level: string;
  message: string;
  actor?: string;
  created_at?: string;
}

export interface WorkOrder {
  id: number;
  code: string;
  circuit_id: number;
  type: string;
  status: string;
  title: string;
  requested_by?: string;
  approved_by?: string;
  notes?: string;
  events: WorkOrderEvent[];
  config_jobs: ConfigJob[];
  created_at?: string;
}

export interface Dashboard {
  tenants: number;
  devices: number;
  devices_online: number;
  circuits: number;
  circuits_active: number;
  total_active_bandwidth_mbps: number;
  work_orders: number;
  circuits_by_status: Record<string, number>;
  devices_by_vendor: Record<string, number>;
}

export interface CircuitHealth {
  circuit_id: number;
  circuit_code: string;
  status: string;
  sla_target?: string;
  avg_latency_ms: number;
  avg_jitter_ms: number;
  avg_packet_loss_pct: number;
  avg_utilization_pct: number;
  peak_utilization_pct: number;
  bandwidth_mbps: number;
  samples: number;
  qos_samples?: number;
  data_sources?: string[];
  health_score: number;
  tunnel_down?: boolean;
}

export interface TelemetrySample {
  id: number;
  circuit_id?: number;
  rx_mbps: number;
  tx_mbps: number;
  utilization_pct: number;
  latency_ms: number;
  jitter_ms: number;
  packet_loss_pct: number;
  tunnel_state?: string;
  created_at?: string;
}

export interface TrafficP95 {
  in_95_mbps: number;
  out_95_mbps: number;
  billable_95_mbps: number;
}

export interface TrafficSummary {
  circuit_id: number;
  samples: TelemetrySample[];
  p95: TrafficP95;
  bandwidth_mbps: number;
}

export interface TrafficBilling {
  circuit_id: number;
  circuit_code: string;
  period?: string | null;
  available_months: string[];
  samples: number;
  bandwidth_mbps: number;
  in_95_mbps: number;
  out_95_mbps: number;
  billable_95_mbps: number;
  peak_mbps: number;
  avg_mbps: number;
  utilization_pct: number;
}

export interface AvailabilityEvent {
  id: number;
  circuit_id: number;
  kind: string;
  started_at: string;
  ended_at?: string;
  duration_sec?: number;
  source: string;
  detail?: string;
}

export interface CircuitAvailability {
  circuit_id: number;
  circuit_code: string;
  hours: number;
  uptime_pct: number;
  interruption_count: number;
  flash_count: number;
  total_downtime_sec: number;
  avg_latency_ms: number;
  flap_count: number;
  events: AvailabilityEvent[];
}

export interface Alarm {
  id: number;
  severity: string;
  status: string;
  kind: string;
  title: string;
  detail?: string;
  circuit_id?: number;
  device_id?: number;
  acknowledged_by?: string;
  created_at?: string;
}

export interface AlarmSummary {
  active: number;
  by_severity: Record<string, number>;
}

export interface Link {
  id: number;
  name: string;
  type: string;
  device_a_id: number;
  device_z_id: number;
  capacity_mbps: number;
  reserved_mbps: number;
}

export interface SiteCapacity {
  site_id: number;
  site: string;
  code: string;
  devices: number;
  capacity_mbps: number;
  used_mbps: number;
  utilization_pct: number;
}

export interface LinkUsage {
  link_id: number;
  name: string;
  type: string;
  device_a: string;
  device_z: string;
  interface_a?: string;
  interface_z?: string;
  capacity_mbps: number;
  reserved_mbps: number;
  traffic_mbps?: number;
  peak_utilization_pct?: number;
  avg_utilization_pct?: number;
  utilization_pct: number;
  samples?: number;
}

export interface AuditEntry {
  id: number;
  actor: string;
  method: string;
  path: string;
  status_code: number;
  source_ip?: string;
  created_at?: string;
}

export interface Topology {
  sites: { id: number; name: string; code: string }[];
  nodes: {
    id: number;
    name: string;
    vendor: string;
    role: string;
    overlay_tech: string;
    site_id?: number;
    status: string;
  }[];
  edges: {
    id: number;
    name: string;
    type: string;
    source: number;
    target: number;
    capacity_mbps: number;
    reserved_mbps: number;
    utilization_pct?: number;
  }[];
}
