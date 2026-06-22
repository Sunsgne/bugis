import { useCallback, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Circuit } from "@/api/types";

export type CircuitDeleteJobStatus = "deleting" | "success" | "error";

export type CircuitDeleteJob = {
  status: CircuitDeleteJobStatus;
  circuitCode: string;
  message?: string;
};

type DeleteScheduled = {
  scheduled: boolean;
  circuit_id: number;
  circuit_code: string;
};

async function pollCircuitDeleted(circuitId: number): Promise<boolean> {
  const maxAttempts = 90;
  for (let i = 0; i < maxAttempts; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    try {
      await api.get(`/circuits/${circuitId}`);
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        return true;
      }
      throw e;
    }
  }
  return false;
}

export function useCircuitDeleteJobs(notify: {
  success: (msg: string) => void;
  error: (msg: string) => void;
}) {
  const [jobs, setJobs] = useState<Record<number, CircuitDeleteJob>>({});

  const activeDeleteCount = useMemo(
    () => Object.values(jobs).filter((job) => job.status === "deleting").length,
    [jobs],
  );

  const getJob = useCallback(
    (circuitId: number): CircuitDeleteJob | null => jobs[circuitId] ?? null,
    [jobs],
  );

  const deleteOne = useCallback(
    async (circuit: Circuit, onDone?: () => void) => {
      setJobs((prev) => ({
        ...prev,
        [circuit.id]: { status: "deleting", circuitCode: circuit.code },
      }));
      try {
        await api.delete<DeleteScheduled>(`/circuits/${circuit.id}`, {
          params: { background: true },
        });
        const deleted = await pollCircuitDeleted(circuit.id);
        if (!deleted) {
          setJobs((prev) => ({
            ...prev,
            [circuit.id]: {
              status: "error",
              circuitCode: circuit.code,
              message: "timeout",
            },
          }));
          notify.error(`${circuit.code} 删除超时，请稍后刷新列表确认`);
          onDone?.();
          return false;
        }
        setJobs((prev) => ({
          ...prev,
          [circuit.id]: { status: "success", circuitCode: circuit.code },
        }));
        notify.success(`专线 ${circuit.code} 已删除`);
        onDone?.();
        return true;
      } catch (e: unknown) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
        setJobs((prev) => ({
          ...prev,
          [circuit.id]: {
            status: "error",
            circuitCode: circuit.code,
            message: detail,
          },
        }));
        notify.error(detail || `${circuit.code} 删除失败`);
        onDone?.();
        return false;
      }
    },
    [notify],
  );

  const clearJob = useCallback((circuitId: number) => {
    setJobs((prev) => {
      if (!(circuitId in prev)) return prev;
      const next = { ...prev };
      delete next[circuitId];
      return next;
    });
  }, []);

  return {
    getJob,
    deleteOne,
    clearJob,
    activeDeleteCount,
  };
}
