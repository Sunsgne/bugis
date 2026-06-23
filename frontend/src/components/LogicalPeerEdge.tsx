import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

type EdgeData = {
  label?: string;
  curvature?: number;
  pathMode?: "bezier" | "smoothstep" | "straight";
  stepOffset?: number;
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
  const pathMode = d?.pathMode ?? "smoothstep";

  let edgePath: string;
  let labelX: number;
  let labelY: number;

  if (pathMode === "straight") {
    [edgePath, labelX, labelY] = getStraightPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
    });
  } else {
    [edgePath, labelX, labelY] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      borderRadius: 0,
      offset: d?.stepOffset ?? 0,
    });
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={style}
        interactionWidth={12}
      />
      {d?.label ? (
        <EdgeLabelRenderer>
          <div
            className="backbone-logical-edge-label nodrag nopan"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY + 14}px)`,
            }}
          >
            {d.label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
