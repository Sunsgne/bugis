import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Device } from "@/api/types";

export type LearnJobStatus = "idle" | "learning" | "success" | "error";

export type LearnJob = {
  status: LearnJobStatus;
  deviceName: string;
  message?: string;
};

type BatchResult = {
  total: number;
  success: number;
  failed: number;
  max_workers: number;
  results: Array<{ device_id?: number; device?: string; success?: boolean; error?: string }>;
};

export function useLearnJobs(notify: {
  success: (msg: string) => void;
  warning: (msg: string) => void;
  error: (msg: string) => void;
  loading: (msg: string, duration?: number) => () => void;
}) {
  const [jobs, setJobs] = useState<Record<number, LearnJob>>({});

  const activeLearnCount = useMemo(
    () => Object.values(jobs).filter((j) => j.status === "learning").length,
    [jobs],
  );

  const getJob = useCallback(
    (deviceId: number): LearnJob | null => jobs[deviceId] ?? null,
    [jobs],
  );

  const learnOne = useCallback(
    async (device: Device, onDone?: () => void) => {
      setJobs((prev) => ({
        ...prev,
        [device.id]: { status: "learning", deviceName: device.name },
      }));
      try {
        const { data } = await api.post(`/devices/${device.id}/learn`);
        if (data.success) {
          const inv = data.inventory;
          setJobs((prev) => ({
            ...prev,
            [device.id]: {
              status: "success",
              deviceName: device.name,
              message: `v${data.snapshot_version} · ${inv?.service_count ?? 0} 业务`,
            },
          }));
          notify.success(`${device.name} 学习完成 · v${data.snapshot_version}`);
        } else {
          setJobs((prev) => ({
            ...prev,
            [device.id]: {
              status: "error",
              deviceName: device.name,
              message: data.error,
            },
          }));
          notify.error(data.error || `${device.name} 学习失败`);
        }
        onDone?.();
        return data;
      } catch (e: unknown) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setJobs((prev) => ({
          ...prev,
          [device.id]: {
            status: "error",
            deviceName: device.name,
            message: detail,
          },
        }));
        notify.error(detail || `${device.name} 学习失败`);
        throw e;
      }
    },
    [notify],
  );

  const learnBatch = useCallback(
    async (devices: Device[], onDone?: () => void) => {
      const ids = devices.map((d) => d.id);
      if (!ids.length) return null;

      for (const d of devices) {
        setJobs((prev) => ({
          ...prev,
          [d.id]: { status: "learning", deviceName: d.name },
        }));
      }

      const hide = notify.loading(`现网配置并行学习中 · ${ids.length} 台设备…`, 0);
      try {
        const { data } = await api.post<BatchResult>("/devices/learn-batch", {
          device_ids: ids,
        });
        hide();

        for (const r of data.results) {
          const id = r.device_id;
          if (id == null) continue;
          const name = r.device || devices.find((d) => d.id === id)?.name || String(id);
          setJobs((prev) => ({
            ...prev,
            [id]: {
              status: r.success ? "success" : "error",
              deviceName: name,
              message: r.error,
            },
          }));
        }

        if (data.failed === 0) {
          notify.success(`并行学习完成 · ${data.success}/${data.total} 成功 · ${data.max_workers} 线程`);
        } else {
          notify.warning(`并行学习完成 · 成功 ${data.success}/${data.total} · 失败 ${data.failed}`);
        }
        onDone?.();
        return data;
      } catch (e: unknown) {
        hide();
        for (const d of devices) {
          setJobs((prev) => ({
            ...prev,
            [d.id]: { status: "error", deviceName: d.name, message: "batch failed" },
          }));
        }
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        notify.error(detail || "批量学习失败");
        throw e;
      }
    },
    [notify],
  );

  const watchScheduledLearn = useCallback(
    (deviceId: number, deviceName: string, onDone?: () => void) => {
      setJobs((prev) => ({
        ...prev,
        [deviceId]: { status: "learning", deviceName },
      }));

      const poll = async () => {
        const maxAttempts = 120;
        for (let i = 0; i < maxAttempts; i += 1) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const { data } = await api.get<{
              has_learned_config?: boolean;
              last_run_status?: string | null;
              latest_snapshot_version?: number | null;
              inventory?: { service_count?: number };
            }>(`/devices/${deviceId}/learned-state`);
            if (data.has_learned_config) {
              const ver = data.latest_snapshot_version;
              const svc = data.inventory?.service_count ?? 0;
              setJobs((prev) => ({
                ...prev,
                [deviceId]: {
                  status: "success",
                  deviceName,
                  message: ver != null ? `v${ver} · ${svc} 业务` : undefined,
                },
              }));
              notify.success(`${deviceName} 现网学习完成${ver != null ? ` · v${ver}` : ""}`);
              onDone?.();
              return;
            }
            if (data.last_run_status === "failed") {
              setJobs((prev) => ({
                ...prev,
                [deviceId]: {
                  status: "error",
                  deviceName,
                  message: "learn failed",
                },
              }));
              notify.error(`${deviceName} 现网学习失败`);
              onDone?.();
              return;
            }
          } catch {
            /* keep polling */
          }
        }
        setJobs((prev) => ({
          ...prev,
          [deviceId]: {
            status: "error",
            deviceName,
            message: "timeout",
          },
        }));
        notify.warning(`${deviceName} 现网学习超时，请稍后在设备页手动重试`);
        onDone?.();
      };

      void poll();
    },
    [notify],
  );

  const watchScheduledLearnBatch = useCallback(
    (devices: Array<{ id: number; name: string }>, onDone?: () => void) => {
      if (!devices.length) return;
      let remaining = devices.length;
      const doneOne = () => {
        remaining -= 1;
        if (remaining <= 0) onDone?.();
      };
      for (const d of devices) {
        watchScheduledLearn(d.id, d.name, doneOne);
      }
    },
    [watchScheduledLearn],
  );

  return {
    getJob,
    learnOne,
    learnBatch,
    watchScheduledLearn,
    watchScheduledLearnBatch,
    activeLearnCount,
  };
}
