import type { ModalProps } from "antd";

/** Standard props for data-entry modals: scrollable body, readable form width. */
export const formModalProps: Pick<
  ModalProps,
  "width" | "centered" | "destroyOnClose" | "styles" | "wrapClassName"
> = {
  width: 640,
  centered: true,
  destroyOnClose: true,
  wrapClassName: "app-form-modal",
  styles: {
    body: {
      maxHeight: "calc(85vh - 110px)",
      overflowY: "auto",
      overflowX: "hidden",
      padding: "20px 24px 24px",
    },
  },
};
