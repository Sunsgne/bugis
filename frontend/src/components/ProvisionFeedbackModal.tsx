import {
  Alert,
  Collapse,
  Modal,
  Progress,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from "@ant-design/icons";
import type { Circuit, ProvisionResult } from "../api/types";
import { ConfigPreviewPre } from "../utils/configPreview";

const WO_STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  failed: "失败",
  running: "执行中",
  scheduled: "排队中",
  draft: "草稿",
  submitted: "已提交",
  approved: "已审批",
  cancelled: "已取消",
  rolled_back: "已回滚",
};

const CIRCUIT_STATUS_LABEL: Record<string, string> = {
  active: "运行中",
  provisioning: "开通中",
  failed: "失败",
  draft: "草稿",
  pending: "待开通",
  degraded: "降级",
  suspended: "暂停",
  decommissioned: "已拆除",
};

const JOB_STATUS_LABEL: Record<string, string> = {
  succeeded: "成功",
  failed: "失败",
  dry_run: "模拟成功",
  rendered: "已渲染",
  pending: "待执行",
};

const JOB_STATUS_COLOR: Record<string, string> = {
  succeeded: "green",
  failed: "red",
  dry_run: "gold",
  rendered: "blue",
  pending: "default",
};

type Props = {
  circuit: Circuit | null;
  woType?: string;
  loading: boolean;
  result: ProvisionResult | null;
  error: string | null;
  onClose: () => void;
};

function summarizeOutput(output?: string | null) {
  if (!output) return "—";
  const line = output.split("\n").find((l) => l.trim()) || output;
  return line.length > 120 ? `${line.slice(0, 120)}…` : line;
}

export default function ProvisionFeedbackModal({
  circuit,
  woType = "provision",
  loading,
  result,
  error,
  onClose,
}: Props) {
  const open = !!circuit;
  const isTeardown = woType === "decommission";
  const success = result?.status === "completed";
  const failed = !!error || result?.status === "failed";
  const inProgress =
    loading || result?.status === "running" || result?.status === "scheduled";
  const queued = result?.status === "scheduled";

  const currentStep = inProgress ? 1 : failed ? 2 : success ? 3 : 2;

  const title = isTeardown ? "拆除回收" : "开通下发";
  const stepItems = isTeardown
    ? [
        { title: "安全校验", description: "依赖 / 资源占用确认" },
        {
          title: "配置回收",
          description: inProgress ? "正在回收各端设备配置…" : "回收作业完毕",
        },
        {
          title: "资源释放",
          description: result?.circuit_status
            ? `专线状态：${CIRCUIT_STATUS_LABEL[result.circuit_status] || result.circuit_status}`
            : "等待结果",
        },
      ]
    : [
        { title: "合规预检", description: "VLAN / 端口占用校验" },
        {
          title: "编排下发",
          description: inProgress ? "正在创建工单并推送配置…" : "工单执行完毕",
        },
        {
          title: "结果确认",
          description: result?.circuit_status
            ? `专线状态：${CIRCUIT_STATUS_LABEL[result.circuit_status] || result.circuit_status}`
            : "等待结果",
        },
      ];

  const spinnerText = queued
    ? "已加入后台队列，正在等待工作线程执行…"
    : isTeardown
      ? "正在回收各端设备配置并释放资源，请稍候…"
      : "正在向各端设备渲染并下发配置，请稍候…";

  return (
    <Modal
      title={circuit ? `${title} · ${circuit.code}` : title}
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
      destroyOnClose
    >
      {circuit ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          {circuit.name} · {circuit.endpoints?.length || 0} 个端点
        </Typography.Paragraph>
      ) : null}

      <Steps
        size="small"
        current={currentStep}
        status={failed ? "error" : inProgress ? "process" : success ? "finish" : "process"}
        style={{ marginBottom: 20 }}
        items={stepItems}
      />

      {inProgress ? (
        <div style={{ textAlign: "center", padding: "32px 0" }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 36 }} spin />} />
          <Typography.Paragraph style={{ marginTop: 16 }}>
            {spinnerText}
          </Typography.Paragraph>
        </div>
      ) : null}

      {error ? (
        <Alert type="error" showIcon message={isTeardown ? "拆除失败" : "开通失败"} description={error} style={{ marginBottom: 16 }} />
      ) : null}

      {result ? (
        <>
          <Space wrap style={{ marginBottom: 16 }}>
            <Tag color={success ? "green" : "red"}>
              工单 {result.code} · {WO_STATUS_LABEL[result.status] || result.status}
            </Tag>
            <Tag color={result.circuit_status === "active" ? "green" : "default"}>
              专线 {CIRCUIT_STATUS_LABEL[result.circuit_status] || result.circuit_status}
            </Tag>
            {result.dry_run ? <Tag color="gold">Dry-run 模拟下发</Tag> : <Tag color="blue">现网下发</Tag>}
          </Space>

          {result.status === "completed" ? (
            <Alert
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              message={isTeardown ? "配置已回收完成" : "配置已下发完成"}
              description={`${result.config_jobs.filter((j) => j.status === "succeeded" || j.status === "dry_run").length} / ${result.config_jobs.length} 个设备作业成功`}
              style={{ marginBottom: 16 }}
            />
          ) : null}

          {result.status === "failed" ? (
            <Alert
              type="error"
              showIcon
              icon={<CloseCircleOutlined />}
              message="工单执行失败"
              description="请查看下方设备作业与流转轨迹中的错误信息"
              style={{ marginBottom: 16 }}
            />
          ) : null}

          <Typography.Title level={5} style={{ marginTop: 0 }}>
            设备下发作业
          </Typography.Title>
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={result.config_jobs}
            locale={{ emptyText: "无配置作业（可能被预检阻断）" }}
            columns={[
              {
                title: "设备",
                render: (_, row) => row.device_name || `#${row.device_id}`,
              },
              { title: "操作", dataIndex: "operation", width: 72 },
              { title: "传输", dataIndex: "transport", width: 88 },
              {
                title: "状态",
                dataIndex: "status",
                width: 96,
                render: (s: string) => (
                  <Tag color={JOB_STATUS_COLOR[s] || "default"}>{JOB_STATUS_LABEL[s] || s}</Tag>
                ),
              },
              {
                title: "回显",
                dataIndex: "output",
                ellipsis: true,
                render: (v?: string) => summarizeOutput(v),
              },
            ]}
            expandable={{
              expandedRowRender: (row) => (
                <div>
                  {row.output ? (
                    <pre className="config-pre" style={{ maxHeight: 120, marginBottom: 8 }}>
                      {row.output}
                    </pre>
                  ) : null}
                  {row.rendered_config ? (
                    <Collapse
                      size="small"
                      items={[
                        {
                          key: "cfg",
                          label: "渲染配置片段",
                          children: <ConfigPreviewPre>{row.rendered_config}</ConfigPreviewPre>,
                        },
                      ]}
                    />
                  ) : null}
                </div>
              ),
              rowExpandable: (row) => !!(row.output || row.rendered_config),
            }}
          />

          <Typography.Title level={5}>流转轨迹</Typography.Title>
          <Timeline
            items={(result.events || []).map((e) => ({
              color: e.level === "error" ? "red" : e.level === "warning" ? "orange" : "blue",
              children: (
                <span>
                  {e.message}
                  {e.actor ? <Tag style={{ marginLeft: 8 }}>{e.actor}</Tag> : null}
                </span>
              ),
            }))}
          />

          {result.config_jobs.length > 0 ? (
            <div style={{ marginTop: 8 }}>
              <Typography.Text type="secondary">作业成功率</Typography.Text>
              <Progress
                percent={Math.round(
                  (result.config_jobs.filter((j) => j.status === "succeeded" || j.status === "dry_run")
                    .length /
                    result.config_jobs.length) *
                    100,
                )}
                status={success ? "success" : "exception"}
                size="small"
              />
            </div>
          ) : null}
        </>
      ) : null}
    </Modal>
  );
}
