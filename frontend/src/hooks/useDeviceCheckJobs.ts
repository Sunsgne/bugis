import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Device } from "@/api/types";

export type DeviceCheckJobStatus = "idle" | "checking" | "success" | "error";

export type DeviceCheckJob = {
  status: DeviceCheckJobStatus;
  deviceName: string;
  message?: string;
};

type CheckResult = {
  scheduled?: boolean;
  device_id?: number;
  device?: string;
  reachable?: boolean;
  latency_ms?: number;
  method?: string;
  mgmt_ip?: string;
  mgmt_ip_backup?: string;
  mgmt_ip_active?: string;
  mgmt_ip_active_label?: string;
  mgmt_ip_active_role?: string;
  dry_run?: boolean;
  probes?: Array<{ method?: string }>;
  svid_scan?: {
    total_s_vids?: number;
    conflicts?: unknown[];
  };
};

type BatchCheckResult = {
  scheduled: number;
  device_ids: number[];
  max_workers: number;
};

function notifyCheckResult(
  data: CheckResult,
  deviceName: string,
  notify: {
    success: (msg: string) => void;
    warning: (msg: string, duration?: number) => void;
  },
) {
  if (data.reachable) {
    const svidCount = data.svid_scan?.total_s_vids ?? 0;
    const conflictCount = data.svid_scan?.conflicts?.length ?? 0;
    const dryTag = data.dry_run ? " · 配置 dry-run" : "";
    const activeTag = data.mgmt_ip_active
      ? ` · 当前 ${data.mgmt_ip_active_label || data.mgmt_ip_active_role} ${data.mgmt_ip_active}`
      : "";
    if (conflictCount > 0) {
      notify.warning(`${deviceName} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`);
    } else {
      notify.success(
        `${deviceName} 可达${data.method ? ` · ${data.method}` : ""}${data.latency_ms != null ? ` (${data.latency_ms}ms)` : ""} · 已扫描 ${svidCount} 个 S-VID 占用${activeTag}${dryTag}`,
      );
    }
    return;
  }
  const tried = data.probes?.map((p) => p.method).filter(Boolean).join(" / ");
  notify.warning(
    `${deviceName} 管理面不可达${data.mgmt_ip_backup ? `（主 ${data.mgmt_ip} / 备 ${data.mgmt_ip_backup}）` : data.mgmt_ip ? ` (${data.mgmt_ip})` : ""}${tried ? ` · 已探测 ${tried}` : ""} · 请检查 IP、端口、SNMP Community 与防火墙`,
    6,
  );
}

async function pollCheckComplete(
  deviceId: number,
  startedAtMs: number,
  previousReachAt?: string | null,
): Promise<CheckResult | null> {
  const maxAttempts = 90;
  for (let i = 0; i < maxAttempts; i += 1) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const { data: dev } = await api.get<Device>(`/devices/${deviceId}`);
      const reachAt = dev.last_reachability_at;
      const updated =
        reachAt != null
        && (previousReachAt == null || new Date(reachAt).getTime() > new Date(previousReachAt).getTime() + 500
          || Date.now() - startedAtMs > 3000 && new Date(reachAt).getTime() >= startedAtMs - 2000);
      if (updated) {
        let svidTotal = 0;
        try {
          const { data: bindings } = await api.get<{ total_bindings?: number }>(
            `/devices/${deviceId}/port-bindings`,
          );
          svidTotal = bindings.total_bindings ?? 0;
        } catch {
          /* optional summary */
        }
        return {
          device: dev.name,
          reachable: dev.status === "online",
          latency_ms: dev.last_reachability_latency_ms,
          method: dev.last_reachability_method,
          mgmt_ip: dev.mgmt_ip,
          mgmt_ip_backup: dev.mgmt_ip_backup,
          mgmt_ip_active: dev.mgmt_ip_active,
          mgmt_ip_active_label:
            dev.mgmt_ip_active_role === "backup"
              ? dev.mgmt_ip_backup_label
              : dev.mgmt_ip_primary_label,
          mgmt_ip_active_role: dev.mgmt_ip_active_role,
          svid_scan: dev.status === "online"
            ? { total_s_vids: svidTotal, conflicts: [] }
            : undefined,
        };
      }
    } catch {
      /* keep polling */
    }
  }
  return null;
}

export function useDeviceCheckJobs(notify: {
  success: (msg: string) => void;
  warning: (msg: string, duration?: number) => void;
  error: (msg: string) => void;
}) {
  const [jobs, setJobs] = useState<Record<number, DeviceCheckJob>>({});

  const activeCheckCount = useMemo(
    () => Object.values(jobs).filter((j) => j.status === "checking").length,
    [jobs],
  );

  const getJob = useCallback(
    (deviceId: number): DeviceCheckJob | null => jobs[deviceId] ?? null,
    [jobs],
  );

  const finishCheck = useCallback(
    (deviceId: number, deviceName: string, data: CheckResult | null, onDone?: () => void) => {
      if (!data) {
        setJobs((prev) => ({
          ...prev,
          [deviceId]: { status: "error", deviceName, message: "timeout" },
        }));
        notify.error(`${deviceName} 可达性探测超时`);
        onDone?.();
        return;
      }
      notifyCheckResult(data, deviceName, notify);
      setJobs((prev) => ({
        ...prev,
        [deviceId]: {
          status: data.reachable ? "success" : "error",
          deviceName,
          message: data.reachable ? "online" : "offline",
        },
      }));
      onDone?.();
    },
    [notify],
  );

  const checkOne = useCallback(
    (
      device: Device | { id: number; name: string; last_reachability_at?: string | null },
      onDone?: () => void,
    ) => {
      const deviceId = device.id;
      const deviceName = device.name;
      const previousReachAt = "last_reachability_at" in device ? device.last_reachability_at : undefined;

      setJobs((prev) => ({
        ...prev,
        [deviceId]: { status: "checking", deviceName },
      }));

      void (async () => {
        const startedAt = Date.now();
        try {
          await api.post<CheckResult>(`/devices/${deviceId}/check`, null, {
            params: { background: true },
          });
          const result = await pollCheckComplete(deviceId, startedAt, previousReachAt);
          finishCheck(deviceId, deviceName, result, onDone);
        } catch (e: unknown) {
          const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          setJobs((prev) => ({
            ...prev,
            [deviceId]: { status: "error", deviceName, message: detail },
          }));
          notify.error(detail || `${deviceName} 探测失败`);
          onDone?.();
        }
      })();
    },
    [finishCheck, notify],
  );

  const checkBatch = useCallback(
    (devices: Device[], onDone?: () => void) => {
      const ids = devices.map((d) => d.id);
      if (!ids.length) return;

      for (const d of devices) {
        setJobs((prev) => ({
          ...prev,
          [d.id]: { status: "checking", deviceName: d.name },
        }));
      }

      void (async () => {
        try {
          await api.post<BatchCheckResult>("/devices/check-batch", { device_ids: ids });
          notify.success(`已启动 ${ids.length} 台设备并行探测 · S-VID 扫描`);
          let remaining = devices.length;
          const doneOne = () => {
            remaining -= 1;
            if (remaining <= 0) onDone?.();
          };
          for (const d of devices) {
            void (async () => {
              const startedAt = Date.now();
              const result = await pollCheckComplete(d.id, startedAt, d.last_reachability_at);
              finishCheck(d.id, d.name, result, doneOne);
            })();
          }
        } catch (e: unknown) {
          const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          for (const d of devices) {
            setJobs((prev) => ({
              ...prev,
              [d.id]: { status: "error", deviceName: d.name, message: detail },
            }));
          }
          notify.error(detail || "批量探测失败");
          onDone?.();
        }
      })();
    },
    [finishCheck, notify],
  );

  return {
    getJob,
    checkOne,
    checkBatch,
    activeCheckCount,
  };
}
