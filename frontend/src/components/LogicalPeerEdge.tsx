import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";

type EdgeData = {
  label?: string;
  curvature?: number;
};

export default function LogicalPeerEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style,
}: EdgeProps) {
  const d = data as EdgeData | undefined;
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: d?.curvature ?? 0.08,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={style} />
      {d?.label ? (
        <EdgeLabelRenderer>
          <div
            className="backbone-logical-edge-label nodrag nopan"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
          >
            {d.label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
