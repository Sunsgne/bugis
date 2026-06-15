import type { TablePaginationConfig } from "antd";

export function buildListQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export function tablePagination(
  total: number,
  page: number,
  pageSize: number,
  onChange: (page: number, pageSize: number) => void,
): TablePaginationConfig {
  return {
    current: page,
    pageSize,
    total,
    showSizeChanger: true,
    showQuickJumper: total > pageSize * 2,
    pageSizeOptions: ["20", "50", "100", "200"],
    showTotal: (t) => `共 ${t.toLocaleString()} 条`,
    onChange,
  };
}
