"""Branded HTML template for alarm notification e-mails."""
from __future__ import annotations

import html

from app.models.alarm import Alarm
from app.models.platform_settings import PlatformSettings
from app.services import alarm_messages as msg
from app.services.alarm_template_registry import AlarmTemplates, get_templates, render_template
from app.services.email_templates import _accent, _logo_block, _shade


def render_alarm_email(
    plat: PlatformSettings,
    alarm: Alarm,
    *,
    copy: msg.AlarmCopy | None = None,
    templates: AlarmTemplates | None = None,
    plain_body: str | None = None,
) -> str:
    t = templates or get_templates()
    c = copy or msg.copy_from_alarm(alarm, t)
    g = t.global_
    product = plat.product_name or "Bugis Network"
    accent = _accent(plat)
    accent_dark = _shade(accent, 0.35)
    sev = msg.severity_label(alarm.severity.value)
    sev_color = {
        "critical": "#cf1322",
        "major": "#d4380d",
        "minor": "#d48806",
        "warning": "#faad14",
        "info": "#1677ff",
    }.get(alarm.severity.value, accent)

    ctx = {
        "product_name": product,
        "severity_label": sev,
        "severity_upper": alarm.severity.value.upper(),
        "priority": c.priority,
        "category": c.category,
        "kind_label": msg.kind_label(alarm.kind, t),
        "title": c.title,
    }

    def section(heading: str, body: str) -> str:
        if not body:
            return ""
        return f"""
        <tr>
          <td style="padding-top:18px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#94a3b8;margin-bottom:8px;">
              {html.escape(heading.lstrip("▎"))}
            </div>
            <div style="font-size:14px;line-height:1.75;color:#334155;background:#f8fafc;border-radius:12px;padding:14px 16px;border:1px solid #e2e8f0;">
              {html.escape(body)}
            </div>
          </td>
        </tr>"""

    meta_line = render_template(g.meta_line, ctx)
    type_line = render_template(g.type_line, ctx)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(c.title)}</title>
</head>
<body style="margin:0;padding:0;background:#0b1220;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(160deg,#0b1220 0%,#1e293b 55%,#0f172a 100%);padding:40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <tr>
            <td style="padding-bottom:20px;text-align:center;">
              <span style="display:inline-block;padding:6px 14px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:12px;color:#cbd5e1;letter-spacing:.08em;">
                NETWORK OPERATIONS ALERT
              </span>
            </td>
          </tr>
          <tr>
            <td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 32px 80px -24px rgba(0,0,0,.55);">
                <tr>
                  <td style="padding:28px 32px;background-color:#0f172a;background-image:linear-gradient(125deg,#0f172a 0%,{accent_dark} 140%);">
                    {_logo_block(plat, accent)}
                  </td>
                </tr>
                <tr>
                  <td style="height:4px;background:linear-gradient(90deg,{sev_color} 0%,{accent} 100%);"></td>
                </tr>
                <tr>
                  <td style="padding:32px 32px 8px;">
                    <div style="margin-bottom:14px;">
                      <span style="display:inline-block;padding:4px 10px;border-radius:8px;background:{sev_color}22;color:{sev_color};font-size:12px;font-weight:700;margin-right:8px;">{html.escape(sev)}</span>
                      <span style="display:inline-block;padding:4px 10px;border-radius:8px;background:#f1f5f9;color:#475569;font-size:12px;font-weight:600;">{html.escape(c.priority)}</span>
                      <span style="display:inline-block;padding:4px 10px;border-radius:8px;background:#f1f5f9;color:#64748b;font-size:12px;margin-left:4px;">{html.escape(c.category)}</span>
                    </div>
                    <div style="font-size:13px;color:#64748b;line-height:1.6;margin-bottom:6px;">{html.escape(meta_line)}</div>
                    <div style="font-size:13px;color:#64748b;margin-bottom:18px;">{html.escape(type_line)}</div>
                    <div style="font-size:22px;font-weight:800;color:#0f172a;line-height:1.35;letter-spacing:-.02em;">
                      {html.escape(c.title)}
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:8px 32px 28px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      {section(g.detail_heading, c.detail)}
                      {section(g.impact_heading, c.impact)}
                      {section(g.action_heading, c.action)}
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:18px 32px 26px;border-top:1px solid #f1f5f9;background:#fafbfc;">
                    <div style="font-size:12px;line-height:1.7;color:#94a3b8;">
                      {html.escape(render_template(g.footer, ctx))}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
