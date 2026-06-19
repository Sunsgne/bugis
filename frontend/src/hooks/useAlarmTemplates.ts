import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

export type KindTemplate = {
  kind_label: string;
  category: string;
  priority: string;
  title: string;
  detail: string;
  impact: string;
  action: string;
};

export type GlobalTemplate = {
  banner: string;
  footer: string;
  email_subject: string;
  detail_heading: string;
  impact_heading: string;
  action_heading: string;
  meta_line: string;
  type_line: string;
  html_enabled: boolean;
};

export type VariableDef = { key: string; label: string };

export type AlarmTemplatesData = {
  global: GlobalTemplate;
  kinds: Record<string, KindTemplate>;
  defaults: { global: GlobalTemplate; kinds: Record<string, KindTemplate> };
  variables: Record<string, VariableDef[]>;
  kinds_order: string[];
};

export type PreviewResult = {
  text: string;
  html: string;
  subject: string;
  title: string;
};

export function useAlarmTemplates() {
  const [data, setData] = useState<AlarmTemplatesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: res } = await api.get<AlarmTemplatesData>("/system/settings/alarm-templates");
      setData(res);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function save(payload: Pick<AlarmTemplatesData, "global" | "kinds">) {
    setSaving(true);
    try {
      const { data: res } = await api.put<AlarmTemplatesData>("/system/settings/alarm-templates", payload);
      setData(res);
      return res;
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      const { data: res } = await api.post<AlarmTemplatesData>("/system/settings/alarm-templates/reset");
      setData(res);
      return res;
    } finally {
      setSaving(false);
    }
  }

  async function preview(kind: string, severity = "major") {
    const { data: res } = await api.post<PreviewResult>("/system/settings/alarm-templates/preview", {
      kind,
      severity,
    });
    return res;
  }

  return { data, loading, saving, load, save, reset, preview };
}
