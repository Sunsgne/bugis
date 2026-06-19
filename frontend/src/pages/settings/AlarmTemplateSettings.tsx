import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Badge,
  Button,
  Card,
  Col,
  Collapse,
  Form,
  Input,
  Row,
  Segmented,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { FormInstance } from "antd/es/form";
import {
  EyeOutlined,
  MailOutlined,
  ReloadOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  useAlarmTemplates,
  type GlobalTemplate,
  type KindTemplate,
} from "../../hooks/useAlarmTemplates";
import { useTc } from "@/i18n/useTc";

const { Text, Title } = Typography;
const { TextArea } = Input;

const KIND_LABELS: Record<string, string> = {
  tunnel_down: "隧道异常",
  circuit_interruption: "业务中断",
  sla_loss: "丢包超标",
  sla_latency: "时延超标",
  utilization: "带宽拥塞",
  health: "健康劣化",
  circuit_flap: "闪断频繁",
  link_utilization: "骨干拥塞",
  test: "测试通知",
};

const PRIORITY_COLOR: Record<string, string> = {
  P1: "#cf1322",
  P2: "#d48806",
  P3: "#1677ff",
  "—": "#8c8c8c",
};

type PreviewMode = "text" | "html" | "subject";

function VariableChips({
  vars,
  onInsert,
}: {
  vars: { key: string; label: string }[];
  onInsert: (token: string) => void;
}) {
  if (!vars?.length) return null;
  return (
    <div className="alarm-template-vars">
      <Text type="secondary" style={{ fontSize: 12, marginRight: 8 }}>
        变量
      </Text>
      <Space size={[6, 6]} wrap>
        {vars.map((v) => (
          <Tooltip key={v.key} title={v.label}>
            <Tag
              className="alarm-template-var-chip"
              onClick={() => onInsert(`{{${v.key}}}`)}
            >
              {`{{${v.key}}}`}
            </Tag>
          </Tooltip>
        ))}
      </Space>
    </div>
  );
}

export default function AlarmTemplateSettings() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const { data, loading, saving, save, reset, preview } = useAlarmTemplates();
  const [selectedKind, setSelectedKind] = useState("sla_loss");
  const [globalForm] = Form.useForm<GlobalTemplate>();
  const [kindForm] = Form.useForm<KindTemplate>();
  const [previewMode, setPreviewMode] = useState<PreviewMode>("html");
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewText, setPreviewText] = useState("");
  const [previewSubject, setPreviewSubject] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!data) return;
    globalForm.setFieldsValue(data.global);
    const k = data.kinds[selectedKind];
    if (k) kindForm.setFieldsValue(k);
  }, [data, selectedKind, globalForm, kindForm]);

  const kindVars = useMemo(() => {
    if (!data) return [];
    const specific = data.variables[selectedKind] || [];
    const global = data.variables.global || [];
    return [...global, ...specific];
  }, [data, selectedKind]);

  const runPreview = useCallback(async () => {
    setPreviewLoading(true);
    try {
      const res = await preview(selectedKind);
      setPreviewHtml(res.html);
      setPreviewText(res.text);
      setPreviewSubject(res.subject);
    } catch {
      message.error(tc("预览失败"));
    } finally {
      setPreviewLoading(false);
    }
  }, [preview, selectedKind, message, tc]);

  useEffect(() => {
    if (data) runPreview();
  }, [data, selectedKind]); // eslint-disable-line react-hooks/exhaustive-deps

  function insertIntoForm(form: FormInstance, field: string, token: string) {
    const current = String(form.getFieldValue(field) || "");
    form.setFieldValue(field, current + token);
  }

  async function onSave() {
    if (!data) return;
    const global = await globalForm.validateFields();
    const kinds = { ...data.kinds };
    kinds[selectedKind] = await kindForm.validateFields();
    try {
      await save({ global, kinds });
      message.success(tc("告警模板已保存"));
      runPreview();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || tc("保存失败"));
    }
  }

  async function onReset() {
    try {
      await reset();
      message.success(tc("已恢复默认模板"));
      runPreview();
    } catch {
      message.error(tc("恢复失败"));
    }
  }

  function restoreKindDefault() {
    if (!data) return;
    const d = data.defaults.kinds[selectedKind];
    if (d) {
      kindForm.setFieldsValue(d);
      message.info(tc("已载入该类型默认文案（需保存后生效）"));
    }
  }

  if (loading || !data) {
    return (
      <div className="alarm-template-loading">
        <ThunderboltOutlined spin style={{ fontSize: 28, color: "#ff6600" }} />
      </div>
    );
  }

  return (
    <div className="alarm-template-editor">
      <div className="alarm-template-hero">
        <div>
          <Title level={4} style={{ margin: 0, color: "#fff" }}>
            {tc("告警通知模板")}
          </Title>
          <Text style={{ color: "rgba(255,255,255,.72)" }}>
            {tc("自定义外发至邮件、钉钉、飞书、Webhook 等渠道的告警文案与版式")}
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset} loading={saving}>
            {tc("恢复默认")}
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={onSave}
            className="alarm-template-save-btn"
          >
            {tc("保存模板")}
          </Button>
        </Space>
      </div>

      <Collapse
        ghost
        className="alarm-template-global-collapse"
        items={[
          {
            key: "global",
            label: (
              <Space>
                <MailOutlined />
                <Text strong>{tc("全局版式")}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {tc("页眉、页脚、邮件主题、章节标题")}
                </Text>
              </Space>
            ),
            children: (
              <Form form={globalForm} layout="vertical" className="app-form">
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="banner" label={tc("通知页眉")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="footer" label={tc("通知页脚")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="email_subject" label={tc("邮件主题")}>
                      <Input prefix={<MailOutlined />} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="html_enabled" label={tc("HTML 富文本邮件")} valuePropName="checked">
                      <Switch checkedChildren="ON" unCheckedChildren="OFF" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="meta_line" label={tc("元信息行")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="type_line" label={tc("类型行")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="detail_heading" label={tc("详情标题")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="impact_heading" label={tc("影响评估标题")}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="action_heading" label={tc("处置建议标题")}>
                      <Input />
                    </Form.Item>
                  </Col>
                </Row>
                <VariableChips
                  vars={data.variables.global || []}
                  onInsert={(t) => insertIntoForm(globalForm, "banner", t)}
                />
              </Form>
            ),
          },
        ]}
      />

      <Row gutter={20} className="alarm-template-main">
        <Col xs={24} lg={6}>
          <Card size="small" className="alarm-template-kind-list" title={tc("告警类型")}>
            <div className="alarm-template-kind-scroll">
              {data.kinds_order.map((kind) => {
                const k = data.kinds[kind];
                const active = kind === selectedKind;
                return (
                  <button
                    key={kind}
                    type="button"
                    className={`alarm-template-kind-item${active ? " is-active" : ""}`}
                    onClick={() => setSelectedKind(kind)}
                  >
                    <span className="alarm-template-kind-name">{KIND_LABELS[kind] || kind}</span>
                    <Badge
                      count={k?.priority || "—"}
                      style={{ backgroundColor: PRIORITY_COLOR[k?.priority || "—"] }}
                    />
                  </button>
                );
              })}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            size="small"
            className="alarm-template-editor-card"
            title={
              <Space>
                <ThunderboltOutlined style={{ color: "#ff6600" }} />
                {KIND_LABELS[selectedKind]}
              </Space>
            }
            extra={
              <Button type="link" size="small" onClick={restoreKindDefault}>
                {tc("恢复此类型默认")}
              </Button>
            }
          >
            <Form form={kindForm} layout="vertical" className="app-form">
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="kind_label" label={tc("类型名称")}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="category" label={tc("分类")}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="priority" label={tc("优先级")}>
                    <Input placeholder="P1 / P2 / P3" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="title" label={tc("告警标题")}>
                <Input />
              </Form.Item>
              <Form.Item name="detail" label={tc("详情正文")}>
                <TextArea rows={3} />
              </Form.Item>
              <Form.Item name="impact" label={tc("影响评估")}>
                <TextArea rows={2} />
              </Form.Item>
              <Form.Item name="action" label={tc("处置建议")}>
                <TextArea rows={2} />
              </Form.Item>
            </Form>
            <VariableChips
              vars={kindVars}
              onInsert={(t) => insertIntoForm(kindForm, "title", t)}
            />
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            size="small"
            className="alarm-template-preview-card"
            title={
              <Space>
                <EyeOutlined />
                {tc("实时预览")}
              </Space>
            }
            extra={
              <Button size="small" icon={<EyeOutlined />} loading={previewLoading} onClick={runPreview}>
                {tc("刷新")}
              </Button>
            }
          >
            <Segmented
              block
              value={previewMode}
              onChange={(v) => setPreviewMode(v as PreviewMode)}
              options={[
                { label: "HTML 邮件", value: "html" },
                { label: tc("纯文本"), value: "text" },
                { label: tc("主题"), value: "subject" },
              ]}
              style={{ marginBottom: 12 }}
            />
            {previewMode === "html" && (
              <div className="alarm-template-preview-frame-wrap">
                <iframe
                  title="preview"
                  className="alarm-template-preview-frame"
                  srcDoc={previewHtml}
                  sandbox=""
                />
              </div>
            )}
            {previewMode === "text" && (
              <pre className="alarm-template-preview-text">{previewText}</pre>
            )}
            {previewMode === "subject" && (
              <div className="alarm-template-subject-preview">
                <MailOutlined style={{ marginRight: 8, color: "#ff6600" }} />
                {previewSubject}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
