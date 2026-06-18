import type { TablePaginationConfig, TableProps } from "antd";
import i18n from "../i18n";
import { tablePaginationTotal } from "../i18n/helpers";

export function buildListQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export const PAGE_SIZE_OPTIONS = [20, 50, 100, 200] as const;

export function pageRangeLabel(total: number, page: number, pageSize: number): string {
  const t = i18n.t.bind(i18n);
  if (total === 0) return t("table.noData");
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return t("table.range", {
    start: start.toLocaleString(),
    end: end.toLocaleString(),
    total: total.toLocaleString(),
  });
}

export function dataTableProps(
  scrollX?: number,
  enableScroll = true,
): Pick<TableProps<unknown>, "size" | "tableLayout" | "className" | "scroll"> {
  return {
    size: "middle",
    tableLayout: "fixed",
    className: "data-table",
    ...(scrollX && enableScroll ? { scroll: { x: scrollX } } : {}),
  };
}

export function tablePagination(
  total: number,
  page: number,
  pageSize: number,
  onChange: (page: number, pageSize: number) => void,
): TablePaginationConfig {
  const t = i18n.t.bind(i18n);
  return {
    current: page,
    pageSize,
    total,
    showSizeChanger: true,
    showQuickJumper: total > pageSize * 2,
    pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
    showTotal: (n, range) => tablePaginationTotal(t, n, range as [number, number] | undefined),
    onChange,
  };
}
