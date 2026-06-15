import type { TablePaginationConfig } from "antd";

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
