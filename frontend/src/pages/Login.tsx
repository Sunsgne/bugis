import {
  ArrowRight,
  Cloud,
  Loader2,
  Lock,
  Network,
  ShieldCheck,
  User,
} from "lucide-react";
import { useState, useEffect, type CSSProperties, type FormEvent } from "react";
import { toast } from "sonner";
import { login } from "../api/client";
import { useAuth } from "../auth";
import { BrandLogo } from "../components/BrandLogo";
import { action, toast as toastCopy } from "../constants/uiCopy";
import { useBrand } from "../context/BrandContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const FEATURES = [
  { icon: Network, label: "EVPN VXLAN 编排" },
  { icon: Cloud, label: "跨 DC 互联" },
  { icon: ShieldCheck, label: "多厂商统一纳管" },
];

export default function Login() {
  const { loginWithToken } = useAuth();
  const { brand } = useBrand();
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");

  useEffect(() => {
    document.body.classList.add("login-route");
    return () => document.body.classList.remove("login-route");
  }, []);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error("请输入用户名和密码");
      return;
    }

    setLoading(true);
    try {
      const token = await login(username.trim(), password);
      await loginWithToken(token);
      toast.success(toastCopy.loginOk);
    } catch {
      toast.error(toastCopy.loginFail);
    } finally {
      setLoading(false);
    }
  }

  const accentStyle = brand.accent_color
    ? ({ ["--brand-accent" as string]: brand.accent_color } as CSSProperties)
    : undefined;

  return (
    <div
      className="login-page relative overflow-hidden"
      style={
        {
          ...(brand.login_background ? { ["--login-bg" as string]: brand.login_background } : {}),
          ...(brand.accent_color ? { ["--brand-accent" as string]: brand.accent_color } : {}),
        } as CSSProperties
      }
    >
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute -right-24 bottom-1/4 h-80 w-80 rounded-full bg-indigo-500/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.4) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-stretch gap-10 lg:flex-row lg:items-center lg:gap-16">
        <section className="flex flex-1 flex-col gap-8 lg:max-w-xl">
          <div className="flex items-center gap-4">
            <BrandLogo brand={brand} variant="login" height={36} />
            <div>
              <div className="text-lg font-semibold tracking-tight text-slate-100">
                {brand.product_name}
              </div>
              {brand.tagline ? (
                <div className="text-sm text-slate-400">{brand.tagline}</div>
              ) : null}
            </div>
          </div>

          <div className="space-y-4">
            <h1 className="text-3xl font-bold leading-tight tracking-tight text-white sm:text-4xl">
              {brand.hero_title || brand.login_title}
            </h1>
            <p className="max-w-md text-base leading-relaxed text-slate-400">
              {brand.hero_subtitle || brand.login_subtitle}
            </p>
          </div>

          <ul className="flex flex-col gap-3">
            {FEATURES.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-3 text-sm text-slate-300">
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700/60 bg-slate-800/50 text-sky-400"
                  style={accentStyle}
                >
                  <Icon className="h-4 w-4" />
                </span>
                {label}
              </li>
            ))}
          </ul>

          <div className="hidden opacity-70 lg:block" aria-hidden>
            <svg viewBox="0 0 420 280" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-48 w-full max-w-sm">
              <defs>
                <linearGradient id="login-line" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.2" />
                  <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#818cf8" stopOpacity="0.2" />
                </linearGradient>
              </defs>
              <circle cx="210" cy="140" r="36" stroke="url(#login-line)" strokeWidth="1.5" opacity="0.6" />
              <circle cx="210" cy="140" r="8" fill="#38bdf8" opacity="0.9" />
              {[
                [80, 60],
                [340, 60],
                [60, 200],
                [360, 200],
                [210, 30],
                [210, 250],
              ].map(([x, y], i) => (
                <g key={i}>
                  <line x1="210" y1="140" x2={x} y2={y} stroke="url(#login-line)" strokeWidth="1" opacity="0.45" />
                  <circle cx={x} cy={y} r="5" fill="#818cf8" opacity="0.85" />
                </g>
              ))}
            </svg>
          </div>
        </section>

        <section className="flex w-full flex-1 justify-center lg:justify-end">
          <Card className="w-full max-w-md border-slate-800/80 bg-slate-900/80 shadow-2xl shadow-black/40 backdrop-blur-sm">
            <CardHeader className="space-y-4 pb-2">
              <div className="flex justify-center lg:justify-start">
                <BrandLogo brand={brand} variant="login" height={32} />
              </div>
              <div className="space-y-1.5 text-center lg:text-left">
                <CardTitle className="text-xl text-slate-100">
                  {brand.login_title || brand.product_name}
                </CardTitle>
                <CardDescription className="text-slate-400">
                  {brand.login_subtitle || brand.tagline || `登录以进入 ${brand.product_name}`}
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent>
              <form onSubmit={onSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="username" className="text-slate-300">
                    用户名
                  </Label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <Input
                      id="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="请输入用户名"
                      autoComplete="username"
                      required
                      className="h-11 border-slate-700 bg-slate-950/50 pl-10 text-slate-100 placeholder:text-slate-500 focus-visible:ring-sky-500/40"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-slate-300">
                    密码
                  </Label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="请输入密码"
                      autoComplete="current-password"
                      required
                      className="h-11 border-slate-700 bg-slate-950/50 pl-10 text-slate-100 placeholder:text-slate-500 focus-visible:ring-sky-500/40"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  className={cn(
                    "h-11 w-full text-sm font-medium",
                    "bg-sky-600 text-white hover:bg-sky-500",
                  )}
                  style={
                    brand.accent_color
                      ? { backgroundColor: brand.accent_color }
                      : undefined
                  }
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      登录中…
                    </>
                  ) : (
                    <>
                      {action.login}
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
