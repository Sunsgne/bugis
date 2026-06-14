export interface Site {
  id: number;
  name: string;
  code: string;
  region?: string;
  address?: string;
  bgp_asn?: number;
  underlay_prefix?: string;
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
}

export interface DeviceInterface {
  id: number;
  device_id: number;
  name: string;
  speed_mbps?: number;
  admin_up: boolean;
  allocated: boolean;
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
  loopback_ip?: string;
  bgp_asn?: number;
  sr_node_sid?: number;
  is_route_reflector: boolean;
  site_id?: number;
  interfaces?: DeviceInterface[];
}

export interface CircuitEndpoint {
  id: number;
  circuit_id: number;
  device_id: number;
  label: string;
  interface_name: string;
  vlan_id?: number;
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
  endpoints: CircuitEndpoint[];
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
  health_score: number;
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
  created_at?: string;
}
