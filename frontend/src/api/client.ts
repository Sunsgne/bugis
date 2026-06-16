import axios from "axios";

export const api = axios.create({ baseURL: "/api/v1" });

const TOKEN_KEY = "bugis_token";

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      setToken(null);
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export interface LoginSecurityConfig {
  turnstile_enabled: boolean;
  turnstile_site_key: string;
  captcha_required_default: boolean;
}

export interface LoginResult {
  access_token?: string | null;
  token_type?: string;
  mfa_required?: boolean;
  mfa_token?: string | null;
  mfa_methods?: string[];
  captcha_required?: boolean;
}

export async function fetchLoginSecurity(): Promise<LoginSecurityConfig> {
  const { data } = await axios.get<LoginSecurityConfig>("/api/v1/auth/login-security");
  return data;
}

export async function loginJson(
  username: string,
  password: string,
  turnstileToken?: string | null,
): Promise<LoginResult> {
  const { data } = await axios.post<LoginResult>("/api/v1/auth/login/json", {
    username,
    password,
    turnstile_token: turnstileToken || undefined,
  });
  return data;
}

/** @deprecated Use loginJson — kept for compatibility */
export async function login(username: string, password: string) {
  const result = await loginJson(username, password);
  if (result.mfa_required) {
    throw Object.assign(new Error("MFA required"), { response: { data: { mfa_required: true, ...result } } });
  }
  if (!result.access_token) throw new Error("login failed");
  return result.access_token;
}

export async function verifyMfa(
  mfaToken: string,
  code: string,
  method: string = "totp",
): Promise<string> {
  const { data } = await axios.post<LoginResult>("/api/v1/auth/mfa/verify", {
    mfa_token: mfaToken,
    code,
    method,
  });
  if (!data.access_token) throw new Error("MFA verify failed");
  return data.access_token;
}

export async function sendMfaEmail(mfaToken: string) {
  await axios.post("/api/v1/auth/mfa/send-email", { mfa_token: mfaToken });
}

export async function fetchStreamTicket(): Promise<string> {
  const { data } = await api.post<{ ticket: string }>("/auth/stream/ticket");
  return data.ticket;
}
