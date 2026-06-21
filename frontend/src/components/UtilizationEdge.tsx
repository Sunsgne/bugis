import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";
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
  curvature?: number;
  labelOffsetY?: number;
  linkType?: string;
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
  const active = Boolean(d?.highlighted || labelHover);
  const showTooltip = Boolean(active && link);
  const showCompactLabel = Boolean(d?.shortLabel && active && !showTooltip);
  const curvature = d?.curvature ?? 0.18;
  const labelOffsetY = labelOffsetForEdge(curvature, d?.labelOffsetY);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature,
  });

  const labelTransform = `translate(-50%, -50%) translate(${labelX}px,${labelY + labelOffsetY}px)`;

  return (
    <>
      <BaseEdge
        path={edgePath}
        {...props}
        interactionWidth={24}
        style={{
          ...props.style,
          stroke: color,
          strokeWidth: selected || d?.highlighted ? style.weight + 1.5 : style.weight,
          strokeDasharray: style.dash,
          strokeLinecap: "round",
          opacity: d?.highlighted ? 1 : 0.88,
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
