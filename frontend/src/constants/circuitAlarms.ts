/** Circuit-scoped alarm kinds (excludes backbone link_utilization). */
export const CIRCUIT_ALARM_KINDS = [
  "tunnel_down",
  "circuit_interruption",
  "sla_loss",
  "sla_latency",
  "utilization",
  "health",
  "circuit_flap",
] as const;

export const DEFAULT_CIRCUIT_ALARM_KINDS = [...CIRCUIT_ALARM_KINDS];

export const DEFAULT_ALARM_SUPPRESS_MINUTES = 60;
