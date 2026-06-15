# Bugis · DCI / EVPN 专线开通与运营平台

> 开源的**多厂商**数据中心互联（DCI）与 EVPN 专线**开通 + 运营**一体化平台。
> 屏蔽华三 / 华为（BGP EVPN VXLAN）与 Juniper / Arista / Cisco（SR-MPLS EVPN）底层差异，
> 提供租户管理、设备管理、专线编排、工单流转、带宽 / SLA 监控等能力。

An open-source, **multi-vendor** platform for provisioning and operating
Data-Center-Interconnect (DCI) and EVPN dedicated lines. It abstracts the
differences between H3C/Huawei (BGP EVPN VXLAN) and Juniper/Arista/Cisco
(SR-MPLS EVPN) and offers tenant management, device inventory, circuit
orchestration, work-order workflow, and bandwidth/SLA telemetry.

---

## ✨ 功能特性 / Features

- **多厂商南向驱动** — 每个厂商一套 Jinja2 配置模板，统一意图模型驱动渲染
  - 华三 H3C (Comware7) · 华为 Huawei (VRP/Datacom) → **BGP EVPN VXLAN** (NETCONF)
  - Juniper (Junos) · Arista (EOS) · Cisco (IOS-XR) → **SR-MPLS EVPN** (NETCONF / CLI)
  - FRRouting (SONiC + FRR 白盒/开源) → **BGP EVPN VXLAN** (vtysh / CLI)
- **专线业务编排** — L2VPN(E-LAN/E-LINE)、L3VPN(IRB/Type-5)、EVPN-VPWS、**DCI 数据中心互联**
- **工单流转** — `draft → submitted → approved → running → completed/failed`，全程审计事件
- **资源自动分配** — VNI / VLAN / RD / RT / VRF / 专线编码自动编排，避免冲突
- **多租户 / 混合云接入** — 企业专线、混合云、公有云接入等租户类型
- **设备与站点管理** — 数据中心(DC)、设备角色(spine/leaf/border/pe/rr/dci-gw)、接口资源
- **遥测与 SLA 可视化** — 健康评分、流量 / 时延 / 抖动 / 丢包曲线，Prometheus `/metrics`
- **告警中心** — SLA / 容量 / 隧道状态阈值检测，告警去重 / 确认 / 清除，顶栏实时徽标
- **容量管理与拓扑** — 数据中心 / 设备 / 链路带宽分配率，SVG 网络拓扑可视化
- **带宽变更** — MODIFY 工单一键调整带宽并重新下发各厂商 QoS
- **北向自动化** — StackStorm 风格 Webhook 一键开通；**Ansible** inventory/playbook 导出（厂商官方 Collection）
- **控制器北向适配** — 站点可托管给 SDN/厂商控制器（华为 NCE-Fabric / 华三 SeerEngine / OpenDaylight / ONOS），开通时下发 JSON 意图到控制器北向 RESTful
- **实时推送 (SSE)** 与 **CSV 批量导入导出**（设备 / 专线）
- **操作审计** — 全量写操作审计日志（操作人 / 路径 / 状态 / 来源 IP）
- **Dry-run 安全模式** — 默认仅渲染配置不下发，无需实验设备即可端到端演示
- **现代化运营门户** — React + Ant Design 大屏与管理界面

## 🏗️ 架构 / Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  前端运营门户  Frontend (React + Vite + Ant Design)            │
│  仪表盘 / 租户 / 设备 / 专线 / 工单 / 监控大屏                   │
└───────────────────────────┬──────────────────────────────────┘
                            │  北向 REST API (JSON / JWT)
┌───────────────────────────▼──────────────────────────────────┐
│  业务编排层  Orchestration (FastAPI)                           │
│  • 工单流转引擎  • 资源分配(VNI/RD/RT)  • DCI 网关编排           │
│  • 多租户 / 设备 / 专线 模型 (SQLAlchemy)                       │
└───────────────────────────┬──────────────────────────────────┘
                            │  统一意图 (Intent)
┌───────────────────────────▼──────────────────────────────────┐
│  南向驱动层  Southbound Drivers                                │
│  Jinja2 模板渲染 →  NETCONF / CLI 下发 (dry-run 可选)           │
│  H3C │ Huawei │ Juniper │ Arista │ Cisco                       │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
                  物理 / 虚拟网络设备 (EVPN VXLAN / SR-MPLS)
```

详见 [`docs/architecture.md`](docs/architecture.md)。

## 🚀 快速开始 / Quick start

### 方式一：本地运行 (SQLite, 零配置)

后端 Backend：

```bash
cd backend
pip install -r requirements.txt
python -m scripts.seed          # 初始化演示数据（账号 admin / admin123）
uvicorn app.main:app --reload   # API: http://localhost:8000  文档: /docs
```

前端 Frontend：

```bash
cd frontend
npm install
npm run dev                     # 门户: http://localhost:5173 (代理到后端 8000)
```

### 方式二：Docker Compose (含 PostgreSQL / Prometheus / Grafana)

```bash
docker compose up --build
# 门户:        http://localhost:8080
# 后端 API:    http://localhost:8000/docs
# Prometheus:  http://localhost:9090
# Grafana:     http://localhost:3000 (admin/admin)
```

默认登录：`admin` / `admin123`

**可观测性开箱即用**：Prometheus 自动抓取后端 `/metrics` 并加载告警规则（`deploy/prometheus/alerts.yml`）；Grafana 自动装载数据源与「Bugis · DCI/EVPN 运营总览」仪表盘（`deploy/grafana/provisioning/`）。指标包含 `bugis_circuits_by_status`、`bugis_devices_by_vendor`、`bugis_alarms_by_severity` 等带标签时序。

## 🔌 主要 API / Key endpoints

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 登录获取 JWT |
| CRUD | `/api/v1/sites` `/tenants` `/devices` `/circuits` | 资源管理 |
| POST | `/api/v1/work-orders/provision/{circuit_id}` | 一键开通（建单→审批→执行） |
| GET  | `/api/v1/work-orders/{id}/preview` | 多厂商配置预览（dry-run 渲染） |
| GET  | `/api/v1/work-orders/{id}/ansible` | 导出 Ansible inventory + playbook |
| POST | `/api/v1/integrations/webhook/provision` | 北向 Webhook 一键开通（`X-Webhook-Token`） |
| GET  | `/api/v1/integrations/ansible/inventory` | 全量 Ansible inventory |
| POST | `/api/v1/telemetry/simulate` | 生成模拟遥测采样（并评估告警） |
| GET  | `/api/v1/telemetry/circuits/{id}/health` | 专线 SLA 健康评分 |
| GET  | `/api/v1/telemetry/dashboard` | 运营大屏聚合 KPI |
| GET/POST | `/api/v1/alarms` `/alarms/evaluate` `/alarms/{id}/ack` | 告警中心 |
| GET  | `/api/v1/capacity/sites` `/capacity/links/usage` `/capacity/topology` | 容量与拓扑 |
| GET  | `/api/v1/audit` | 操作审计日志 |
| GET  | `/metrics` | Prometheus 指标 |

## ⚙️ 配置 / Configuration

环境变量均以 `BUGIS_` 前缀，见 [`backend/.env.example`](backend/.env.example)。
关键项：

- `BUGIS_DATABASE_URL` — 数据库连接串（默认 SQLite）
- `BUGIS_DRY_RUN` — 默认 `false`（生产模式，真实 NETCONF/SSH 下发）；设为 `true` 则仅渲染预览
- `BUGIS_SECRET_KEY` — JWT 签名密钥（生产务必修改）
- `BUGIS_WEBHOOK_TOKEN` — 北向 Webhook 共享令牌（StackStorm/ITSM 对接）
- `BUGIS_THRESHOLD_*` — 告警阈值（丢包 / 时延 / 利用率 / 健康分）

## 🗄️ 数据库迁移 / Migrations

生产环境使用 Alembic 进行版本化表结构迁移（本地 SQLite 开发仍可用启动时 `create_all` 便捷建表）：

```bash
cd backend
alembic upgrade head                              # 应用最新迁移
alembic revision --autogenerate -m "描述变更"     # 模型变更后生成新迁移
```

## 🧪 测试 / Tests

```bash
cd backend && python -m pytest -q
```

## 📐 业界落地参考 / Reference

平台设计参考了开源 SDN/编排生态，可与之集成或演进：

- **业务编排 / 北向自动化**：StackStorm（事件驱动）、Ansible（`h3c.comware` / `huawei.datacom` Collection）
- **南向控制器**：OpenDaylight (NETCONF / BGPCEP)、ONOS、FRRouting (RR / VTEP)
- **遥测可视化**：SNMP Exporter / Telegraf + Prometheus + Grafana
- **云网底座**：OpenStack Neutron (ML2/OVN) + FRR EVPN-VXLAN，对接华三/华为硬件网关
- **厂商开放 API**：华为 iMaster NCE-Fabric、华三 AD-DC SeerEngine 的 RESTful (Restconf/Netconf)

本平台的南向驱动层即为对接上述控制器 / 设备的抽象点。

## 🚀 Demo 环境自动部署

公开 Demo：`http://203.117.117.196:3300/`（账号 `admin` / `admin123`）

Demo 栈与生产 Compose 对齐，使用 **PostgreSQL 16**（非 SQLite），并附带 **Prometheus / Grafana** 可观测性组件：

| 服务 | 地址 |
|------|------|
| 门户 | `http://<host>:3300/` |
| Prometheus | `http://<host>:3309/` |
| Grafana | `http://<host>:3303/`（默认 `admin` / 见 `GRAFANA_ADMIN_PASSWORD`） |

每次合并到 `main` 后，可通过 GitHub Actions 自动同步 Demo（需在仓库 Secrets 配置）：

| Secret | 说明 |
|--------|------|
| `DEMO_SSH_PASSWORD` | **必填**，远程 SSH 密码 |
| `DEMO_SSH_HOST` | 默认 `203.117.117.196` |
| `DEMO_SSH_PORT` | 默认 `2333` |
| `DEMO_SSH_USER` | 默认 `root` |
| `DEMO_REMOTE_DIR` | 默认 `/root/bugis` |
| `POSTGRES_PASSWORD` | 可选，Demo 库密码（未设则用脚本默认值） |
| `BUGIS_SECRET_KEY` | 可选，JWT 签名密钥 |
| `GRAFANA_ADMIN_PASSWORD` | 可选，Grafana 管理员密码 |

本地手动部署：

```bash
cp deploy/demo.env.example deploy/demo.env   # 填入 SSH 密码与栈密钥，勿提交
source deploy/demo.env
./scripts/deploy-demo.sh
```

本地仅启动 Demo 栈（无需 SSH）：

```bash
docker compose -f docker-compose.demo.yml --env-file deploy/demo.env up --build
```

从旧版 SQLite Demo 升级时，数据需重新 seed（`pgdata` 卷持久化 PostgreSQL）；旧 `bugis_data` 卷可手动删除。

Workflow 文件：`.github/workflows/demo-deploy.yml`（push `main` 或手动触发）。

## ⚠️ 说明

- 默认 **生产模式**（`BUGIS_DRY_RUN=false`），配置会通过 NETCONF/SSH 真实下发；开发/演示可设为 dry-run。
- 模板为生产可参考的范式，实际部署请结合现网命名规范、地址规划与安全基线校验。

## 📄 License

Apache-2.0
