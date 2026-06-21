import type { TooltipProps } from "antd";

/** Shared Ant Design 6 tooltip props for link utilization popovers. */
export const linkUtilTooltipProps: Pick<
  TooltipProps,
  "overlayClassName" | "styles" | "classNames"
> = {
  overlayClassName: "link-util-tooltip-overlay",
  classNames: {
    root: "link-util-tooltip-root",
  },
  styles: {
    root: {
      filter: "none",
      maxWidth: "none",
    },
    container: {
      padding: 0,
      background: "transparent",
      boxShadow: "none",
      minWidth: 0,
      minHeight: 0,
      borderRadius: 0,
    },
  },
};
