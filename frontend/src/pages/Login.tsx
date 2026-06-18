import {
  ArrowLeft,
  ArrowRight,
  Cloud,
  KeyRound,
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
  forgotPassword,
  loginJson,
  resetPassword,
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

type Mode = "login" | "mfa" | "forgot" | "reset";

const FEATURES = [
  { icon: Network, label: "EVPN VXLAN 智能编排", desc: "意图驱动，多厂商一键开通" },
  { icon: Cloud, label: "跨 DC / 跨域互联", desc: "DCI 专线全生命周期管理" },
  { icon: ShieldCheck, label: "多厂商统一纳管", desc: "华三 / 华为 / 思科 / Juniper" },
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
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [security, setSecurity] = useState<LoginSecurityConfig | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [captchaForced, setCaptchaForced] = useState(false);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaMethods, setMfaMethods] = useState<string[]>([]);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaMethod, setMfaMethod] = useState("totp");
  // Password recovery
  const [resetIdentifier, setResetIdentifier] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetPwd, setResetPwd] = useState("");
  const [resetPwd2, setResetPwd2] = useState("");
  const turnstileRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  const showTurnstile =
    security?.turnstile_enabled || captchaForced || security?.captcha_required_default;
  const captchaVisible = showTurnstile && (mode === "login" || mode === "forgot");

  useEffect(() => {
    document.body.classList.add("login-route");
    fetchLoginSecurity().then(setSecurity).catch(() => {});
    return () => document.body.classList.remove("login-route");
  }, []);

  useEffect(() => {
    if (!captchaVisible || !security?.turnstile_site_key || !turnstileRef.current) return;
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
  }, [captchaVisible, security?.turnstile_site_key, captchaForced, mode]);

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
        setMode("mfa");
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

  function backToLogin() {
    setMode("login");
    setMfaToken(null);
    setMfaCode("");
    setResetCode("");
    setResetPwd("");
    setResetPwd2("");
  }

  function openForgot() {
    setResetIdentifier(username.trim());
    setResetCode("");
    setResetPwd("");
    setResetPwd2("");
    setMode("forgot");
  }

  async function onForgotSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!resetIdentifier.trim()) {
      toast.error("请输入用户名或邮箱");
      return;
    }
    if (showTurnstile && security?.turnstile_site_key && !turnstileToken) {
      toast.error("请先完成人机验证");
      return;
    }
    setLoading(true);
    try {
      const detail = await forgotPassword(resetIdentifier.trim(), turnstileToken);
      toast.success(detail || "若账号存在，验证码已发送至邮箱");
      setMode("reset");
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 428) {
        setCaptchaForced(true);
        toast.error("需要完成人机验证后重试");
      } else {
        toast.error(err?.response?.data?.detail || "发送失败，请稍后再试");
      }
    } finally {
      setLoading(false);
    }
  }

  async function onResetSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!resetCode.trim()) return toast.error("请输入验证码");
    if (resetPwd.length < 8) return toast.error("新密码至少 8 位");
    if (resetPwd !== resetPwd2) return toast.error("两次输入的密码不一致");
    setLoading(true);
    try {
      await resetPassword(resetIdentifier.trim(), resetCode.trim(), resetPwd);
      toast.success("密码已重置，请使用新密码登录");
      setUsername(resetIdentifier.trim());
      setPassword("");
      backToLogin();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "重置失败，请检查验证码");
    } finally {
      setLoading(false);
    }
  }

  const accentBtn: CSSProperties | undefined = brand.accent_color
    ? { backgroundColor: brand.accent_color }
    : undefined;

  const cardTitle =
    mode === "mfa"
      ? "双因素验证"
      : mode === "forgot"
        ? "找回密码"
        : mode === "reset"
          ? "重置密码"
          : brand.login_title || brand.product_name;
  const cardDesc =
    mode === "mfa"
      ? "请输入验证器或邮件中的 6 位验证码以完成登录"
      : mode === "forgot"
        ? "输入账号用户名或绑定邮箱，我们将发送验证码到邮箱"
        : mode === "reset"
          ? "输入邮箱收到的验证码并设置新的登录密码"
          : brand.login_subtitle || brand.tagline || `登录以进入 ${brand.product_name}`;

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
        <div className="absolute -left-32 top-1/4 h-[28rem] w-[28rem] rounded-full bg-orange-500/15 blur-3xl" />
        <div className="absolute -right-24 bottom-1/4 h-96 w-96 rounded-full bg-amber-500/10 blur-3xl" />
        <div className="absolute left-1/2 top-1/2 h-[40rem] w-[40rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/[0.02] blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-stretch gap-12 px-2 lg:flex-row lg:items-center lg:gap-20">
        <section className="flex flex-1 flex-col gap-10 lg:max-w-xl">
          <div className="flex items-center gap-4">
            <BrandLogo brand={brand} variant="login" height={40} />
            <div>
              <div className="text-lg font-semibold tracking-tight text-slate-100">
                {brand.product_name}
              </div>
              {brand.tagline ? (
                <div className="text-sm text-slate-400">{brand.tagline}</div>
              ) : null}
            </div>
          </div>
          <div className="space-y-5">
            <h1 className="text-4xl font-bold leading-[1.15] tracking-tight text-white sm:text-5xl">
              {brand.hero_title || brand.login_title}
            </h1>
            <p className="max-w-md text-base leading-relaxed text-slate-400">
              {brand.hero_subtitle || brand.login_subtitle}
            </p>
          </div>
          <ul className="flex flex-col gap-4">
            {FEATURES.map(({ icon: Icon, label, desc }) => (
              <li key={label} className="flex items-start gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-orange-500/25 bg-orange-500/10 text-orange-400">
                  <Icon className="h-5 w-5" />
                </span>
                <div className="pt-0.5">
                  <div className="text-sm font-medium text-slate-200">{label}</div>
                  <div className="text-xs text-slate-500">{desc}</div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="flex w-full flex-1 justify-center lg:max-w-md lg:justify-end">
          <Card className="login-card w-full max-w-md border-slate-800/70 bg-slate-900/75 shadow-2xl shadow-black/50 backdrop-blur-xl">
            <CardHeader className="space-y-5 px-8 pb-8 pt-10 sm:px-10">
              <span
                className="flex h-12 w-12 items-center justify-center rounded-2xl border border-orange-500/30 bg-orange-500/10 text-orange-400"
                style={
                  brand.accent_color
                    ? { color: brand.accent_color, borderColor: `${brand.accent_color}55` }
                    : undefined
                }
              >
                {mode === "login" ? (
                  <Lock className="h-5 w-5" />
                ) : mode === "mfa" ? (
                  <ShieldCheck className="h-5 w-5" />
                ) : (
                  <KeyRound className="h-5 w-5" />
                )}
              </span>
              <div className="space-y-2">
                <CardTitle className="text-2xl font-semibold tracking-tight text-slate-100">
                  {cardTitle}
                </CardTitle>
                <CardDescription className="leading-relaxed text-slate-400">
                  {cardDesc}
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent className="px-8 pb-10 sm:px-10">
              {mode === "mfa" ? (
                <form onSubmit={onMfaSubmit} className="space-y-7">
                  <div className="space-y-3">
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
                      maxLength={6}
                      required
                      className="h-12 border-slate-700 bg-slate-950/50 text-center text-lg tracking-[0.4em] text-slate-100"
                    />
                  </div>
                  {mfaMethods.includes("email") && (
                    <Button
                      type="button"
                      variant="outline"
                      className="h-11 w-full border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800"
                      disabled={loading}
                      onClick={onSendEmailCode}
                    >
                      <Mail className="mr-2 h-4 w-4" />
                      发送邮件验证码
                    </Button>
                  )}
                  <Button
                    type="submit"
                    disabled={loading}
                    className="h-12 w-full bg-orange-600 text-white hover:bg-orange-500"
                    style={accentBtn}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "验证并登录"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full text-slate-400 hover:text-slate-200"
                    onClick={backToLogin}
                  >
                    <ArrowLeft className="mr-1 h-4 w-4" />
                    返回登录
                  </Button>
                </form>
              ) : mode === "forgot" ? (
                <form onSubmit={onForgotSubmit} className="space-y-7">
                  <div className="space-y-3">
                    <Label htmlFor="forgot-id" className="text-slate-300">
                      用户名或邮箱
                    </Label>
                    <div className="relative">
                      <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                      <Input
                        id="forgot-id"
                        value={resetIdentifier}
                        onChange={(e) => setResetIdentifier(e.target.value)}
                        placeholder="请输入用户名或绑定邮箱"
                        autoComplete="username"
                        required
                        className="h-12 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  {captchaVisible && security?.turnstile_site_key ? (
                    <div ref={turnstileRef} className="flex justify-center" />
                  ) : null}
                  <Button
                    type="submit"
                    disabled={loading}
                    className="h-12 w-full bg-orange-600 text-white hover:bg-orange-500"
                    style={accentBtn}
                  >
                    {loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <Mail className="h-4 w-4" />
                        发送验证码
                      </>
                    )}
                  </Button>
                  <div className="flex items-center justify-between text-sm">
                    <button
                      type="button"
                      className="text-slate-400 transition-colors hover:text-slate-200"
                      onClick={backToLogin}
                    >
                      <ArrowLeft className="mr-1 inline h-4 w-4" />
                      返回登录
                    </button>
                    <button
                      type="button"
                      className="text-slate-400 transition-colors hover:text-slate-200"
                      onClick={() => setMode("reset")}
                    >
                      已有验证码？
                    </button>
                  </div>
                </form>
              ) : mode === "reset" ? (
                <form onSubmit={onResetSubmit} className="space-y-6">
                  <div className="space-y-3">
                    <Label htmlFor="reset-code" className="text-slate-300">
                      邮件验证码
                    </Label>
                    <Input
                      id="reset-code"
                      value={resetCode}
                      onChange={(e) => setResetCode(e.target.value)}
                      placeholder="6 位数字"
                      inputMode="numeric"
                      maxLength={6}
                      required
                      className="h-12 border-slate-700 bg-slate-950/50 text-center text-lg tracking-[0.4em] text-slate-100"
                    />
                  </div>
                  <div className="space-y-3">
                    <Label htmlFor="reset-pwd" className="text-slate-300">
                      新密码
                    </Label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                      <Input
                        id="reset-pwd"
                        type="password"
                        value={resetPwd}
                        onChange={(e) => setResetPwd(e.target.value)}
                        placeholder="至少 8 位"
                        autoComplete="new-password"
                        required
                        className="h-12 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <Label htmlFor="reset-pwd2" className="text-slate-300">
                      确认新密码
                    </Label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                      <Input
                        id="reset-pwd2"
                        type="password"
                        value={resetPwd2}
                        onChange={(e) => setResetPwd2(e.target.value)}
                        placeholder="请再次输入新密码"
                        autoComplete="new-password"
                        required
                        className="h-12 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  <Button
                    type="submit"
                    disabled={loading}
                    className="h-12 w-full bg-orange-600 text-white hover:bg-orange-500"
                    style={accentBtn}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "重置密码并返回登录"}
                  </Button>
                  <div className="flex items-center justify-between text-sm">
                    <button
                      type="button"
                      className="text-slate-400 transition-colors hover:text-slate-200"
                      onClick={() => setMode("forgot")}
                    >
                      <ArrowLeft className="mr-1 inline h-4 w-4" />
                      重新获取验证码
                    </button>
                    <button
                      type="button"
                      className="text-slate-400 transition-colors hover:text-slate-200"
                      onClick={backToLogin}
                    >
                      返回登录
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={onSubmit} className="space-y-7">
                  <div className="space-y-3">
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
                        className="h-12 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password" className="text-slate-300">
                        密码
                      </Label>
                      {security?.password_reset_enabled ? (
                        <button
                          type="button"
                          className="text-xs text-slate-400 transition-colors hover:text-orange-400"
                          onClick={openForgot}
                        >
                          忘记密码？
                        </button>
                      ) : null}
                    </div>
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
                        className="h-12 border-slate-700 bg-slate-950/50 pl-10 text-slate-100"
                      />
                    </div>
                  </div>
                  {captchaVisible && security?.turnstile_site_key ? (
                    <div ref={turnstileRef} className="flex justify-center" />
                  ) : captchaVisible ? (
                    <p className="text-center text-xs text-amber-400">
                      已要求人机验证，请在系统设置中配置 Turnstile Site Key
                    </p>
                  ) : null}
                  <Button
                    type="submit"
                    disabled={loading}
                    className={cn("h-12 w-full bg-orange-600 text-white hover:bg-orange-500")}
                    style={accentBtn}
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
