import { BaseEdge, EdgeLabelRenderer, getBezierPath, getSmoothStepPath, getStraightPath, type EdgeProps } from "@xyflow/react";
import { Tooltip } from "antd";
import { useState } from "react";
import type { LinkUsage } from "@/api/types";
import { useTc } from "@/i18n/useTc";
import { backboneUtilColor } from "@/utils/linkUtilization";
import LinkUtilizationTooltipContent from "./LinkUtilizationTooltipContent";
import { linkUtilTooltipProps } from "@/utils/linkUtilTooltip";

const EDGE_STYLE: Record<string, { dash?: string; weight: number }> = {
  dci: { dash: "6 4", weight: 3 },
  intra_dc: { weight: 2.5 },
  access: { weight: 1.5 },
  uplink: { weight: 2 },
};

export type UtilizationEdgeData = {
  link?: LinkUsage;
  utilization_pct: number;
  shortLabel: string;
  highlighted?: boolean;
  pathHighlighted?: boolean;
  curvature?: number;
  labelOffsetY?: number;
  linkType?: string;
  /** Orthogonal straight segments (capacity backbone); default bezier curve. */
  pathMode?: "bezier" | "smoothstep" | "straight";
  stepOffset?: number;
};

function labelOffsetForEdge(curvature: number, explicit?: number): number {
  if (explicit != null) return explicit;
  const sign = curvature >= 0 ? -1 : 1;
  return sign * 20;
}

export default function UtilizationEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  ...props
}: EdgeProps) {
  const { tc } = useTc();
  const d = data as UtilizationEdgeData | undefined;
  const pct = d?.utilization_pct ?? 0;
  const color = backboneUtilColor(pct);
  const link = d?.link;
  const style = EDGE_STYLE[d?.linkType || "intra_dc"] || EDGE_STYLE.intra_dc;
  const [labelHover, setLabelHover] = useState(false);
  const active = Boolean(d?.highlighted || d?.pathHighlighted || labelHover);
  const showTooltip = Boolean(active && link && !d?.pathHighlighted);
  const showCompactLabel = Boolean(d?.shortLabel && active && !showTooltip);
  const pathStroke = d?.pathHighlighted ? "#6366f1" : color;
  const pathMode = d?.pathMode ?? "bezier";
  const curvature = d?.curvature ?? 0.18;
  const labelOffsetY = labelOffsetForEdge(curvature, d?.labelOffsetY);

  let edgePath: string;
  let labelX: number;
  let labelY: number;

  if (pathMode === "smoothstep") {
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
  } else if (pathMode === "straight") {
    [edgePath, labelX, labelY] = getStraightPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
    });
  } else {
    [edgePath, labelX, labelY] = getBezierPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      curvature,
    });
  }

  const labelTransform = `translate(-50%, -50%) translate(${labelX}px,${labelY + labelOffsetY}px)`;

  return (
    <>
      <BaseEdge
        path={edgePath}
        {...props}
        interactionWidth={24}
        style={{
          ...props.style,
          stroke: pathStroke,
          strokeWidth: selected || d?.highlighted || d?.pathHighlighted ? style.weight + 1.5 : style.weight,
          strokeDasharray: d?.pathHighlighted ? undefined : style.dash,
          strokeLinecap: pathMode === "smoothstep" || pathMode === "straight" ? "square" : "round",
          opacity: d?.highlighted || d?.pathHighlighted ? 1 : 0.88,
        }}
      />
      {active && d?.shortLabel ? (
        <EdgeLabelRenderer>
          <Tooltip
            {...linkUtilTooltipProps}
            open={showTooltip}
            placement="top"
            mouseEnterDelay={0}
            zIndex={2100}
            getPopupContainer={() => document.body}
            align={{ offset: [0, -8] }}
            title={link ? <LinkUtilizationTooltipContent link={link} pct={pct} tc={tc} /> : undefined}
          >
            <div
              className={[
                "backbone-edge-label",
                "physical-topology-edge-label",
                "nodrag",
                "nopan",
                showCompactLabel ? "is-visible" : "",
                showTooltip ? "is-tooltip-anchor" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{
                transform: labelTransform,
                borderColor: showCompactLabel ? color : "transparent",
              }}
              onMouseEnter={() => setLabelHover(true)}
              onMouseLeave={() => setLabelHover(false)}
            >
              {showCompactLabel ? d.shortLabel : null}
            </div>
          </Tooltip>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
