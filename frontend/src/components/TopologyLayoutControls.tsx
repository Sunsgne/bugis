import { ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Space, Switch, Tooltip } from "antd";
import { useTc } from "@/i18n/useTc";

type Props = {
  layoutDirty: boolean;
  saving: boolean;
  autoSave: boolean;
  onAutoSaveChange: (checked: boolean) => void;
  onSave: () => void;
  onReset: () => void;
  compact?: boolean;
};

export default function TopologyLayoutControls({
  layoutDirty,
  saving,
  autoSave,
  onAutoSaveChange,
  onSave,
  onReset,
  compact = false,
}: Props) {
  const { tc } = useTc();

  return (
    <Space wrap size={compact ? "small" : "middle"}>
      <Tooltip title={tc("开启后，拖动设备位置将自动写入服务端，无需手动点击保存")}>
        <Space size={6}>
          <Switch size="small" checked={autoSave} onChange={onAutoSaveChange} />
          <span className={compact ? "text-[11px] text-slate-500" : "text-xs text-muted-foreground"}>
            {tc("拖动后自动保存")}
          </span>
        </Space>
      </Tooltip>
      <Button
        type="primary"
        size={compact ? "small" : "middle"}
        icon={<SaveOutlined />}
        disabled={autoSave || !layoutDirty}
        loading={saving}
        onClick={onSave}
      >
        {tc("保存布局")}
      </Button>
      <Button size={compact ? "small" : "middle"} icon={<ReloadOutlined />} loading={saving} onClick={onReset}>
        {tc("恢复自动布局")}
      </Button>
    </Space>
  );
}
