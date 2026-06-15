import { Button, Form, Input, Typography, App as AntApp } from "antd";
import {
  LockOutlined,
  UserOutlined,
  ArrowRightOutlined,
  CloudServerOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import { login } from "../api/client";
import { useAuth } from "../auth";

const FEATURES = [
  { icon: <NodeIndexOutlined />, label: "EVPN VXLAN 编排" },
  { icon: <CloudServerOutlined />, label: "跨 DC 互联" },
  { icon: <SafetyCertificateOutlined />, label: "多厂商统一纳管" },
];

export default function Login() {
  const { loginWithToken } = useAuth();
  const { message } = AntApp.useApp();
  const [loading, setLoading] = useState(false);

  async function onFinish(v: { username: string; password: string }) {
    setLoading(true);
    try {
      const token = await login(v.username, v.password);
      await loginWithToken(token);
      message.success("登录成功");
    } catch {
      message.error("用户名或密码错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__bg" aria-hidden>
        <div className="login-page__orb login-page__orb--1" />
        <div className="login-page__orb login-page__orb--2" />
        <div className="login-page__grid" />
      </div>

      <div className="login-page__shell">
        <section className="login-page__hero">
          <div className="login-page__brand">
            <span className="login-page__logo-mark" />
            <span className="login-page__logo-text">Bugis</span>
          </div>

          <Typography.Title level={1} className="login-page__headline">
            DCI / EVPN
            <br />
            专线运营平台
          </Typography.Title>

          <Typography.Paragraph className="login-page__tagline">
            面向数据中心互联与 EVPN 专线的一站式编排、开通与运维控制台。
          </Typography.Paragraph>

          <ul className="login-page__features">
            {FEATURES.map((f) => (
              <li key={f.label}>
                <span className="login-page__feature-icon">{f.icon}</span>
                {f.label}
              </li>
            ))}
          </ul>

          <div className="login-page__topology" aria-hidden>
            <svg viewBox="0 0 420 280" fill="none" xmlns="http://www.w3.org/2000/svg">
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

        <section className="login-page__panel">
          <div className="login-page__card">
            <header className="login-page__card-header">
              <Typography.Title level={3} className="login-page__card-title">
                欢迎回来
              </Typography.Title>
              <Typography.Text className="login-page__card-sub">
                登录以进入运营控制台
              </Typography.Text>
            </header>

            <Form
              layout="vertical"
              onFinish={onFinish}
              initialValues={{ username: "admin", password: "admin123" }}
              requiredMark={false}
              className="login-page__form"
            >
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: "请输入用户名" }]}
              >
                <Input
                  prefix={<UserOutlined className="login-page__input-icon" />}
                  placeholder="请输入用户名"
                  size="large"
                  autoComplete="username"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: "请输入密码" }]}
              >
                <Input.Password
                  prefix={<LockOutlined className="login-page__input-icon" />}
                  placeholder="请输入密码"
                  size="large"
                  autoComplete="current-password"
                />
              </Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                block
                size="large"
                loading={loading}
                className="login-page__submit"
                icon={<ArrowRightOutlined />}
                iconPosition="end"
              >
                进入平台
              </Button>
            </Form>

            <p className="login-page__demo-hint">
              <span className="login-page__demo-badge">Demo</span>
              体验环境 · admin / admin123
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
