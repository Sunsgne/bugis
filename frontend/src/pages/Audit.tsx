import { useEffect, useState } from "react";
import { Input, Table, Tag, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { AuditEntry } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { empty, page } from "../constants/uiCopy";

const METHOD_COLOR: Record<string, string> = {
  POST: "green",
  PATCH: "orange",
  PUT: "orange",
  DELETE: "red",
};

export default function Audit({ embedded }: { embedded?: boolean }) {
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

  const search = (
    <Input.Search
      placeholder="按操作人筛选"
      allowClear
      style={{ width: 220 }}
      onSearch={setActor}
      enterButton={<ReloadOutlined />}
    />
  );

  const table = (
    <Table
      rowKey="id"
      loading={loading}
      dataSource={rows}
      {...dataTableProps()}
      locale={{ emptyText: empty.default }}
      columns={[
        {
          title: "时间",
          dataIndex: "created_at",
          width: "14%",
          render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "—"),
        },
        { title: "操作人", dataIndex: "actor", width: "12%", render: (a) => <Tag>{a}</Tag> },
        {
          title: "方法",
          dataIndex: "method",
          width: "8%",
          render: (m) => <Tag color={METHOD_COLOR[m]}>{m}</Tag>,
        },
        { title: "路径", dataIndex: "path", width: "32%", ellipsis: true },
        {
          title: "状态码",
          dataIndex: "status_code",
          width: "8%",
          render: (c) => (
            <Tag color={c < 300 ? "green" : c < 500 ? "orange" : "red"}>{c}</Tag>
          ),
        },
        { title: "来源 IP", dataIndex: "source_ip", width: "14%", ellipsis: true, render: (v) => v || "—" },
      ]}
    />
  );

  if (embedded) {
    return (
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            {page.audit}
          </Typography.Title>
          {search}
        </div>
        {table}
      </div>
    );
  }

  return (
    <PageCard title={page.audit} extra={search}>
      {table}
    </PageCard>
  );
}
