import type { BrandConfig } from "../context/BrandContext";

interface BrandLogoProps {
  brand: BrandConfig;
  variant?: "sidebar" | "login";
  height?: number;
}

export function BrandLogo({ brand, variant = "sidebar", height = 28 }: BrandLogoProps) {
  const src = variant === "login" ? brand.logo_url || brand.logo_mark_url : brand.logo_mark_url || brand.logo_url;
  if (src) {
    return (
      <img
        src={src}
        alt={brand.product_name}
        style={{
          height,
          maxWidth: variant === "sidebar" ? 140 : 200,
          objectFit: "contain",
          display: "block",
        }}
      />
    );
  }
  const color = brand.accent_color || "#52c41a";
  return (
    <span
      className="brand-dot"
      style={{
        width: variant === "login" ? 12 : 8,
        height: variant === "login" ? 12 : 8,
        borderRadius: "50%",
        background: `linear-gradient(135deg, ${color}, #13c2c2)`,
        boxShadow: `0 0 12px ${color}99`,
        flexShrink: 0,
        display: "inline-block",
      }}
    />
  );
}
