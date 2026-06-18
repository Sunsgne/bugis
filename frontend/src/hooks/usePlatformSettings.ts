import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

export interface PlatformSettings {
  id: number;
  dry_run: boolean;
  netconf_timeout: number;
  ssh_timeout?: number;
  default_netconf_port?: number;
  default_ssh_port?: number;
  default_username?: string;
  baseline_ntp_server: string;
  baseline_syslog_server: string;
  scheduler_enabled: boolean;
  scheduler_interval_seconds: number;
  threshold_packet_loss_pct: number;
  threshold_latency_ms: number;
  threshold_utilization_pct: number;
  threshold_health_score: number;
  threshold_link_utilization_pct: number;
  controller_bgp_asn: number;
  controller_node_id: string;
  webhook_token: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_from: string;
  smtp_provider?: string;
  smtp_security?: string;
  smtp_password_set?: boolean;
  enable_metrics: boolean;
  access_token_expire_minutes: number;
  login_rate_limit_per_ip?: number;
  login_rate_limit_window_minutes?: number;
  login_lockout_after_failures?: number;
  login_lockout_minutes?: number;
  captcha_after_failures?: number;
  turnstile_enabled?: boolean;
  turnstile_site_key?: string;
  turnstile_secret_key_set?: boolean;
  mfa_required_platform?: boolean;
  mfa_required_portal?: boolean;
  mfa_allow_totp?: boolean;
  mfa_allow_email?: boolean;
  expose_openapi?: boolean;
  protect_live_config?: boolean;
  snapshot_before_change?: boolean;
  async_provisioning?: boolean;
  provision_max_concurrency?: number;
  notes?: string;
}

export interface ReadonlyInfo {
  version: string;
  app_env: string;
  app_name: string;
  database_url: string;
  secret_key_set: boolean;
}

export function usePlatformSettings() {
  const [platform, setPlatform] = useState<PlatformSettings | null>(null);
  const [readonly, setReadonly] = useState<ReadonlyInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<{ platform: PlatformSettings; readonly: ReadonlyInfo }>(
        "/system/settings",
      );
      setPlatform(data.platform);
      setReadonly(data.readonly);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function save(partial: Partial<PlatformSettings & { smtp_password?: string }>) {
    setSaving(true);
    try {
      const payload = { ...partial };
      if ("smtp_password" in payload && !payload.smtp_password) {
        delete payload.smtp_password;
      }
      if ("turnstile_secret_key" in payload && !payload.turnstile_secret_key) {
        delete payload.turnstile_secret_key;
      }
      const { data } = await api.patch<PlatformSettings>("/system/settings/platform", payload);
      setPlatform(data);
      return data;
    } finally {
      setSaving(false);
    }
  }

  return { platform, readonly, loading, saving, load, save };
}
