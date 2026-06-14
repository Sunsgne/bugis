import { useEffect, useState } from "react";
import { Button, Card, Input, Table, Tag } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { AuditEntry } from "../api/types";

const METHOD_COLOR: Record<string, string> = {
  POST: "green",
  PATCH: "orange",
  PUT: "orange",
  DELETE: "red",
};

export default function Audit() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [actor, setActor] = useState("");

  async function load() {
    setLoading(true);
    try {
      const q = actor ? `?actor=${encodeURIComponent(actor)}` : "";
      const { data } = await api.get<AuditEntry[]>(`/audit${q}`);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [actor]);

  return (
    <Card
      title="操作审计"
      extra={
        <Input.Search
          placeholder="按操作人过滤"
          allowClear
          style={{ width: 220 }}
          onSearch={setActor}
          enterButton={<ReloadOutlined />}
        />
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={[
          {
            title: "时间",
            dataIndex: "created_at",
            width: 180,
            render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "-"),
          },
          { title: "操作人", dataIndex: "actor", render: (a) => <Tag>{a}</Tag> },
          {
            title: "方法",
            dataIndex: "method",
            width: 90,
            render: (m) => <Tag color={METHOD_COLOR[m]}>{m}</Tag>,
          },
          { title: "路径", dataIndex: "path" },
          {
            title: "状态码",
            dataIndex: "status_code",
            width: 90,
            render: (c) => (
              <Tag color={c < 300 ? "green" : c < 500 ? "orange" : "red"}>{c}</Tag>
            ),
          },
          { title: "来源 IP", dataIndex: "source_ip" },
        ]}
      />
    </Card>
  );
}
