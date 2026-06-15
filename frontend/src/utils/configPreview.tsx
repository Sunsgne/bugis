import type { ModalFuncProps } from "antd";
import type { ReactNode } from "react";

/** Shared layout for configuration preview modals. */
export const configPreviewModalProps: Pick<
  ModalFuncProps,
  "width" | "centered" | "styles" | "maskClosable"
> = {
  width: 1100,
  centered: true,
  maskClosable: true,
  styles: {
    body: {
      maxHeight: "calc(82vh - 108px)",
      overflow: "auto",
      paddingTop: 8,
    },
  },
};

/** Large form modal for「新建专线」— wide layout, minimal nested scrollbars. */
export const createCircuitModalProps: Pick<
  ModalFuncProps,
  "width" | "centered" | "styles" | "maskClosable" | "wrapClassName"
> = {
  width: 1280,
  centered: true,
  maskClosable: false,
  wrapClassName: "create-circuit-modal",
  styles: {
    body: {
      maxHeight: "calc(88vh - 110px)",
      overflowY: "auto",
      overflowX: "hidden",
      paddingTop: 4,
    },
  },
};

export function ConfigPreviewPre({ children }: { children: ReactNode }) {
  return <pre className="config-pre config-pre-lg">{children}</pre>;
}
