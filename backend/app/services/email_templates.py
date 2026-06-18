"""Branded, responsive HTML e-mail templates.

These templates render a polished, on-brand message (logo, product name and
accent color come from platform settings) for security e-mails such as MFA
login codes and password-reset codes. Everything is inline-styled so it renders
consistently across major mail clients (Gmail / Outlook / Apple Mail).
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from app.models.platform_settings import PlatformSettings


def _accent(plat: PlatformSettings) -> str:
    color = (plat.accent_color or "").strip()
    return color or "#ff6600"


def _shade(hex_color: str, factor: float) -> str:
    """Darken a #rrggbb color by *factor* (0..1) for gradient depth."""
    try:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        r, g, b = 255, 102, 0
    r, g, b = (max(0, int(c * (1 - factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _logo_block(plat: PlatformSettings, accent: str) -> str:
    logo = (plat.logo_url or plat.logo_mark_url or "").strip()
    name = html.escape(plat.product_name or "Network Ops")
    if logo and logo.startswith(("http://", "https://")):
        return (
            f'<img src="{html.escape(logo)}" alt="{name}" '
            'height="34" style="height:34px;display:inline-block;border:0;outline:none;" />'
        )
    initial = html.escape((plat.product_name or "N")[:1].upper())
    return (
        '<span style="display:inline-block;vertical-align:middle;">'
        f'<span style="display:inline-block;width:34px;height:34px;line-height:34px;'
        f'border-radius:9px;background:{accent};color:#ffffff;font-weight:700;'
        f'font-size:18px;text-align:center;">{initial}</span>'
        f'<span style="margin-left:10px;font-size:17px;font-weight:700;'
        f'color:#f8fafc;vertical-align:middle;">{name}</span>'
        '</span>'
    )


def render_email(
    plat: PlatformSettings,
    *,
    heading: str,
    intro: str,
    code: str | None = None,
    code_caption: str | None = None,
    outro: str | None = None,
    note: str | None = None,
) -> str:
    """Render a branded HTML e-mail and return the full document string."""
    accent = _accent(plat)
    accent_dark = _shade(accent, 0.35)
    product = html.escape(plat.product_name or "Network Ops")
    tagline = html.escape(plat.tagline or plat.login_subtitle or "")
    year = datetime.now(timezone.utc).year

    code_html = ""
    if code:
        caption = html.escape(code_caption or "您的验证码")
        digits = html.escape(code)
        code_html = f"""
        <tr>
          <td style="padding:8px 0 4px;">
            <div style="font-size:13px;color:#64748b;letter-spacing:.04em;margin-bottom:10px;">{caption}</div>
            <div style="display:inline-block;padding:16px 28px;border-radius:14px;
                        background-color:{accent};
                        background-image:linear-gradient(135deg,{accent} 0%,{accent_dark} 100%);
                        box-shadow:0 10px 24px -10px {accent};">
              <span style="font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;
                           font-size:34px;font-weight:700;letter-spacing:.42em;color:#ffffff;
                           padding-left:.42em;">{digits}</span>
            </div>
          </td>
        </tr>"""

    outro_html = ""
    if outro:
        outro_html = (
            f'<tr><td style="padding-top:18px;font-size:14px;line-height:1.7;'
            f'color:#475569;">{html.escape(outro)}</td></tr>'
        )

    note_html = ""
    if note:
        note_html = f"""
        <tr>
          <td style="padding-top:22px;">
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
                        padding:14px 16px;font-size:13px;line-height:1.65;color:#64748b;">
              {html.escape(note)}
            </div>
          </td>
        </tr>"""

    tagline_html = (
        f'<div style="margin-top:6px;font-size:12px;color:#94a3b8;'
        f'letter-spacing:.06em;">{tagline}</div>'
        if tagline
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{product}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f7;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;width:100%;background:#ffffff;border-radius:18px;overflow:hidden;
                      box-shadow:0 24px 60px -28px rgba(15,23,42,.45);">
          <tr>
            <td style="padding:26px 36px;background-color:#0f172a;background-image:linear-gradient(125deg,#0f172a 0%,{accent_dark} 130%);">
              {_logo_block(plat, accent)}
              {tagline_html}
            </td>
          </tr>
          <tr>
            <td style="height:4px;background-color:{accent};background-image:linear-gradient(90deg,{accent} 0%,{accent_dark} 100%);"></td>
          </tr>
          <tr>
            <td style="padding:36px 36px 30px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size:21px;font-weight:700;color:#0f172a;padding-bottom:12px;">
                    {html.escape(heading)}
                  </td>
                </tr>
                <tr>
                  <td style="font-size:14px;line-height:1.75;color:#475569;">
                    {html.escape(intro)}
                  </td>
                </tr>
                {code_html}
                {outro_html}
                {note_html}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 36px 28px;border-top:1px solid #eef2f7;">
              <div style="font-size:12px;line-height:1.7;color:#94a3b8;">
                此邮件由 {product} 安全系统自动发送，请勿直接回复。<br />
                &copy; {year} {product}. All rights reserved.
              </div>
            </td>
          </tr>
        </table>
        <div style="max-width:560px;margin:16px auto 0;font-size:11px;color:#b6c0cf;text-align:center;">
          如非本人操作，请忽略本邮件或联系系统管理员。
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""
