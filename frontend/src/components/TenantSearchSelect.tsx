import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Select, Spin } from "antd";
import type { SelectProps } from "antd";
import { api } from "../api/client";
import type { Paginated, Tenant } from "../api/types";

export interface TenantOption {
  value: number;
  label: string;
  circuits_total?: number;
}

interface TenantListItem extends Tenant {
  circuits_total?: number;
}

function formatTenantOption(t: TenantListItem): TenantOption {
  const count = t.circuits_total ?? 0;
  return {
    value: t.id,
    label: `${t.code} · ${t.name} (${count})`,
    circuits_total: count,
  };
}

export function useTenantSearch(initialTenantId?: number | null) {
  const [options, setOptions] = useState<TenantOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const fetchTenants = useCallback(async (q = "") => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page: "1", page_size: "50" });
      if (q.trim()) qs.set("q", q.trim());
      const { data } = await api.get<Paginated<TenantListItem>>(`/tenants?${qs}`);
      setOptions(data.items.map(formatTenantOption));
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, []);

  const ensureSelected = useCallback(
    async (tenantId: number) => {
      if (options.some((o) => o.value === tenantId)) return;
      try {
        const { data } = await api.get<TenantListItem>(`/tenants/${tenantId}`);
        const { data: page } = await api.get<Paginated<TenantListItem>>(
          `/tenants?page=1&page_size=1&q=${encodeURIComponent(data.code)}`,
        );
        const hit = page.items.find((t) => t.id === tenantId);
        const opt = formatTenantOption({ ...data, circuits_total: hit?.circuits_total ?? 0 });
        setOptions((prev) => (prev.some((o) => o.value === tenantId) ? prev : [opt, ...prev]));
      } catch {
        /* ignore */
      }
    },
    [options],
  );

  useEffect(() => {
    fetchTenants("");
  }, [fetchTenants]);

  useEffect(() => {
    if (initialTenantId) ensureSelected(initialTenantId);
  }, [initialTenantId, ensureSelected]);

  const onSearch = useCallback(
    (q: string) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => fetchTenants(q), 280);
    },
    [fetchTenants],
  );

  return { options, loading, total, onSearch, refresh: fetchTenants };
}

type TenantSelectProps = Omit<SelectProps, "options" | "onSearch"> & {
  tenantTotal?: number;
};

export function TenantSearchSelect({
  tenantTotal,
  loading,
  options,
  onSearch,
  ...rest
}: TenantSelectProps & {
  options: TenantOption[];
  loading?: boolean;
  onSearch: (q: string) => void;
}) {
  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      placeholder="筛选客户（搜索名称或编码）"
      style={{ minWidth: 320, maxWidth: 420 }}
      notFoundContent={loading ? <Spin size="small" /> : "未找到客户"}
      onSearch={onSearch}
      options={options}
      popupRender={(menu) => (
        <>
          {menu}
          {tenantTotal != null && tenantTotal > options.length && (
            <div style={{ padding: "8px 12px", color: "#888", fontSize: 12, borderTop: "1px solid #f0f0f0" }}>
              共 {tenantTotal.toLocaleString()} 个客户，请输入关键词缩小范围
            </div>
          )}
        </>
      )}
      {...rest}
    />
  );
}

export function useTenantSelectOptions(initialTenantId?: number | null) {
  const search = useTenantSearch(initialTenantId);
  const selectOptions = useMemo(
    () => search.options.map((o) => ({ value: o.value, label: o.label })),
    [search.options],
  );
  return { ...search, selectOptions };
}
