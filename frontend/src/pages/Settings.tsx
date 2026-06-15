import { useEffect } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  ColorPicker,
  Divider,
  Form,
  Input,
  Row,
  Space,
  Typography,
  Upload,
  App as AntApp,
} from "antd";
import { SaveOutlined, UndoOutlined, UploadOutlined } from "@ant-design/icons";
import type { Color } from "antd/es/color-picker";
import type { UploadProps } from "antd";
import { useBrand, type BrandConfig } from "../context/BrandContext";
import { BrandLogo } from "../components/BrandLogo";
import { page, toast } from "../constants/uiCopy";
import { useAuth } from "../auth";

const { Text, Title } = Typography;

async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function makeUploadProps(
  onDataUrl: (url: string | null) => void,
  message: ReturnType<typeof AntApp.useApp>["message"]
): UploadProps {
  return {
    accept: "image/png,image/jpeg,image/svg+xml,image/webp",
    showUploadList: false,
    beforeUpload: async (file) => {
      if (file.size > 512 * 1024) {
        message.error("图片请小于 512KB");
        return Upload.LIST_IGNORE;
      }
      const url = await fileToDataUrl(file);
      onDataUrl(url);
      return false;
    },
  };
}

export default function Settings() {
  const { message } = AntApp.useApp();
  const { user } = useAuth();
  const { brand, save, reload } = useBrand();
  const canEdit = user?.role === "admin" || user?.role === "operator";
  const [form] = Form.useForm<BrandConfig>();

  useEffect(() => {
    form.setFieldsValue(brand);
  }, [brand, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("品牌与外观已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  function resetDefaults() {
    form.setFieldsValue({
      product_name: "Bugis Network",
      header_title: "DCI / EVPN 全域网络运营中枢",
      tagline: "DCI · EVPN 全域智能运营",
      login_title: "Bugis Network",
      login_subtitle: "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops",
      hero_title: "DCI / EVPN 运营驾驶舱",
      hero_subtitle: "多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI",
      logo_url: null,
      logo_mark_url: null,
      accent_color: "#52c41a",
      login_background: "linear-gradient(135deg, #0b1f3a 0%, #1677ff 100%)",
    });
  }

  const preview = Form.useWatch([], form) as BrandConfig | undefined;
  const previewBrand = { ...brand, ...preview };

  return (
    <Card title={page.settings}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
        message="品牌与 Logo 自定义"
        description="修改后将同步应用于登录页、侧栏 Logo、顶栏标题与运营驾驶舱横幅。Logo 支持 PNG / SVG / WebP（Base64 存储，建议小于 512KB）。"
      />
      {!canEdit && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前账号为只读权限，无法保存品牌设置"
        />
      )}

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          <Form form={form} layout="vertical" disabled={!canEdit}>
            <Title level={5} style={{ marginTop: 0 }}>
              全局品牌
            </Title>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="product_name" label="产品名称（侧栏）" rules={[{ required: true }]}>
                  <Input placeholder="Bugis Network" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="tagline" label="产品 Tagline">
                  <Input placeholder="DCI · EVPN 全域智能运营" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="header_title" label="顶栏标题" rules={[{ required: true }]}>
              <Input placeholder="DCI / EVPN 全域网络运营中枢" />
            </Form.Item>

            <Divider />
            <Title level={5}>登录页</Title>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="login_title" label="登录标题" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="login_subtitle" label="登录副标题">
                  <Input />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="login_background"
              label="登录页背景"
              extra="CSS background 值，如 linear-gradient(...) 或 #0b1f3a"
            >
              <Input placeholder="linear-gradient(135deg, #0b1f3a 0%, #1677ff 100%)" />
            </Form.Item>

            <Divider />
            <Title level={5}>运营驾驶舱</Title>
            <Form.Item name="hero_title" label="横幅主标题" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="hero_subtitle" label="横幅副标题">
              <Input.TextArea rows={2} />
            </Form.Item>

            <Divider />
            <Title level={5}>Logo 与主题色</Title>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="logo_url" label="主 Logo（侧栏 / 登录）">
                  <Input placeholder="URL 或上传图片" allowClear />
                </Form.Item>
                <Upload {...makeUploadProps((url) => form.setFieldValue("logo_url", url), message)}>
                  <Button icon={<UploadOutlined />} size="small">
                    上传主 Logo
                  </Button>
                </Upload>
              </Col>
              <Col span={12}>
                <Form.Item name="logo_mark_url" label="Mark / Favicon">
                  <Input placeholder="小图标 · 浏览器标签页" allowClear />
                </Form.Item>
                <Upload {...makeUploadProps((url) => form.setFieldValue("logo_mark_url", url), message)}>
                  <Button icon={<UploadOutlined />} size="small">
                    上传 Mark
                  </Button>
                </Upload>
              </Col>
            </Row>
            <Form.Item
              name="accent_color"
              label="强调色"
              getValueFromEvent={(color: Color) => color.toHexString()}
            >
              <ColorPicker showText format="hex" />
            </Form.Item>

            <Space style={{ marginTop: 8 }}>
              <Button type="primary" icon={<SaveOutlined />} onClick={onSave} disabled={!canEdit}>
                保存
              </Button>
              <Button icon={<UndoOutlined />} onClick={resetDefaults} disabled={!canEdit}>
                恢复默认文案
              </Button>
              <Button onClick={() => reload()}>重新加载</Button>
            </Space>
          </Form>
        </Col>

        <Col xs={24} lg={10}>
          <Card size="small" title="实时预览" style={{ position: "sticky", top: 16 }}>
            <div
              style={{
                background: "#001529",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 12,
              }}
            >
              <BrandLogo brand={previewBrand} variant="sidebar" />
              <Text style={{ color: "#fff", fontWeight: 600 }}>{previewBrand.product_name}</Text>
            </div>
            <div
              style={{
                background: previewBrand.login_background || undefined,
                borderRadius: 8,
                padding: 20,
                color: "#fff",
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
                <BrandLogo brand={previewBrand} variant="login" height={36} />
              </div>
              <div style={{ textAlign: "center", fontWeight: 700 }}>{previewBrand.login_title}</div>
              <div style={{ textAlign: "center", opacity: 0.85, fontSize: 12, marginTop: 4 }}>
                {previewBrand.login_subtitle}
              </div>
            </div>
            <div
              style={{
                background: "linear-gradient(120deg, #0b1f3a 0%, #1668dc 60%, #13c2c2 100%)",
                borderRadius: 8,
                padding: 16,
                color: "#fff",
              }}
            >
              <div style={{ fontWeight: 700 }}>{previewBrand.hero_title}</div>
              <div style={{ opacity: 0.85, fontSize: 12, marginTop: 4 }}>{previewBrand.hero_subtitle}</div>
            </div>
            <Text type="secondary" style={{ display: "block", marginTop: 12, fontSize: 12 }}>
              顶栏：{previewBrand.header_title}
            </Text>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
