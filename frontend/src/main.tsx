import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { BrandProvider } from "./context/BrandContext";
import { LocaleProvider, bootstrapLocaleFromStorage } from "./context/LocaleContext";
import AntdProvider from "./providers/AntdProvider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./i18n";
import "./index.css";

bootstrapLocaleFromStorage();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TooltipProvider delayDuration={200}>
      <BrandProvider>
        <AuthProvider>
          <LocaleProvider>
            <AntdProvider>
              <BrowserRouter>
                <App />
                <Toaster richColors position="top-right" />
              </BrowserRouter>
            </AntdProvider>
          </LocaleProvider>
        </AuthProvider>
      </BrandProvider>
    </TooltipProvider>
  </React.StrictMode>,
);
