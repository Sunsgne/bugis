import { useCallback, useEffect, useRef, useState } from "react";
import { Select, Spin } from "antd";
import type { SelectProps } from "antd";
import { api } from "../api/client";
import type { Offering, Paginated } from "../api/types";
import { buildListQuery } from "../utils/table";

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
  remote_ipt: "Remote IPT",
};

export interface OfferingOption {
  value: number;
  label: string;
  offering: Offering;
}

function formatOfferingOption(o: Offering): OfferingOption {
  const svc = SERVICE_LABEL[o.service_type] || o.service_type;
  const tier = o.tier ? `[${o.tier}] ` : "";
  return {
    value: o.id,
    label: `${tier}${o.code} · ${o.name} · ${o.bandwidth_mbps.toLocaleString()}Mbps · ${svc}`,
    offering: o,
  };
}

export function useOfferingSearch(initialOfferingId?: number | null) {
  const [options, setOptions] = useState<OfferingOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const fetchOfferings = useCallback(async (q = "") => {
    setLoading(true);
    try {
      const { data } = await api.get<Paginated<Offering>>(
        `/offerings${buildListQuery({ active: true, page: 1, page_size: 50, q: q || undefined })}`,
      );
      setOptions(data.items.map(formatOfferingOption));
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, []);

  const ensureSelected = useCallback(async (offeringId: number) => {
    if (options.some((o) => o.value === offeringId)) return;
    try {
      const { data } = await api.get<Offering>(`/offerings/${offeringId}`);
      const opt = formatOfferingOption(data);
      setOptions((prev) => (prev.some((o) => o.value === offeringId) ? prev : [opt, ...prev]));
    } catch {
      /* ignore */
    }
  }, [options]);

  useEffect(() => {
    fetchOfferings("");
  }, [fetchOfferings]);

  useEffect(() => {
    if (initialOfferingId) ensureSelected(initialOfferingId);
  }, [initialOfferingId, ensureSelected]);

  const onSearch = useCallback(
    (q: string) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => fetchOfferings(q), 280);
    },
    [fetchOfferings],
  );

  return { options, loading, total, onSearch };
}

type Props = Omit<SelectProps, "options" | "onSearch"> & {
  options: OfferingOption[];
  loading?: boolean;
  onSearch: (q: string) => void;
  offeringTotal?: number;
};

export default function OfferingSearchSelect({
  options,
  loading,
  onSearch,
  offeringTotal,
  ...rest
}: Props) {
  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      placeholder="搜索套餐编码或名称（仅上架）"
      notFoundContent={loading ? <Spin size="small" /> : "未找到套餐"}
      onSearch={onSearch}
      options={options}
      popupRender={(menu) => (
        <>
          {menu}
          {offeringTotal != null && offeringTotal > options.length && (
            <div
              style={{
                padding: "8px 12px",
                color: "#888",
                fontSize: 12,
                borderTop: "1px solid #f0f0f0",
              }}
            >
              共 {offeringTotal.toLocaleString()} 个上架套餐，请输入关键词缩小范围
            </div>
          )}
        </>
      )}
      {...rest}
    />
  );
}
