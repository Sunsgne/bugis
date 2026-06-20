import { useCallback, useRef, useState } from "react";
import { App as AntApp } from "antd";
import { api } from "@/api/client";
import type { TopologyNodePositions } from "@/components/PhysicalTopologyFlow";
import { useTc } from "@/i18n/useTc";

const AUTO_SAVE_KEY = "topology-layout-auto-save";

function positionsEqual(a: TopologyNodePositions, b: TopologyNodePositions): boolean {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  return keysA.every((k) => a[k]?.x === b[k]?.x && a[k]?.y === b[k]?.y);
}

function readAutoSavePref(): boolean {
  try {
    return localStorage.getItem(AUTO_SAVE_KEY) === "true";
  } catch {
    return false;
  }
}

export function useTopologyLayout() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [savedPositions, setSavedPositions] = useState<TopologyNodePositions>({});
  const [draftPositions, setDraftPositions] = useState<TopologyNodePositions>({});
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [autoSave, setAutoSave] = useState(readAutoSavePref);
  const layoutLoaded = useRef(false);
  const layoutDirtyRef = useRef(false);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  layoutDirtyRef.current = layoutDirty;

  const loadLayout = useCallback(async () => {
    const { data } = await api.get<{ positions: TopologyNodePositions }>("/capacity/topology/layout");
    const serverPositions = data.positions ?? {};
    setSavedPositions(serverPositions);
    if (!layoutLoaded.current || !layoutDirtyRef.current) {
      setDraftPositions(serverPositions);
      layoutLoaded.current = true;
    }
    return serverPositions;
  }, []);

  const saveLayout = useCallback(
    async (positions?: TopologyNodePositions) => {
      const payload = positions ?? draftPositions;
      setSaving(true);
      try {
        const { data } = await api.put<{ positions: TopologyNodePositions }>("/capacity/topology/layout", {
          positions: payload,
        });
        const next = data.positions ?? payload;
        setSavedPositions(next);
        setDraftPositions(next);
        setLayoutDirty(false);
        message.success(tc("拓扑布局已保存"));
        return next;
      } catch {
        message.error(tc("保存拓扑布局失败"));
        return null;
      } finally {
        setSaving(false);
      }
    },
    [draftPositions, message, tc],
  );

  const resetLayout = useCallback(async () => {
    setSaving(true);
    try {
      const { data } = await api.put<{ positions: TopologyNodePositions }>("/capacity/topology/layout", {
        positions: {},
      });
      const next = data.positions ?? {};
      setSavedPositions(next);
      setDraftPositions(next);
      setLayoutDirty(false);
      message.success(tc("已恢复自动布局"));
      return next;
    } catch {
      message.error(tc("重置拓扑布局失败"));
      return null;
    } finally {
      setSaving(false);
    }
  }, [message, tc]);

  const handlePositionsChange = useCallback(
    (positions: TopologyNodePositions, options?: { autoSave?: boolean }) => {
      setDraftPositions(positions);
      const dirty = !positionsEqual(positions, savedPositions);
      setLayoutDirty(dirty);
      const shouldAutoSave = options?.autoSave ?? autoSave;
      if (autoSaveTimer.current) {
        clearTimeout(autoSaveTimer.current);
        autoSaveTimer.current = null;
      }
      if (shouldAutoSave && dirty) {
        autoSaveTimer.current = setTimeout(() => {
          void saveLayout(positions);
        }, 450);
      }
    },
    [autoSave, savedPositions, saveLayout],
  );

  const toggleAutoSave = useCallback((checked: boolean) => {
    setAutoSave(checked);
    try {
      localStorage.setItem(AUTO_SAVE_KEY, String(checked));
    } catch {
      /* ignore */
    }
  }, []);

  return {
    savedPositions,
    draftPositions,
    layoutDirty,
    saving,
    autoSave,
    loadLayout,
    saveLayout,
    resetLayout,
    handlePositionsChange,
    toggleAutoSave,
    setDraftPositions,
  };
}
