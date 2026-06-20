import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, App as AntApp, Button, Space } from "antd";
import { ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { LinkUsage, Topology as Topo } from "../api/types";
import PageCard from "@/components/PageCard";
import PhysicalTopologyFlow, { type TopologyNodePositions } from "@/components/PhysicalTopologyFlow";
import { Badge } from "@/components/ui/badge";
import { empty, page } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";

function positionsEqual(a: TopologyNodePositions, b: TopologyNodePositions): boolean {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  return keysA.every((k) => a[k]?.x === b[k]?.x && a[k]?.y === b[k]?.y);
}

export default function Topology() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [topo, setTopo] = useState<Topo | null>(null);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [savedPositions, setSavedPositions] = useState<TopologyNodePositions>({});
  const [draftPositions, setDraftPositions] = useState<TopologyNodePositions>({});
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const layoutLoaded = useRef(false);

  async function load() {
    try {
      const [topoRes, linksRes, layoutRes] = await Promise.all([
        api.get<Topo>("/capacity/topology"),
        api.get<LinkUsage[]>("/capacity/links/usage"),
        api.get<{ positions: TopologyNodePositions }>("/capacity/topology/layout"),
      ]);
      setTopo(topoRes.data);
      setLinks(linksRes.data);
      const serverPositions = layoutRes.data.positions ?? {};
      setSavedPositions(serverPositions);
      if (!layoutLoaded.current || !layoutDirty) {
        setDraftPositions(serverPositions);
        layoutLoaded.current = true;
      }
      setError(false);
    } catch {
      setError(true);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const handlePositionsChange = useCallback(
    (positions: TopologyNodePositions) => {
      setDraftPositions(positions);
      setLayoutDirty(!positionsEqual(positions, savedPositions));
    },
    [savedPositions],
  );

  async function saveLayout() {
    setSaving(true);
    try {
      const { data } = await api.put<{ positions: TopologyNodePositions }>("/capacity/topology/layout", {
        positions: draftPositions,
      });
      const next = data.positions ?? draftPositions;
      setSavedPositions(next);
      setDraftPositions(next);
      setLayoutDirty(false);
      message.success(tc("拓扑布局已保存"));
    } catch {
      message.error(tc("保存拓扑布局失败"));
    } finally {
      setSaving(false);
    }
  }

  async function resetLayout() {
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
    } catch {
      message.error(tc("重置拓扑布局失败"));
    } finally {
      setSaving(false);
    }
  }

  if (error && !topo) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">{tc("拓扑数据加载失败，将自动重试…")}</div>
    );
  }

  if (!topo) {
    return <div className="py-16 text-center text-sm text-muted-foreground">{empty.data}</div>;
  }

  if (!topo.nodes.length) {
    return <div className="py-16 text-center text-sm text-muted-foreground">{empty.devices}</div>;
  }

  const linkStats = {
    dci: topo.edges.filter((e) => e.type === "dci").length,
    fabric: topo.edges.filter((e) => e.type === "intra_dc").length,
  };

  return (
    <PageCard
      className="topology-page-card"
      title={page.topology}
      extra={
        <Space wrap size="middle">
          <Badge variant="destructive">DCI {linkStats.dci}</Badge>
          <Badge variant="info">Fabric {linkStats.fabric}</Badge>
          <span className="text-xs text-muted-foreground">{tc("滚轮缩放 · 拖拽平移 · 拖动设备可调整布局")}</span>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            disabled={!layoutDirty}
            loading={saving}
            onClick={saveLayout}
          >
            {tc("保存布局")}
          </Button>
          <Button icon={<ReloadOutlined />} loading={saving} onClick={resetLayout}>
            {tc("恢复自动布局")}
          </Button>
        </Space>
      }
    >
      {topo.edges.length === 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={tc("尚未配置站点间链路")}
          description={tc("设备节点按互联关系自动布局；在「容量规划」中添加 DCI / Fabric 链路后，将显示设备间连线与带宽利用率。")}
        />
      )}
      <div className="topology-page-body">
        <PhysicalTopologyFlow
          topo={topo}
          links={links}
          savedPositions={draftPositions}
          onPositionsChange={handlePositionsChange}
        />
      </div>
    </PageCard>
  );
}
