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

export async function login(username: string, password: string) {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);
  const { data } = await axios.post("/api/v1/auth/login", form);
  return data.access_token as string;
}
