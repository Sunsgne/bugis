import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { DeviceInterface } from "@/api/types";

export type SnmpDiscoverJobStatus = "idle" | "discovering" | "success" | "error";

export type SnmpDiscoverJob = {
  status: SnmpDiscoverJobStatus;
  deviceName: string;
  message?: string;
};

function notifyDiscoverResult(
  data: DeviceInterface[],
  deviceName: string,
  notify: {
    success: (msg: string) => void;
    warning: (msg: string, duration?: number) => void;
    info: (msg: string) => void;
  },
) {
  const simCount = data.filter((i) => i.discovered_via === "snmp-sim").length;
  const cfgCount = data.filter((i) => i.discovered_via === "running-config").length;
  const svidCount = data.filter((i) => i.used_s_vids?.length).length;
  if (simCount === data.length) {
    notify.warning(
      `${deviceName} · 返回模拟数据（SNMP 不可达）。请确认 Community/端口后重试`,
      6,
    );
    return;
  }
  if (cfgCount > 0 && !data.some((i) => i.discovered_via === "snmp")) {
    notify.info(
      `${deviceName} · SNMP 不可达，已从 running-config 解析 ${data.length} 个物理口`,
    );
    return;
  }
  if (simCount > 0) {
    notify.warning(`${deviceName} · 部分接口为模拟数据（${simCount}/${data.length}）`);
    return;
  }
  notify.success(`${deviceName} · SNMP 发现 ${data.length} 个接口 · ${svidCount} 个端口有 S-VID`);
  if (svidCount === 0) {
    notify.info(`${deviceName} · S-VID 需现网学习后重新检测`);
  }
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

  const discoverOne = useCallback(
    async (deviceId: number, deviceName: string, onDone?: () => void) => {
      setJobs((prev) => ({
        ...prev,
        [deviceId]: { status: "discovering", deviceName },
      }));
      try {
        const { data } = await api.post<DeviceInterface[]>(
          `/devices/${deviceId}/discover-interfaces`,
        );
        notifyDiscoverResult(data, deviceName, notify);
        setJobs((prev) => ({
          ...prev,
          [deviceId]: { status: "success", deviceName },
        }));
        onDone?.();
        return data;
      } catch (e: unknown) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
        setJobs((prev) => ({
          ...prev,
          [deviceId]: { status: "error", deviceName, message: detail },
        }));
        notify.error(detail || `${deviceName} SNMP 发现失败`);
        onDone?.();
        throw e;
      }
    },
    [notify],
  );

  return {
    getJob,
    discoverOne,
    activeDiscoverCount,
  };
}
