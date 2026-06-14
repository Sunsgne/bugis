import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntApp, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import { AuthProvider } from "./auth";
import "antd/dist/reset.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#3b82f6",
          colorInfo: "#3b82f6",
          borderRadius: 10,
          colorBgLayout: "#0a0e17",
          colorBgContainer: "#121a2b",
          colorBgElevated: "#16203a",
          colorBorderSecondary: "#1e293b",
          colorBorder: "#243149",
          fontSize: 14,
          wireframe: false,
        },
        components: {
          Layout: {
            headerBg: "#0d1424",
            siderBg: "#0b1220",
            bodyBg: "#0a0e17",
            headerPadding: "0 24px",
          },
          Menu: {
            darkItemBg: "#0b1220",
            darkSubMenuItemBg: "#0b1220",
            darkItemSelectedBg: "#1668dc",
            itemBorderRadius: 8,
            itemMarginInline: 8,
          },
          Card: { colorBgContainer: "#121a2b" },
          Table: { headerBg: "#16203a", colorBgContainer: "#121a2b" },
        },
      }}
    >
      <AntApp>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
