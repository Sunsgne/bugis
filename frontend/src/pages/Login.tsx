import {
  ArrowRight,
  Cloud,
  Loader2,
  Lock,
  Mail,
  Network,
  ShieldCheck,
  User,
} from "lucide-react";
import { useState, useEffect, useRef, type CSSProperties, type FormEvent } from "react";
import { toast } from "sonner";
import {
  fetchLoginSecurity,
  loginJson,
  sendMfaEmail,
  verifyMfa,
  type LoginSecurityConfig,
} from "../api/client";
import { useAuth } from "../auth";
import { BrandLogo } from "../components/BrandLogo";
import { action, toast as toastCopy } from "../constants/uiCopy";
import { useBrand } from "../context/BrandContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    turnstile?: {
      render: (
        el: HTMLElement,
        opts: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback"?: () => void;
          theme?: string;
        },
      ) => string;
      reset: (widgetId?: string) => void;
    };
  }
}

const FEATURES = [
  { icon: Network, label: "EVPN VXLAN 编排" },
  { icon: Cloud, label: "跨 DC 互联" },
  { icon: ShieldCheck, label: "多厂商统一纳管" },
];

function loadTurnstileScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[src*="turnstile"]');
    if (existing) {
      existing.addEventListener("load", () => resolve());
      return;
    }
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Turnstile 脚本加载失败"));
    document.head.appendChild(script);
  });
}

export default function Login() {
  const { loginWithToken } = useAuth();
  const { brand } = useBrand();
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [security, setSecurity] = useState<LoginSecurityConfig | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [captchaForced, setCaptchaForced] = useState(false);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaMethods, setMfaMethods] = useState<string[]>([]);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaMethod, setMfaMethod] = useState("totp");
  const turnstileRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  const showTurnstile =
    security?.turnstile_enabled || captchaForced || security?.captcha_required_default;

  useEffect(() => {
    document.body.classList.add("login-route");
    fetchLoginSecurity().then(setSecurity).catch(() => {});
    return () => document.body.classList.remove("login-route");
  }, []);

  useEffect(() => {
    if (!showTurnstile || !security?.turnstile_site_key || !turnstileRef.current) return;
    let cancelled = false;
    loadTurnstileScript()
      .then(() => {
        if (cancelled || !turnstileRef.current || !window.turnstile) return;
        if (widgetIdRef.current) window.turnstile.reset(widgetIdRef.current);
        widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
          sitekey: security.turnstile_site_key,
          theme: "dark",
          callback: (token) => setTurnstileToken(token),
          "expired-callback": () => setTurnstileToken(null),
        });
      })
      .catch(() => toast.error("人机验证组件加载失败"));
    return () => {
      cancelled = true;
    };
  }, [showTurnstile, security?.turnstile_site_key, captchaForced]);

  async function completeLogin(token: string) {
    const me = await loginWithToken(token);
    toast.success(toastCopy.loginOk);
    window.location.href = me && (me.scope === "tenant" || me.tenant_id != null) ? "/portal" : "/";
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error("请输入用户名和密码");
      return;
    }
    if (showTurnstile && security?.turnstile_site_key && !turnstileToken) {
      toast.error("请先完成人机验证");
      return;
    }

    setLoading(true);
    try {
      const result = await loginJson(username.trim(), password, turnstileToken);
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token);
        setMfaMethods(result.mfa_methods || ["totp"]);
        setMfaMethod(result.mfa_methods?.[0] || "totp");
        toast.message("请输入双因素验证码");
        return;
      }
      if (!result.access_token) throw new Error("login failed");
      await completeLogin(result.access_token);
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 428) {
        setCaptchaForced(true);
        toast.error("需要完成人机验证后重试");
      } else {
        toast.error(err?.response?.data?.detail || toastCopy.loginFail);
      }
    } finally {
      setLoading(false);
    }
  }

  async function onMfaSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!mfaToken || !mfaCode.trim()) {
      toast.error("请输入验证码");
      return;
    }
    setLoading(true);
    try {
      const token = await verifyMfa(mfaToken, mfaCode.trim(), mfaMethod);
      await completeLogin(token);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "验证码错误");
    } finally {
      setLoading(false);
    }
  }

  async function onSendEmailCode() {
    if (!mfaToken) return;
    setLoading(true);
    try {
      await sendMfaEmail(mfaToken);
      toast.success("验证码已发送至邮箱");
      setMfaMethod("email");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "邮件发送失败");
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
        <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-orange-500/15 blur-3xl" />
        <div className="absolute -right-24 bottom-1/4 h-80 w-80 rounded-full bg-amber-500/10 blur-3xl" />
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
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-orange-500/30 bg-orange-500/10 text-orange-400">
                  <Icon className="h-4 w-4" />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </section>

        <section className="flex w-full flex-1 justify-center lg:justify-end">
          <Card className="w-full max-w-md border-slate-800/80 bg-slate-900/80 shadow-2xl shadow-black/40 backdrop-blur-sm">
            <CardHeader className="space-y-4 pb-2">
              <CardTitle className="text-xl text-slate-100">
                {mfaToken ? "双因素验证" : brand.login_title || brand.product_name}
              </CardTitle>
              <CardDescription className="text-slate-400">
                {mfaToken
                  ? "请输入验证器或邮件中的 6 位验证码"
                  : brand.login_subtitle || brand.tagline || `登录以进入 ${brand.product_name}`}
              </CardDescription>
            </CardHeader>

            <CardContent>
              {mfaToken ? (
                <form onSubmit={onMfaSubmit} className="space-y-5">
                  <div className="space-y-2">
                    <Label htmlFor="mfa-code" className="text-slate-300">
                      验证码
                    </Label>
                    <Input
                      id="mfa-code"
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                      placeholder="6 位数字"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      required
                      className="h-11 border-slate-700 bg-slate-950/50 text-slate-100"
                    />
                  </div>
                  {mfaMethods.includes("email") && (
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      disabled={loading}
                      onClick={onSendEmailCode}
                    >
                      <Mail className="mr-2 h-4 w-4" />
                      发送邮件验证码
                    </Button>
                  )}
                  <Button type="submit" disabled={loading} className="h-11 w-full bg-orange-600 hover:bg-orange-500">
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "验证并登录"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full text-slate-400"
                    onClick={() => {
                      setMfaToken(null);
                      setMfaCode("");
                    }}
                  >
                    返回上一步
                  </Button>
                </form>
              ) : (
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
                        className="h-11 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
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
                        className="h-11 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  {showTurnstile && security?.turnstile_site_key ? (
                    <div ref={turnstileRef} className="flex justify-center" />
                  ) : showTurnstile ? (
                    <p className="text-center text-xs text-amber-400">
                      已要求人机验证，请在系统设置中配置 Turnstile Site Key
                    </p>
                  ) : null}
                  <Button
                    type="submit"
                    disabled={loading}
                    className={cn("h-11 w-full bg-orange-600 text-white hover:bg-orange-500")}
                    style={brand.accent_color ? { backgroundColor: brand.accent_color } : undefined}
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
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
