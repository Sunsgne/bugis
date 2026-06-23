import type { ColumnType } from "antd/es/table";
import type { Breakpoint } from "antd/es/_util/responsiveObserver";
import type { TablePaginationConfig, TableProps } from "antd";
import type { CSSProperties } from "react";
import i18n from "../i18n";
import { tablePaginationTotal } from "../i18n/helpers";

export const TABLE_SCROLL = {
  sm: 720,
  md: 960,
  lg: 1200,
  xl: 1400,
  max: "max-content",
} as const;

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

/** Hide column below breakpoint (visible on md+ when bp is md). */
export function hideBelow(col: ColumnType<any>, bp: Breakpoint = "md"): ColumnType<any> {
  if (col.responsive) return col;
  return { ...col, responsive: [bp] };
}

/** Mark secondary columns hidden on small screens. Match by dataIndex, key, or column index. */
export function withMobileHide(
  columns: ColumnType<any>[],
  hideKeys: (string | number)[],
  bp: Breakpoint = "md",
): ColumnType<any>[] {
  const hide = new Set(hideKeys.map(String));
  return columns.map((col, idx) => {
    const id = String(col.key ?? col.dataIndex ?? idx);
    return hide.has(id) ? hideBelow(col, bp) : col;
  });
}

export function twinTableProps(): Pick<TableProps<unknown>, "size" | "tableLayout" | "className"> {
  return {
    size: "small",
    tableLayout: "auto",
    className: "data-table control-plane-twin-table",
  };
}

export function dataTableProps(
  scrollX: number | string = TABLE_SCROLL.md,
  enableScroll = true,
): Pick<TableProps<unknown>, "size" | "tableLayout" | "className" | "scroll"> {
  return {
    size: "middle",
    tableLayout: "fixed",
    className: "data-table",
    ...(enableScroll ? { scroll: { x: scrollX } } : {}),
  };
}

const NOWRAP_HEADER: CSSProperties = { whiteSpace: "nowrap" };

/** Table column with nowrap header — prevents awkward English line breaks. */
export function colNowrap<T>(
  col: ColumnType<T>,
  minWidth?: number,
): ColumnType<T> {
  return {
    ...col,
    ...(minWidth != null ? { width: col.width ?? minWidth } : {}),
    onHeaderCell: () => ({ style: NOWRAP_HEADER }),
  };
}

/** Apply nowrap headers to all columns. */
export function colsNowrap<T>(columns: ColumnType<T>[], minWidths?: Record<string, number>): ColumnType<T>[] {
  return columns.map((col, idx) => {
    const key = String(col.key ?? col.dataIndex ?? idx);
    return colNowrap(col, minWidths?.[key]);
  });
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
