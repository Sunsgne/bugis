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
          },
          Table: {
            headerBg: "hsl(210, 40%, 98%)",
            borderColor: "transparent",
            headerSplitColor: "transparent",
          },
          Modal: {
            headerBg: "transparent",
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
