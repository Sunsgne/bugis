/** Mainstream SMTP provider presets (host / port / TLS). */

export type SmtpSecurity = "none" | "starttls" | "ssl";

export interface SmtpPreset {
  id: string;
  name: string;
  category: string;
  host: string;
  port: number;
  security: SmtpSecurity;
  userHint?: string;
  fromHint?: string;
  doc?: string;
}

export const SMTP_PRESETS: SmtpPreset[] = [
  // --- 国内个人邮箱 ---
  {
    id: "qq",
    name: "QQ 邮箱",
    category: "国内邮箱",
    host: "smtp.qq.com",
    port: 465,
    security: "ssl",
    userHint: "完整 QQ 邮箱地址",
    fromHint: "与 QQ 邮箱相同",
    doc: "需在 QQ 邮箱设置中开启 SMTP 并使用授权码（非 QQ 密码）。",
  },
  {
    id: "foxmail",
    name: "Foxmail",
    category: "国内邮箱",
    host: "smtp.qq.com",
    port: 465,
    security: "ssl",
    userHint: "Foxmail 邮箱地址",
    doc: "与 QQ 邮箱共用 SMTP，使用授权码登录。",
  },
  {
    id: "163",
    name: "网易 163",
    category: "国内邮箱",
    host: "smtp.163.com",
    port: 465,
    security: "ssl",
    userHint: "163 邮箱地址",
    doc: "需在网易邮箱 → 设置 → POP3/SMTP 中开启并获取授权码。",
  },
  {
    id: "126",
    name: "网易 126",
    category: "国内邮箱",
    host: "smtp.126.com",
    port: 465,
    security: "ssl",
    userHint: "126 邮箱地址",
    doc: "需开启 SMTP 并使用客户端授权码。",
  },
  {
    id: "yeah",
    name: "网易 Yeah.net",
    category: "国内邮箱",
    host: "smtp.yeah.net",
    port: 465,
    security: "ssl",
    userHint: "Yeah.net 邮箱地址",
  },
  {
    id: "sina",
    name: "新浪邮箱",
    category: "国内邮箱",
    host: "smtp.sina.com",
    port: 465,
    security: "ssl",
    userHint: "新浪邮箱地址",
    doc: "需开启 SMTP 并使用授权码。",
  },
  {
    id: "sohu",
    name: "搜狐邮箱",
    category: "国内邮箱",
    host: "smtp.sohu.com",
    port: 465,
    security: "ssl",
    userHint: "搜狐邮箱地址",
  },
  {
    id: "aliyun_personal",
    name: "阿里个人邮箱",
    category: "国内邮箱",
    host: "smtp.aliyun.com",
    port: 465,
    security: "ssl",
    userHint: "阿里邮箱地址",
  },

  // --- 国内企业邮 ---
  {
    id: "exmail",
    name: "腾讯企业邮",
    category: "国内企业邮",
    host: "smtp.exmail.qq.com",
    port: 465,
    security: "ssl",
    userHint: "企业邮箱账号",
    fromHint: "已验证的发件地址",
    doc: "腾讯企业邮 / 微信企业邮箱管理后台可查看 SMTP 参数。",
  },
  {
    id: "aliyun_enterprise",
    name: "阿里企业邮",
    category: "国内企业邮",
    host: "smtp.mxhichina.com",
    port: 465,
    security: "ssl",
    userHint: "企业邮箱账号",
    doc: "阿里云企业邮箱（万网邮）SMTP 服务器。",
  },
  {
    id: "netease_enterprise",
    name: "网易企业邮",
    category: "国内企业邮",
    host: "smtp.qiye.163.com",
    port: 994,
    security: "ssl",
    userHint: "企业邮箱账号",
  },
  {
    id: "feishu",
    name: "飞书企业邮箱",
    category: "国内企业邮",
    host: "smtp.feishu.cn",
    port: 465,
    security: "ssl",
    userHint: "飞书邮箱账号",
    doc: "需在飞书管理后台开启第三方客户端 / SMTP。",
  },

  // --- 国内云邮件推送 ---
  {
    id: "aliyun_dm",
    name: "阿里云邮件推送",
    category: "云邮件服务",
    host: "smtpdm.aliyun.com",
    port: 465,
    security: "ssl",
    userHint: "控制台发信地址",
    fromHint: "已验证发信域名地址",
    doc: "阿里云 DirectMail 控制台获取 SMTP 账号与密码。",
  },
  {
    id: "tencent_ses",
    name: "腾讯云邮件推送",
    category: "云邮件服务",
    host: "smtp.qcloudmail.com",
    port: 465,
    security: "ssl",
    userHint: "控制台 SMTP 账号",
    doc: "腾讯云 SES 控制台 → 发信地址 → SMTP 设置。",
  },
  {
    id: "huawei_dm",
    name: "华为云邮件",
    category: "云邮件服务",
    host: "smtp.huaweicloud.com",
    port: 465,
    security: "ssl",
    userHint: "华为云邮件账号",
  },

  // --- 国际邮箱 ---
  {
    id: "gmail",
    name: "Gmail / Google Workspace",
    category: "国际邮箱",
    host: "smtp.gmail.com",
    port: 587,
    security: "starttls",
    userHint: "Gmail 地址",
    doc: "需开启两步验证并使用应用专用密码（App Password）。",
  },
  {
    id: "outlook365",
    name: "Microsoft 365 / Exchange Online",
    category: "国际邮箱",
    host: "smtp.office365.com",
    port: 587,
    security: "starttls",
    userHint: "Microsoft 365 邮箱",
    doc: "组织需允许 SMTP AUTH；部分租户需开启基本身份验证例外。",
  },
  {
    id: "outlook",
    name: "Outlook.com / Hotmail",
    category: "国际邮箱",
    host: "smtp-mail.outlook.com",
    port: 587,
    security: "starttls",
    userHint: "Outlook 邮箱地址",
  },
  {
    id: "icloud",
    name: "Apple iCloud",
    category: "国际邮箱",
    host: "smtp.mail.me.com",
    port: 587,
    security: "starttls",
    userHint: "iCloud 邮箱",
    doc: "需生成应用专用密码。",
  },
  {
    id: "yahoo",
    name: "Yahoo Mail",
    category: "国际邮箱",
    host: "smtp.mail.yahoo.com",
    port: 465,
    security: "ssl",
    userHint: "Yahoo 邮箱",
    doc: "需使用应用密码。",
  },
  {
    id: "zoho",
    name: "Zoho Mail",
    category: "国际邮箱",
    host: "smtp.zoho.com",
    port: 465,
    security: "ssl",
    userHint: "Zoho 邮箱",
    doc: "企业版可用 smtppro.zoho.com。",
  },
  {
    id: "zoho_pro",
    name: "Zoho Mail (企业)",
    category: "国际邮箱",
    host: "smtppro.zoho.com",
    port: 465,
    security: "ssl",
    userHint: "Zoho 企业邮箱",
  },
  {
    id: "fastmail",
    name: "Fastmail",
    category: "国际邮箱",
    host: "smtp.fastmail.com",
    port: 465,
    security: "ssl",
    userHint: "Fastmail 账号",
  },
  {
    id: "proton",
    name: "Proton Mail (Bridge)",
    category: "国际邮箱",
    host: "127.0.0.1",
    port: 1025,
    security: "none",
    userHint: "Proton Bridge 本地账号",
    doc: "需在本机运行 Proton Mail Bridge。",
  },

  // --- 国际事务邮件 / ESP ---
  {
    id: "sendgrid",
    name: "SendGrid",
    category: "事务邮件 ESP",
    host: "smtp.sendgrid.net",
    port: 587,
    security: "starttls",
    userHint: "apikey",
    doc: "用户名固定为 apikey，密码为 SendGrid API Key。",
  },
  {
    id: "mailgun",
    name: "Mailgun",
    category: "事务邮件 ESP",
    host: "smtp.mailgun.org",
    port: 587,
    security: "starttls",
    userHint: "postmaster@your-domain",
    doc: "Mailgun 控制台 → Sending → SMTP credentials。",
  },
  {
    id: "ses_us_east_1",
    name: "Amazon SES (us-east-1)",
    category: "事务邮件 ESP",
    host: "email-smtp.us-east-1.amazonaws.com",
    port: 587,
    security: "starttls",
    userHint: "SMTP 用户名 (IAM)",
    doc: "AWS SES 控制台创建 SMTP 凭证；发件人需在 SES 验证。",
  },
  {
    id: "ses_ap_southeast_1",
    name: "Amazon SES (ap-southeast-1)",
    category: "事务邮件 ESP",
    host: "email-smtp.ap-southeast-1.amazonaws.com",
    port: 587,
    security: "starttls",
    userHint: "SMTP 用户名 (IAM)",
  },
  {
    id: "ses_eu_west_1",
    name: "Amazon SES (eu-west-1)",
    category: "事务邮件 ESP",
    host: "email-smtp.eu-west-1.amazonaws.com",
    port: 587,
    security: "starttls",
    userHint: "SMTP 用户名 (IAM)",
  },
  {
    id: "postmark",
    name: "Postmark",
    category: "事务邮件 ESP",
    host: "smtp.postmarkapp.com",
    port: 587,
    security: "starttls",
    userHint: "Server API Token",
  },
  {
    id: "sparkpost",
    name: "SparkPost",
    category: "事务邮件 ESP",
    host: "smtp.sparkpostmail.com",
    port: 587,
    security: "starttls",
    userHint: "SMTP 用户名",
  },
  {
    id: "mailjet",
    name: "Mailjet",
    category: "事务邮件 ESP",
    host: "in-v3.mailjet.com",
    port: 587,
    security: "starttls",
    userHint: "API Key",
    doc: "密码为 Mailjet Secret Key。",
  },
  {
    id: "brevo",
    name: "Brevo (Sendinblue)",
    category: "事务邮件 ESP",
    host: "smtp-relay.brevo.com",
    port: 587,
    security: "starttls",
    userHint: "登录邮箱",
    doc: "SMTP 密钥在 Brevo → SMTP & API 获取。",
  },
  {
    id: "mailchimp",
    name: "Mailchimp Transactional (Mandrill)",
    category: "事务邮件 ESP",
    host: "smtp.mandrillapp.com",
    port: 587,
    security: "starttls",
    userHint: "任意用户名",
    doc: "密码为 Mandrill API Key。",
  },
  {
    id: "custom",
    name: "自定义 / 其他",
    category: "其他",
    host: "",
    port: 587,
    security: "starttls",
    doc: "手动填写 SMTP 主机、端口与加密方式。",
  },
];

export const SMTP_CATEGORIES = [...new Set(SMTP_PRESETS.map((p) => p.category))];

export function getSmtpPreset(id: string | undefined): SmtpPreset | undefined {
  return SMTP_PRESETS.find((p) => p.id === id);
}

export function guessSmtpProvider(host: string, port: number): string {
  const h = host.trim().toLowerCase();
  const hit = SMTP_PRESETS.find(
    (p) => p.id !== "custom" && p.host.toLowerCase() === h && p.port === port,
  );
  if (hit) return hit.id;
  const hostOnly = SMTP_PRESETS.find((p) => p.id !== "custom" && p.host.toLowerCase() === h);
  return hostOnly?.id || "custom";
}

export const SMTP_SECURITY_OPTIONS = [
  { value: "starttls", label: "STARTTLS (推荐，端口 587)" },
  { value: "ssl", label: "SSL/TLS (端口 465)" },
  { value: "none", label: "无加密 (端口 25，内网)" },
];
