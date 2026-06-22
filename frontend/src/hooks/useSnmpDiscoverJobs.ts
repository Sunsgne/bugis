import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Device, DeviceInterface } from "@/api/types";

export type SnmpDiscoverJobStatus = "idle" | "discovering" | "success" | "error";

export type SnmpDiscoverJob = {
  status: SnmpDiscoverJobStatus;
  deviceName: string;
  message?: string;
};

type ScheduledOut = {
  scheduled?: boolean;
  device_id?: number;
  device?: string;
};

type BatchOut = {
  scheduled: number;
  device_ids: number[];
  max_workers: number;
};

function notifyDiscoverResult(
  ifaces: DeviceInterface[],
  deviceName: string,
  notify: {
    success: (msg: string) => void;
    warning: (msg: string, duration?: number) => void;
    info: (msg: string) => void;
  },
) {
  const simCount = ifaces.filter((i) => i.discovered_via === "snmp-sim").length;
  const cfgCount = ifaces.filter((i) => i.discovered_via === "running-config").length;
  const svidCount = ifaces.filter((i) => i.used_s_vids?.length).length;
  if (simCount === ifaces.length) {
    notify.warning(
      `${deviceName}：返回模拟数据（SNMP 不可达或 Community/端口错误）。华为请确认 UDP 16161 与管理网 IP 可达`,
      6,
    );
  } else if (cfgCount > 0 && !ifaces.some((i) => i.discovered_via === "snmp")) {
    notify.info(
      `${deviceName}：SNMP 不可达，已从 running-config 解析 ${ifaces.length} 个物理口（${svidCount} 个有 S-VID 占用）`,
    );
  } else if (simCount > 0) {
    notify.warning(`${deviceName}：部分接口为模拟数据（${simCount}/${ifaces.length}）`);
  } else {
    notify.success(`${deviceName}：SNMP 发现 ${ifaces.length} 个接口 · ${svidCount} 个端口有 S-VID 占用`);
  }
  if (svidCount === 0 && simCount < ifaces.length) {
    notify.info(`${deviceName}：S-VID 需现网学习后解析，请执行「现网学习」`);
  }
}

async function pollDiscoverComplete(
  deviceId: number,
  startedAtMs: number,
  baselineCount: number,
): Promise<DeviceInterface[] | null> {
  for (let i = 0; i < 90; i += 1) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
      const maxUpdated = data.reduce((max, row) => {
        const ts = row.updated_at ? new Date(row.updated_at).getTime() : 0;
        return Math.max(max, ts);
      }, 0);
      if (data.length > baselineCount) return data;
      if (maxUpdated >= startedAtMs - 1500 && data.length > 0) return data;
    } catch {
      /* keep polling */
    }
  }
  return null;
}

export function useSnmpDiscoverJobs(notify: {
  success: (msg: string) => void;
  warning: (msg: string, duration?: number) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}) {
  const [jobs, setJobs] = useState<Record<number, SnmpDiscoverJob>>({});

  const activeDiscoverCount = useMemo(
    () => Object.values(jobs).filter((j) => j.status === "discovering").length,
    [jobs],
  );

  const getJob = useCallback(
    (deviceId: number): SnmpDiscoverJob | null => jobs[deviceId] ?? null,
    [jobs],
  );

  const finishDiscover = useCallback(
    (
      deviceId: number,
      deviceName: string,
      ifaces: DeviceInterface[] | null,
      onDone?: () => void,
    ) => {
      if (!ifaces) {
        setJobs((prev) => ({
          ...prev,
          [deviceId]: { status: "error", deviceName, message: "timeout" },
        }));
        notify.error(`${deviceName} SNMP 接口扫描超时`);
        onDone?.();
        return;
      }
      notifyDiscoverResult(ifaces, deviceName, notify);
      setJobs((prev) => ({
        ...prev,
        [deviceId]: {
          status: "success",
          deviceName,
          message: `${ifaces.length} 接口`,
        },
      }));
      onDone?.();
    },
    [notify],
  );

  const discoverOne = useCallback(
    (device: Device | { id: number; name: string }, onDone?: () => void) => {
      const deviceId = device.id;
      const deviceName = device.name;

      setJobs((prev) => ({
        ...prev,
        [deviceId]: { status: "discovering", deviceName },
      }));

      void (async () => {
        const startedAt = Date.now();
        let baselineCount = 0;
        try {
          try {
            const { data: existing } = await api.get<DeviceInterface[]>(
              `/devices/${deviceId}/interfaces`,
            );
            baselineCount = existing.length;
          } catch {
            baselineCount = 0;
          }

          await api.post<ScheduledOut>(`/devices/${deviceId}/discover-interfaces`, null, {
            params: { background: true },
          });
          const ifaces = await pollDiscoverComplete(deviceId, startedAt, baselineCount);
          finishDiscover(deviceId, deviceName, ifaces, onDone);
        } catch (e: unknown) {
          const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          setJobs((prev) => ({
            ...prev,
            [deviceId]: { status: "error", deviceName, message: detail },
          }));
          notify.error(detail || `${deviceName} SNMP 发现失败`);
          onDone?.();
        }
      })();
    },
    [finishDiscover, notify],
  );

  const discoverBatch = useCallback(
    (devices: Device[], onDone?: () => void) => {
      const ids = devices.map((d) => d.id);
      if (!ids.length) return;

      for (const d of devices) {
        setJobs((prev) => ({
          ...prev,
          [d.id]: { status: "discovering", deviceName: d.name },
        }));
      }

      void (async () => {
        try {
          await api.post<BatchOut>("/devices/discover-interfaces-batch", { device_ids: ids });
          notify.success(`已启动 ${ids.length} 台设备并行 SNMP 接口扫描`);
          let remaining = devices.length;
          const doneOne = () => {
            remaining -= 1;
            if (remaining <= 0) onDone?.();
          };
          for (const d of devices) {
            void (async () => {
              const startedAt = Date.now();
              let baselineCount = 0;
              try {
                const { data: existing } = await api.get<DeviceInterface[]>(
                  `/devices/${d.id}/interfaces`,
                );
                baselineCount = existing.length;
              } catch {
                baselineCount = 0;
              }
              const ifaces = await pollDiscoverComplete(d.id, startedAt, baselineCount);
              finishDiscover(d.id, d.name, ifaces, doneOne);
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
          notify.error(detail || "批量 SNMP 发现失败");
          onDone?.();
        }
      })();
    },
    [finishDiscover, notify],
  );

  return {
    getJob,
    discoverOne,
    discoverBatch,
    activeDiscoverCount,
  };
}
