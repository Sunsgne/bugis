import { Button, Input, Popover, Space, Table, Tag, Typography } from "antd";
import { useMemo, useState } from "react";
import type { SvidUsage } from "@/api/types";

const SVID_SOURCE: Record<string, { label: string; color: string }> = {
  platform: { label: "平台", color: "blue" },
  device: { label: "设备", color: "orange" },
  legacy: { label: "手工", color: "red" },
};

export function svidUsageLabel(u: SvidUsage): string {
  if (u.access_mode === "access") return "untagged";
  if (u.c_vid != null && u.s_vid != null) return `S:${u.s_vid}/C:${u.c_vid}`;
  if (u.s_vid != null) return `S:${u.s_vid}`;
  return "unknown";
}

export function svidUsageTitle(u: SvidUsage): string {
  const src = SVID_SOURCE[u.source || "platform"]?.label || u.source || "平台";
  const parts = [`来源: ${src}`];
  if (u.circuit_code) parts.push(`专线 ${u.circuit_code}`);
  if (u.note) parts.push(u.note);
  return parts.join(" · ");
}

function tagColor(u: SvidUsage): string {
  return SVID_SOURCE[u.source || ""]?.color || SVID_SOURCE.platform.color;
}

type DetailProps = {
  list: SvidUsage[];
};

function SvidUsageDetailPanel({ list }: DetailProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((u) => {
      const label = svidUsageLabel(u).toLowerCase();
      const circuit = u.circuit_code?.toLowerCase() || "";
      const note = u.note?.toLowerCase() || "";
      const src = (SVID_SOURCE[u.source || "platform"]?.label || u.source || "").toLowerCase();
      return (
        label.includes(q) ||
        circuit.includes(q) ||
        note.includes(q) ||
        src.includes(q) ||
        String(u.s_vid ?? "").includes(q) ||
        String(u.c_vid ?? "").includes(q)
      );
    });
  }, [list, search]);

  return (
    <div style={{ width: 420, maxWidth: "min(92vw, 420px)" }}>
      <Input.Search
        allowClear
        placeholder="搜索 S-VID / 专线 / 来源"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <Table
        size="small"
        rowKey={(_, idx) => String(idx)}
        dataSource={filtered}
        pagination={{
          pageSize: 10,
          size: "small",
          showSizeChanger: filtered.length > 20,
          pageSizeOptions: ["10", "20", "50"],
          showTotal: (t) => `共 ${t} 个`,
        }}
        scroll={{ y: 280 }}
        columns={[
          {
            title: "VLAN",
            width: 120,
            render: (_: unknown, u: SvidUsage) => (
              <Tag color={tagColor(u)} style={{ margin: 0 }}>
                {svidUsageLabel(u)}
              </Tag>
            ),
          },
          {
            title: "专线",
            dataIndex: "circuit_code",
            width: 100,
            ellipsis: true,
            render: (v?: string) => v || "—",
          },
          {
            title: "来源",
            width: 72,
            render: (_: unknown, u: SvidUsage) => SVID_SOURCE[u.source || "platform"]?.label || u.source || "—",
          },
          {
            title: "备注",
            dataIndex: "note",
            ellipsis: true,
            render: (v?: string) => v || "—",
          },
        ]}
      />
    </div>
  );
}

type Props = {
  list?: SvidUsage[] | null;
  /** Max tags shown inline before collapsing to +N */
  inlineMax?: number;
  /** Above this count, show summary link only (no inline tags) */
  summaryThreshold?: number;
};

export default function SvidUsageCell({ list, inlineMax = 2, summaryThreshold = 8 }: Props) {
  if (!list?.length) {
    return <Typography.Text type="secondary">—</Typography.Text>;
  }

  const count = list.length;
  const popoverTitle = `S-VID 占用 · ${count.toLocaleString()} 个`;
  const popoverContent = <SvidUsageDetailPanel list={list} />;

  if (count > summaryThreshold) {
    return (
      <Popover trigger="click" placement="left" title={popoverTitle} content={popoverContent}>
        <Button type="link" size="small" style={{ padding: 0, height: "auto", fontWeight: 500 }}>
          {count.toLocaleString()} 个 S-VID
        </Button>
      </Popover>
    );
  }

  const visible = list.slice(0, inlineMax);
  const rest = count - visible.length;

  return (
    <Space size={4} wrap={false} style={{ maxWidth: "100%" }}>
      {visible.map((u, idx) => (
        <Tag key={idx} color={tagColor(u)} style={{ margin: 0, maxWidth: 96 }} title={svidUsageTitle(u)}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{svidUsageLabel(u)}</span>
        </Tag>
      ))}
      {rest > 0 ? (
        <Popover trigger="click" placement="left" title={popoverTitle} content={popoverContent}>
          <Tag style={{ margin: 0, cursor: "pointer" }}>+{rest}</Tag>
        </Popover>
      ) : null}
    </Space>
  );
}
