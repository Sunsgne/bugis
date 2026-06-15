import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { brand as defaultBrand } from "../constants/uiCopy";

export interface BrandConfig {
  product_name: string;
  header_title: string;
  tagline: string;
  login_title: string;
  login_subtitle: string;
  hero_title: string;
  hero_subtitle: string;
  logo_url?: string | null;
  logo_mark_url?: string | null;
  accent_color?: string;
  login_background?: string | null;
}

const FALLBACK: BrandConfig = {
  product_name: defaultBrand.product,
  header_title: defaultBrand.header,
  tagline: defaultBrand.tagline,
  login_title: defaultBrand.loginTitle,
  login_subtitle: defaultBrand.loginSubtitle,
  hero_title: defaultBrand.heroTitle,
  hero_subtitle: defaultBrand.heroSubtitle,
  accent_color: "#52c41a",
  login_background: "linear-gradient(135deg, #0b1f3a 0%, #1677ff 100%)",
};

function applyDocumentBrand(b: BrandConfig) {
  document.title = b.header_title || b.product_name;
  const href = b.logo_mark_url || b.logo_url;
  if (!href) return;
  let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = href;
}

interface BrandCtx {
  brand: BrandConfig;
  loading: boolean;
  reload: () => Promise<void>;
  save: (payload: Partial<BrandConfig>) => Promise<BrandConfig>;
}

const Ctx = createContext<BrandCtx | null>(null);

export function BrandProvider({ children }: { children: React.ReactNode }) {
  const [brand, setBrand] = useState<BrandConfig>(FALLBACK);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const { data } = await api.get<BrandConfig>("/system/branding");
      setBrand({ ...FALLBACK, ...data });
      applyDocumentBrand({ ...FALLBACK, ...data });
    } catch {
      setBrand(FALLBACK);
    } finally {
      setLoading(false);
    }
  }, []);

  const save = useCallback(async (payload: Partial<BrandConfig>) => {
    const { data } = await api.patch<BrandConfig>("/system/settings/platform", payload);
    const merged = { ...FALLBACK, ...data };
    setBrand(merged);
    applyDocumentBrand(merged);
    return merged;
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const value = useMemo(
    () => ({ brand, loading, reload, save }),
    [brand, loading, reload, save]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useBrand() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useBrand must be used within BrandProvider");
  return ctx;
}
