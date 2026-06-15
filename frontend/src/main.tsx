import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import { AuthProvider } from "./auth";
import { BrandProvider } from "./context/BrandContext";
import "antd/dist/reset.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      popupMatchSelectWidth={false}
      theme={{
        token: { colorPrimary: "#1677ff", borderRadius: 8, colorBgLayout: "#f0f2f5" },
        components: {
          Layout: { siderBg: "#001529", headerBg: "#ffffff" },
          Menu: { itemBorderRadius: 8, itemMarginInline: 8 },
          Select: { optionPadding: "8px 12px" },
        },
      }}
    >
      <AntApp>
        <BrandProvider>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </BrandProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
