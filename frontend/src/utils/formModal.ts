import type { ModalProps } from "antd";

/** Standard props for data-entry modals: scrollable body, readable form width.
 *
 * `maskClosable: false` so clicking the dimmed backdrop never discards a form
 * in progress — the dialog must be closed deliberately via 取消 / 关闭 (✕).
 * `keyboard: false` likewise disables accidental Esc-to-close. */
export const formModalProps: Pick<
  ModalProps,
  "width" | "centered" | "destroyOnClose" | "styles" | "wrapClassName" | "maskClosable" | "keyboard"
> = {
  width: 640,
  centered: true,
  destroyOnClose: true,
  maskClosable: false,
  keyboard: false,
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
