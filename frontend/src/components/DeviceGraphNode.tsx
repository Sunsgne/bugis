import { Handle, Position, useNodeId, useUpdateNodeInternals } from "@xyflow/react";
import { useEffect } from "react";

export type DeviceGraphNodeData = {
  label: string;
  fullName: string;
  meta: string;
  siteLabel?: string | null;
  border: string;
  online: boolean;
  dimmed?: boolean;
  pathActive?: boolean;
};

export const DEVICE_GRAPH_NODE_WIDTH = 220;
export const DEVICE_GRAPH_NODE_HEIGHT = 72;

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
      className={[
        "device-graph-node rounded-xl border-2 bg-white px-3 py-2 shadow-sm transition-all hover:shadow-md",
        data.pathActive ? "device-graph-node-path-active" : "",
      ].filter(Boolean).join(" ")}
      style={{
        borderColor: data.pathActive ? "#6366f1" : data.border,
        width: DEVICE_GRAPH_NODE_WIDTH,
        height: DEVICE_GRAPH_NODE_HEIGHT,
        opacity: data.dimmed ? 0.28 : 1,
      }}
      title={data.fullName}
    >
      <Handle type="target" position={Position.Top} id="top-in" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Top} id="top-out" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Bottom} id="bottom-in" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Bottom} id="bottom-out" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Left} id="left-in" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Left} id="left-out" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Right} id="right-in" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Right} id="right-out" className="!border-0 !bg-transparent !opacity-0 !min-w-0 !min-h-0 !w-1 !h-1" />
      <div className="flex items-start gap-2">
        <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-[12px] font-semibold leading-tight text-slate-800">
            {data.label}
          </div>
          <div className="mt-0.5 truncate text-[10px] text-slate-500">{data.meta}</div>
        </div>
        {data.siteLabel && (
          <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
            {data.siteLabel}
          </span>
        )}
      </div>
    </div>
  );
}
