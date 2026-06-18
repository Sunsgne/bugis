import { useEffect, useState } from "react";
import { Alert } from "antd";
import { api } from "../api/client";

type SystemInfo = {
  dry_run?: boolean;
  telemetry_simulation?: boolean;
  snmp_enabled?: boolean;
  production_data_mode?: boolean;
};

/** Global banner when platform is not in full production data collection mode. */
export default function OperationalBanner() {
  const [info, setInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api
        .get<SystemInfo>("/system/info")
        .then(({ data }) => {
          if (!cancelled) setInfo(data);
        })
        .catch(() => {
          if (!cancelled) setInfo(null);
        });
    };
    load();
    const timer = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (!info) return null;

  const warnings: string[] = [];
  if (info.dry_run) {
    warnings.push("Dry-run 模式：配置不下发至设备，拨测为模拟结果");
  }
  if (info.telemetry_simulation) {
    warnings.push("已启用 telemetry 模拟（BUGIS_TELEMETRY_SIMULATION）");
  }
  if (!info.snmp_enabled) {
    warnings.push("SNMP 未启用：流量/链路负载需配置 SNMP 后才有实测数据");
  }
  if (info.production_data_mode && !warnings.length) {
    return null;
  }

  return (
    <Alert
      type={info.production_data_mode ? "info" : "warning"}
      showIcon
      banner
      style={{ marginBottom: 0, borderRadius: 0 }}
      message={
        info.production_data_mode
          ? "生产数据采集模式：指标来自 SNMP 与南向拨测"
          : "非完整生产数据模式"
      }
      description={warnings.length ? warnings.join(" · ") : undefined}
    />
  );
}
