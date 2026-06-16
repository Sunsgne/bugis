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
  if (u.tenant_name) parts.push(`客户 ${u.tenant_name}`);
  if (u.circuit_code) parts.push(`专线 ${u.circuit_code}`);
  if (u.vni != null) parts.push(`VNI ${u.vni}`);
  if (u.rate_limit_mbps) parts.push(`限速 ${u.rate_limit_mbps}M`);
  if (u.description) parts.push(u.description);
  if (u.note) parts.push(u.note);
  return parts.join(" · ");
}

function tagColor(u: SvidUsage): string {
  return SVID_SOURCE[u.source || ""]?.color || SVID_SOURCE.platform.color;
}

export function formatRateLimit(u: SvidUsage): string {
  const mbps = u.rate_limit_mbps ?? u.bandwidth_mbps;
  if (!mbps) return "—";
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
}

function formatBusiness(u: SvidUsage): string {
  return u.circuit_name || u.vsi_name || u.description || u.circuit_code || "—";
}

function formatCustomer(u: SvidUsage): string {
  if (u.tenant_name) {
    return u.tenant_code ? `${u.tenant_name} (${u.tenant_code})` : u.tenant_name;
  }
  if (u.vsi_name?.toLowerCase().startsWith("cus-")) {
    return u.vsi_name;
  }
  return "—";
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
      const haystack = [
        svidUsageLabel(u),
        u.circuit_code,
        u.circuit_name,
        u.tenant_name,
        u.tenant_code,
        u.description,
        u.note,
        u.vsi_name,
        formatBusiness(u),
        formatRateLimit(u),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [list, search]);

  return (
    <div style={{ width: 860, maxWidth: "min(96vw, 860px)" }}>
      <Input.Search
        allowClear
        placeholder="搜索客户 / 接口 / 业务 / S-VID / 限速"
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
        scroll={{ x: 820, y: 300 }}
        columns={[
          {
            title: "客户",
            width: 120,
            fixed: "left",
            ellipsis: true,
            render: (_: unknown, u?: SvidUsage) => formatCustomer(u || {}),
          },
          {
            title: "业务",
            width: 140,
            ellipsis: true,
            render: (_: unknown, u?: SvidUsage) => formatBusiness(u || {}),
          },
          {
            title: "S-VID",
            width: 96,
            render: (_: unknown, u?: SvidUsage) => (
              <Tag color={tagColor(u || {})} style={{ margin: 0 }}>
                {svidUsageLabel(u || {})}
              </Tag>
            ),
          },
          {
            title: "限速带宽",
            width: 88,
            render: (_: unknown, u?: SvidUsage) => formatRateLimit(u || {}),
          },
          {
            title: "VNI",
            dataIndex: "vni",
            width: 72,
            render: (v?: number) => (v != null ? v : "—"),
          },
          {
            title: "描述",
            dataIndex: "description",
            width: 140,
            ellipsis: true,
            render: (v?: string) => v || "—",
          },
          {
            title: "专线",
            dataIndex: "circuit_code",
            width: 96,
            ellipsis: true,
            render: (v?: string) => v || "—",
          },
          {
            title: "来源",
            width: 72,
            render: (_: unknown, u?: SvidUsage) =>
              SVID_SOURCE[u?.source || "platform"]?.label || u?.source || "—",
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
      {visible.map((u, idx) => {
        const bw = formatRateLimit(u);
        const label =
          bw !== "—" ? `${svidUsageLabel(u)} · ${bw}` : svidUsageLabel(u);
        return (
          <Tag key={idx} color={tagColor(u)} style={{ margin: 0, maxWidth: 120 }} title={svidUsageTitle(u)}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
          </Tag>
        );
      })}
      {rest > 0 ? (
        <Popover trigger="click" placement="left" title={popoverTitle} content={popoverContent}>
          <Tag style={{ margin: 0, cursor: "pointer" }}>+{rest}</Tag>
        </Popover>
      ) : (
        <Popover trigger="click" placement="left" title={popoverTitle} content={popoverContent}>
          <Button type="link" size="small" style={{ padding: 0, height: "auto" }}>
            明细
          </Button>
        </Popover>
      )}
    </Space>
  );
}
