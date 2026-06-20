import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Device, DeviceInterface } from "@/api/types";

export type InterfaceDescSaveStatus = "idle" | "saving" | "success" | "error";

export type InterfaceDescSaveJob = {
  status: InterfaceDescSaveStatus;
  deviceName: string;
  message?: string;
  updated?: number;
};

type SaveItem = { name: string; description: string };

function diffDescriptionItems(
  physicalPorts: DeviceInterface[],
  draft: Record<string, string>,
): SaveItem[] {
  return physicalPorts
    .map((i) => ({ name: i.name, description: (draft[i.name] ?? "").trim() }))
    .filter((i) => i.description !== (physicalPorts.find((p) => p.name === i.name)?.description || ""));
}

export function useInterfaceDescJobs(notify: {
  success: (msg: string) => void;
  warning: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<number, Record<string, string>>>({});
  const [editingIds, setEditingIds] = useState<Set<number>>(() => new Set());
  const [jobs, setJobs] = useState<Record<number, InterfaceDescSaveJob>>({});

  const activeSaveCount = useMemo(
    () => Object.values(jobs).filter((j) => j.status === "saving").length,
    [jobs],
  );

  const isEditing = useCallback((deviceId?: number | null) => {
    if (deviceId == null) return false;
    return editingIds.has(deviceId);
  }, [editingIds]);

  const getDraft = useCallback(
    (deviceId: number) => drafts[deviceId] ?? {},
    [drafts],
  );

  const getJob = useCallback(
    (deviceId: number): InterfaceDescSaveJob | null => jobs[deviceId] ?? null,
    [jobs],
  );

  const beginEdit = useCallback((deviceId: number, physicalPorts: DeviceInterface[]) => {
    const draft: Record<string, string> = {};
    for (const i of physicalPorts) draft[i.name] = i.description || "";
    setDrafts((prev) => ({ ...prev, [deviceId]: draft }));
    setEditingIds((prev) => new Set(prev).add(deviceId));
    setJobs((prev) => {
      if (prev[deviceId]?.status === "saving") return prev;
      const next = { ...prev };
      delete next[deviceId];
      return next;
    });
  }, []);

  const cancelEdit = useCallback((deviceId: number) => {
    setEditingIds((prev) => {
      const next = new Set(prev);
      next.delete(deviceId);
      return next;
    });
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[deviceId];
      return next;
    });
  }, []);

  const updateDraft = useCallback((deviceId: number, name: string, value: string) => {
    setDrafts((prev) => ({
      ...prev,
      [deviceId]: { ...(prev[deviceId] ?? {}), [name]: value },
    }));
  }, []);

  const enqueueSave = useCallback(
    (device: Device, physicalPorts: DeviceInterface[]) => {
      const draft = drafts[device.id];
      if (!draft) return;
      const items = diffDescriptionItems(physicalPorts, draft);
      if (items.length === 0) {
        notify.info("没有需要保存的描述变更");
        cancelEdit(device.id);
        return;
      }

      setEditingIds((prev) => {
        const next = new Set(prev);
        next.delete(device.id);
        return next;
      });
      setJobs((prev) => ({
        ...prev,
        [device.id]: { status: "saving", deviceName: device.name },
      }));

      void (async () => {
        try {
          const { data } = await api.post<{
            updated: number;
            pushed: boolean;
            dry_run: boolean;
          }>(`/devices/${device.id}/interfaces/descriptions`, { items, push: true });

          let message: string;
          if (data.dry_run) {
            message = `已保存 ${data.updated} 个接口描述（Dry-run）`;
          } else if (data.pushed) {
            message = `已保存并下发 ${data.updated} 个接口描述`;
          } else {
            message = `已保存 ${data.updated} 个接口描述，但下发失败`;
          }

          setJobs((prev) => ({
            ...prev,
            [device.id]: {
              status: data.pushed || data.dry_run ? "success" : "error",
              deviceName: device.name,
              message,
              updated: data.updated,
            },
          }));
          setDrafts((prev) => {
            const next = { ...prev };
            delete next[device.id];
            return next;
          });

          if (data.dry_run) notify.success(`${device.name}：${message}`);
          else if (data.pushed) notify.success(`${device.name}：${message}`);
          else notify.warning(`${device.name}：${message}`);
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } } };
          const detail = err?.response?.data?.detail || "保存接口描述失败";
          setJobs((prev) => ({
            ...prev,
            [device.id]: { status: "error", deviceName: device.name, message: detail },
          }));
          notify.error(`${device.name}：${detail}`);
        }
      })();
    },
    [cancelEdit, drafts, notify],
  );

  const clearJob = useCallback((deviceId: number) => {
    setJobs((prev) => {
      const next = { ...prev };
      delete next[deviceId];
      return next;
    });
  }, []);

  return {
    activeSaveCount,
    isEditing,
    getDraft,
    getJob,
    beginEdit,
    cancelEdit,
    updateDraft,
    enqueueSave,
    clearJob,
    jobs,
  };
}
