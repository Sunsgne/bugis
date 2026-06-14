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
- **专线业务编排** — L2VPN(E-LAN/E-LINE)、L3VPN(IRB/Type-5)、EVPN-VPWS、**DCI 数据中心互联**
- **工单流转** — `draft → submitted → approved → running → completed/failed`，全程审计事件
- **资源自动分配** — VNI / VLAN / RD / RT / VRF / 专线编码自动编排，避免冲突
- **多租户 / 混合云接入** — 企业专线、混合云、公有云接入等租户类型
- **设备与站点管理** — 数据中心(DC)、设备角色(spine/leaf/border/pe/rr/dci-gw)、接口资源
- **遥测与 SLA 可视化** — 健康评分、流量 / 时延 / 抖动 / 丢包曲线，Prometheus `/metrics`
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

## 🔌 主要 API / Key endpoints

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 登录获取 JWT |
| CRUD | `/api/v1/sites` `/tenants` `/devices` `/circuits` | 资源管理 |
| POST | `/api/v1/work-orders/provision/{circuit_id}` | 一键开通（建单→审批→执行） |
| GET  | `/api/v1/work-orders/{id}/preview` | 多厂商配置预览（dry-run 渲染） |
| POST | `/api/v1/telemetry/simulate` | 生成模拟遥测采样 |
| GET  | `/api/v1/telemetry/circuits/{id}/health` | 专线 SLA 健康评分 |
| GET  | `/api/v1/telemetry/dashboard` | 运营大屏聚合 KPI |
| GET  | `/metrics` | Prometheus 指标 |

## ⚙️ 配置 / Configuration

环境变量均以 `BUGIS_` 前缀，见 [`backend/.env.example`](backend/.env.example)。
关键项：

- `BUGIS_DATABASE_URL` — 数据库连接串（默认 SQLite）
- `BUGIS_DRY_RUN` — `true` 仅渲染配置不下发；`false` 真实下发（需安装 `ncclient` / `netmiko`）
- `BUGIS_SECRET_KEY` — JWT 签名密钥（生产务必修改）

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

## ⚠️ 说明

- 默认 **dry-run** 模式，渲染的厂商配置仅用于审阅，不会下发到真实设备。
- 模板为生产可参考的范式，实际部署请结合现网命名规范、地址规划与安全基线校验。

## 📄 License

Apache-2.0
