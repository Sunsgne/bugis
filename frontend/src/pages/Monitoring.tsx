import { useEffect, useState } from "react";
import { Button, Col, Row, Select, Space, App as AntApp } from "antd";
import { ExperimentOutlined, ReloadOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Circuit } from "../api/types";
import CircuitMonitorPanel from "../components/CircuitMonitorPanel";
import PageCard from "../components/PageCard";
import { action } from "../constants/uiCopy";
import { fetchAllPages } from "../utils/pagination";

export default function Monitoring() {
  const { message } = AntApp.useApp();
  const [params, setParams] = useSearchParams();
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  async function loadCircuits() {
    const items = await fetchAllPages<Circuit>("/circuits", { status: "active" });
    setCircuits(items);
    const fromUrl = Number(params.get("circuit"));
    if (fromUrl && items.some((c) => c.id === fromUrl)) {
      setSelected(fromUrl);
    } else if (!selected && items.length) {
      setSelected(items[0].id);
    }
  }

  useEffect(() => {
    loadCircuits();
  }, []);

  function selectCircuit(id: number) {
    setSelected(id);
    setParams({ circuit: String(id) });
  }

  async function simulate() {
    const { data } = await api.post("/telemetry/simulate");
    message.success(`已采集 ${data.generated} 条 SNMP/模拟采样`);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PageCard>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Select
              style={{ width: 360 }}
              value={selected ?? undefined}
              onChange={selectCircuit}
              placeholder="选择专线"
              showSearch
              optionFilterProp="label"
              options={circuits.map((c) => ({
                value: c.id,
                label: `${c.code} · ${c.name}`,
              }))}
            />
          </Col>
          <Col>
            <Space>
              <Button icon={<ExperimentOutlined />} onClick={simulate} type="primary" ghost>
                立即采集
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => setRefreshKey((k) => k + 1)}>
                {action.refresh}
              </Button>
            </Space>
          </Col>
        </Row>
      </PageCard>

      {selected ? (
        <CircuitMonitorPanel key={`${selected}-${refreshKey}`} circuitId={selected} pollSec={15} />
      ) : null}
    </div>
  );
}
