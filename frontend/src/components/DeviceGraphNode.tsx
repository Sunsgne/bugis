import { Handle, Position, useNodeId, useUpdateNodeInternals } from "@xyflow/react";
import { useEffect } from "react";
import {
  EDGE_HANDLE_SLOT_COUNT,
  EDGE_HANDLE_SLOT_OFFSETS,
  type EdgeHandleSide,
} from "@/utils/deviceGraphLayout";

export type DeviceGraphNodeData = {
  label: string;
  fullName: string;
  meta: string;
  siteLabel?: string | null;
  border: string;
  online: boolean;
  dimmed?: boolean;
};

export const DEVICE_GRAPH_NODE_WIDTH = 220;
export const DEVICE_GRAPH_NODE_HEIGHT = 72;

const SIDE_CONFIG: { side: EdgeHandleSide; position: Position }[] = [
  { side: "top", position: Position.Top },
  { side: "right", position: Position.Right },
  { side: "bottom", position: Position.Bottom },
  { side: "left", position: Position.Left },
];

function slotStyle(side: EdgeHandleSide, slot: number): React.CSSProperties {
  const pct = `${Math.round(EDGE_HANDLE_SLOT_OFFSETS[slot] * 100)}%`;
  if (side === "top" || side === "bottom") {
    return { left: pct, transform: "translateX(-50%)" };
  }
  return { top: pct, transform: "translateY(-50%)" };
}

export default function DeviceGraphNode({ data }: { data: DeviceGraphNodeData }) {
  const nodeId = useNodeId();
  const updateNodeInternals = useUpdateNodeInternals();

  useEffect(() => {
    if (nodeId) {
      updateNodeInternals(nodeId);
    }
  }, [nodeId, updateNodeInternals, data.label, data.siteLabel]);

  return (
    <div
      className="device-graph-node rounded-xl border-2 bg-white px-3 py-2.5 shadow-sm transition-all hover:shadow-md"
      style={{
        borderColor: data.border,
        width: DEVICE_GRAPH_NODE_WIDTH,
        height: DEVICE_GRAPH_NODE_HEIGHT,
        opacity: data.dimmed ? 0.35 : 1,
      }}
      title={data.fullName}
    >
      {SIDE_CONFIG.flatMap(({ side, position }) =>
        Array.from({ length: EDGE_HANDLE_SLOT_COUNT }, (_, slot) => [
          <Handle
            key={`${side}-in-${slot}`}
            type="target"
            position={position}
            id={`${side}-in-${slot}`}
            className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1"
            style={slotStyle(side, slot)}
          />,
          <Handle
            key={`${side}-out-${slot}`}
            type="source"
            position={position}
            id={`${side}-out-${slot}`}
            className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1"
            style={slotStyle(side, slot)}
          />,
        ]).flat(),
      )}
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <span className="truncate text-sm font-semibold text-slate-800">{data.label}</span>
        {data.siteLabel && (
          <span className="ml-auto shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
            {data.siteLabel}
          </span>
        )}
      </div>
      <div className="mt-1 truncate text-[11px] text-slate-500">{data.meta}</div>
    </div>
  );
}
