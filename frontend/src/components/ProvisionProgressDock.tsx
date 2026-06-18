import { Button, Progress, Space, Tag, Typography } from "antd";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  CloseOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import type { Circuit, ProvisionResult } from "../api/types";

type Props = {
  circuit: Circuit | null;
  woType?: string;
  loading: boolean;
  result: ProvisionResult | null;
  error: string | null;
  onOpenDetails: () => void;
  onClose: () => void;
};

const STATUS_LABEL: Record<string, string> = {
  scheduled: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  rolled_back: "已回滚",
  cancelled: "已取消",
};

/**
 * Compact, non-blocking progress indicator pinned to the bottom-right corner.
 * Replaces the full-screen provisioning/teardown modal so the operator can keep
 * working while a circuit is being applied or torn down. Click 查看详情 to open
 * the full staged view.
 */
export default function ProvisionProgressDock({
  circuit,
  woType = "provision",
  loading,
  result,
  error,
  onOpenDetails,
  onClose,
}: Props) {
  if (!circuit) return null;

  const isTeardown = woType === "decommission";
  const opLabel = isTeardown ? "拆除回收" : "开通下发";
  const status = result?.status;
  const inProgress = loading || status === "running" || status === "scheduled";
  const failed = !!error || status === "failed";
  const success = status === "completed";

  const stage = inProgress
    ? status === "scheduled"
      ? "已加入后台队列，等待执行…"
      : isTeardown
        ? "正在回收各端设备配置…"
        : "正在向各端设备下发配置…"
    : success
      ? isTeardown
        ? "资源已释放，拆除完成"
        : "配置已下发完成"
      : failed
        ? "执行失败，点击查看详情"
        : "等待结果";

  const jobs = result?.config_jobs || [];
  const okJobs = jobs.filter((j) => j.status === "succeeded" || j.status === "dry_run").length;
  const percent = inProgress
    ? jobs.length
      ? Math.min(95, Math.round((okJobs / Math.max(jobs.length, 1)) * 100))
      : 30
    : success
      ? 100
      : failed
        ? 100
        : 0;

  const accent = failed ? "#ff4d4f" : success ? "#52c41a" : "#ff6600";

  return (
    <div
      style={{
        position: "fixed",
        right: 24,
        bottom: 24,
        width: 340,
        zIndex: 1100,
        background: "#fff",
        borderRadius: 12,
        boxShadow: "0 8px 32px rgba(0,0,0,.18)",
        borderLeft: `4px solid ${accent}`,
        padding: "14px 16px",
      }}
    >
      <Space style={{ width: "100%", justifyContent: "space-between" }} align="start">
        <Space size={8}>
          {inProgress ? (
            <LoadingOutlined style={{ color: accent, fontSize: 18 }} spin />
          ) : success ? (
            <CheckCircleFilled style={{ color: accent, fontSize: 18 }} />
          ) : (
            <CloseCircleFilled style={{ color: accent, fontSize: 18 }} />
          )}
          <div>
            <Typography.Text strong>
              {opLabel} · {circuit.code}
            </Typography.Text>
            {status ? (
              <Tag style={{ marginLeft: 8 }} color={failed ? "red" : success ? "green" : "processing"}>
                {STATUS_LABEL[status] || status}
              </Tag>
            ) : null}
          </div>
        </Space>
        <Button type="text" size="small" icon={<CloseOutlined />} onClick={onClose} />
      </Space>

      <Typography.Paragraph type="secondary" style={{ margin: "8px 0 6px", fontSize: 12 }}>
        {stage}
      </Typography.Paragraph>

      <Progress
        percent={percent}
        size="small"
        status={failed ? "exception" : success ? "success" : "active"}
        showInfo={false}
        strokeColor={accent}
      />

      <Space style={{ width: "100%", justifyContent: "space-between", marginTop: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {jobs.length ? `设备作业 ${okJobs}/${jobs.length}` : circuit.name}
        </Typography.Text>
        <Button type="link" size="small" onClick={onOpenDetails}>
          查看详情
        </Button>
      </Space>
    </div>
  );
}
