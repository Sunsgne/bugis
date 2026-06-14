# 架构设计 / Architecture

本文档描述 Bugis 平台的分层架构、核心数据模型与专线开通流程。

## 1. 分层架构

平台采用经典的"北向编排 + 南向驱动"分层，对应业界 DCI/EVPN 运营平台的演进路线。

| 层 | 组件 | 职责 |
|---|---|---|
| 表现层 | React + Ant Design 门户 | 运营大屏、资源管理、工单、监控 |
| 北向 API | FastAPI REST (`/api/v1`) | 鉴权、资源 CRUD、工单驱动 |
| 编排层 | `services/orchestrator.py` | 工单生命周期、资源分配、DCI 网关编排 |
| 模型层 | SQLAlchemy models | 多租户 / 设备 / 专线 / 工单 / 遥测 |
| 南向驱动 | `drivers/` + `templates/` | 意图 → 厂商配置渲染 → NETCONF/CLI 下发 |
| 遥测 | `services/telemetry_service.py` + `/metrics` | SLA 健康、流量采样、Prometheus |

## 2. 多厂商抽象

南向驱动通过**统一意图模型**（circuit + endpoint + device + site）驱动 Jinja2 模板渲染，
将各厂商命令行/配置差异收敛到模板文件中：

```
backend/app/templates/
├── _generic/          # 兜底模板（厂商模板缺失时使用）
├── h3c/               # Comware7  - BGP EVPN VXLAN
├── huawei/            # VRP       - BGP EVPN VXLAN
├── juniper/           # Junos     - SR-MPLS EVPN
├── arista/            # EOS       - SR-MPLS EVPN
└── cisco/             # IOS-XR    - SR-MPLS EVPN
```

每个厂商目录包含 `{service_type}_{operation}.j2`，其中：

- `service_type ∈ {l2vpn_evpn, l3vpn_evpn, evpn_vpws, dci}`
- `operation ∈ {apply, remove}`

驱动注册表 `drivers/registry.py` 将 `Vendor → Driver` 映射，并声明各厂商默认传输方式
（NETCONF / CLI）与所属 Overlay 技术（VXLAN-EVPN / SR-MPLS-EVPN）。

### Dry-run 与真实下发

`BaseDriver.push()` 默认 dry-run，仅返回渲染结果；当 `BUGIS_DRY_RUN=false` 时：

- NETCONF 设备通过 `ncclient` 下发（华三/华为/Cisco/Juniper）
- CLI 设备通过 `netmiko` 下发（Arista 等）

两个库为**可选依赖**，未安装时自动回退到 dry-run。

## 3. 核心数据模型

```
Site (数据中心)──< Device (设备) ──< DeviceInterface (接口)
                       │
Tenant (租户) ──< Circuit (专线) ──< CircuitEndpoint (端点) >── Device
                       │
                       └─< WorkOrder (工单) ──< WorkOrderEvent (事件)
                                  │
                                  └─< ConfigJob (配置作业) >── Device
Circuit / Device ──< TelemetrySample (遥测采样)
```

- **Circuit** 持有 EVPN 标识（VNI / VLAN / RD / RT / VRF / ESI）、带宽、MTU、SLA。
- **WorkOrder** 编排一次生命周期变更，产生若干 **ConfigJob**（每设备一个）。
- **ConfigJob** 保存渲染配置 `rendered_config` 与回滚配置 `rollback_config`。

## 4. 专线开通流程

```
创建专线(草稿)
   │  自动分配 VNI/VLAN/RD/RT/VRF
   ▼
创建工单 WorkOrder ── submit ──► 审批 approve ──► 执行 execute
                                                    │
                  ┌─────────────────────────────────┤
                  ▼                                 ▼
        对每个接入端点设备                   对站点 DCI/Border 网关
        渲染 service_type 配置               渲染 DCI 配置
                  │                                 │
                  └──────────────┬──────────────────┘
                                 ▼
                  ConfigJob 渲染 + (dry-run) 下发
                                 │
              全部成功 → 专线 active / 工单 completed
              任一失败 → 专线 failed / 工单 failed
```

一键开通接口 `POST /work-orders/provision/{circuit_id}` 将
create → submit → approve → execute 串联完成，便于演示与自动化对接。

## 5. DCI 数据中心互联

当专线类型为 `dci`，或开通过程中识别到端点设备所在站点存在
`dci_gw` / `border_leaf` 角色设备时，编排引擎会额外为这些网关渲染 DCI 模板，
实现跨 Fabric 的 EVPN 路由再发起 / 缝合（route re-origination / stitching）。

## 6. 遥测与 SLA

- `TelemetrySample` 记录 Rx/Tx、利用率、时延、抖动、丢包、隧道状态。
- `compute_health()` 基于丢包/时延/抖动/峰值利用率计算 0–100 健康评分。
- `/telemetry/simulate` 为活跃专线生成模拟采样，便于无真实采集器时演示大屏。
- `/metrics` 暴露 Prometheus 指标，可被 Prometheus 抓取并在 Grafana 展示。

## 7. 与开源生态集成

| 能力 | 可集成组件 |
|---|---|
| 事件驱动编排 | StackStorm（Webhook 接收工单指令触发开通） |
| 配置自动化 | Ansible（`h3c.comware` / `huawei.datacom` Collection） |
| SDN 控制器 | OpenDaylight (NETCONF/BGPCEP)、ONOS、FRRouting |
| 厂商控制器北向 | 华为 iMaster NCE-Fabric、华三 AD-DC SeerEngine (Restconf) |
| 监控可视化 | SNMP Exporter / Telegraf + Prometheus + Grafana |

南向驱动层是这些集成的统一接入点：可在 `drivers/` 中新增一个"控制器驱动"，
将渲染后的意图转发给上述控制器的 RESTful/NETCONF 北向接口，而非直连设备。
