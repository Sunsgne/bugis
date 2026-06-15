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

export function ConfigPreviewPre({ children }: { children: ReactNode }) {
  return <pre className="config-pre config-pre-lg">{children}</pre>;
}
