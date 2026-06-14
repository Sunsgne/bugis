import { Button, Card, Form, Input, Typography, App as AntApp } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useState } from "react";
import { login } from "../api/client";
import { useAuth } from "../auth";

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
    <div className="login-wrap">
      <Card style={{ width: 380, boxShadow: "0 12px 40px rgba(0,0,0,0.25)" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <Typography.Title level={3} style={{ marginBottom: 0 }}>
            Bugis 专线运营平台
          </Typography.Title>
          <Typography.Text type="secondary">
            DCI · EVPN VXLAN · SR-MPLS EVPN
          </Typography.Text>
        </div>
        <Form onFinish={onFinish} initialValues={{ username: "admin", password: "admin123" }}>
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading}>
            登录
          </Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}>
          默认账号 admin / admin123
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
