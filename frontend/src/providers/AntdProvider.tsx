import { App, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";

/** Wraps hybrid antd pages (Circuits, Dashboard, Settings…) with required context. */
export default function AntdProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "hsl(221, 83%, 53%)",
          borderRadius: 8,
          colorBorder: "rgba(15, 23, 42, 0.06)",
          colorSplit: "rgba(15, 23, 42, 0.05)",
          lineWidth: 1,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
        },
        components: {
          Card: {
            headerHeight: 48,
            paddingLG: 20,
          },
          Table: {
            headerBg: "hsl(210, 40%, 98%)",
            borderColor: "transparent",
            headerSplitColor: "transparent",
            cellPaddingBlock: 12,
            cellPaddingInline: 16,
          },
          Modal: {
            titleFontSize: 16,
          },
          Form: {
            itemMarginBottom: 20,
            labelHeight: 22,
            verticalLabelPadding: 4,
            labelFontSize: 13,
          },
          Descriptions: {
            labelBg: "hsl(210, 40%, 98%)",
            padding: 12,
          },
          Menu: {
            itemBg: "transparent",
          },
        },
      }}
      getPopupContainer={() => document.body}
    >
      <App>{children}</App>
    </ConfigProvider>
  );
}
