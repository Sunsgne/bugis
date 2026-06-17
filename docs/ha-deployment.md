# Bugis 高可用（HA）部署指南

本文说明生产环境多节点部署方案、服务器规格建议，以及如何使用仓库内脚本一键下发。

## 架构概览

```
                    [负载均衡 LB]
                    nginx / 云 LB
                   /             \
          [App-1]                   [App-2]
    scheduler ON + migrate      scheduler OFF
    frontend:3300               frontend:3300
           \                         /
            \                       /
             [PostgreSQL 主库]
                  (可选从库)
```

- **无状态层**：多台 App 节点共享同一 PostgreSQL，JWT 密钥 `BUGIS_SECRET_KEY` 必须一致。
- **有状态层**：PostgreSQL 为唯一写入点；后台调度器（SNMP 采集、拨测、告警评估）**仅在第一台 App 节点运行**。
- **入口**：用户只访问 LB 的 80/443；LB 使用 `ip_hash` 保持 SSE 长连接粘性。

## 需要几台服务器？

### 方案 A — 最小高可用（4 台）

适合中小规模生产、可接受数据库单点（靠备份恢复）。

| 角色 | 数量 | 最低规格 | 说明 |
|------|------|----------|------|
| 负载均衡 LB | 1 | 2 vCPU / 4 GB / 40 GB | nginx 反向代理 |
| 应用 App | 2 | 4 vCPU / 16 GB / 100 GB SSD | Docker：backend + frontend |
| 数据库 DB | 1 | 4 vCPU / 16 GB / 200 GB SSD | PostgreSQL 17 |

**合计：4 台**

### 方案 B — 推荐生产（6 台）

应用与数据库均冗余，可手工切换 DB 从库。

| 角色 | 数量 | 推荐规格 | 说明 |
|------|------|----------|------|
| LB | 2 | 2 vCPU / 4 GB | keepalived VIP 或云负载均衡 |
| App | 2 | 8 vCPU / 16 GB / 100 GB SSD | 见方案 A |
| DB 主 + 从 | 2 | 8 vCPU / 32 GB / 500 GB SSD | 流复制，手动 failover |
| 可观测（可选） | 1 | 2 vCPU / 4 GB | Prometheus + Grafana，可与 LB 合并 |

**合计：6 台（可观测合并则 5 台）**

### 方案 C — 企业级（8 台+）

- 云厂商托管 PostgreSQL（RDS / PolarDB）替代自建 DB 集群
- 或 Patroni + etcd 三节点自动故障转移
- 独立可观测与跳板机

## 规格选型说明

| 维度 | 建议 |
|------|------|
| CPU | App 节点承担 SNMP 轮询、配置渲染、编排下发，建议 ≥4 核；DB ≥4 核 |
| 内存 | App 16 GB 起；设备数量 >200 台时考虑 32 GB |
| 磁盘 | DB 必须用 SSD；App 100 GB 起（镜像 + 日志） |
| 网络 | 节点间内网互通；App→设备 NETCONF/SSH/SNMP 需可达 |
| OS | Ubuntu 22.04/24.04 LTS 或 RHEL 8+，内核 5.x |

## 端口与安全暴露

默认原则：**仅前端（或 LB）对外**；后端 API、数据库、可观测组件不直接对公网映射端口。

| 节点 | 对外端口 | 内网端口 | 说明 |
|------|----------|----------|------|
| LB | 80, 443 | — | 唯一公网入口，反代到 App frontend |
| App | — | 3300 | frontend，供 LB 回源 |
| App | — | 8000 | backend `/metrics`，绑定 `HA_APP_METRICS_BIND`（默认 127.0.0.1；多节点设为私网 IP 并由防火墙限制） |
| DB | — | 5432 | PostgreSQL，绑定 `HA_DB_BIND`（默认 127.0.0.1；App 跨机访问时设为私网 IP + 防火墙） |
| Obs | — | 127.0.0.1:9090 / :3000 | Prometheus / Grafana 仅本机回环，通过 SSH 隧道访问 |

API 经前端 Nginx 反代 `/api/`；`/docs`、`/metrics` 默认不对外暴露。

## 部署前准备

每台机器安装：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
docker compose version   # 需 v2.20+
```

控制机（你本地或跳板机）需要：

- `ssh` / `scp`
- `curl`, `python3`
- 可选 `sshpass`（若使用密码登录）

## 快速开始

### 1. 生成清单

交互式填写服务器 IP：

```bash
./scripts/ha/generate-inventory.sh
```

或手工复制模板：

```bash
cp deploy/ha/inventory.env.example deploy/ha/inventory.env
vim deploy/ha/inventory.env
```

### 2. 填写清单（发给我即可代部署）

把以下信息整理好发给我：

```ini
# SSH
HA_SSH_USER=root
HA_SSH_PORT=22

# 数据库
HA_DB_HOST=10.0.0.20
POSTGRES_PASSWORD=***

# 应用（第一台为调度主节点）
HA_APP_HOSTS=10.0.0.10,10.0.0.11

# 负载均衡
HA_LB_HOSTS=10.0.0.1
HA_PUBLIC_URL=bugis.yourcompany.com

# 密钥（所有 App 相同）
BUGIS_SECRET_KEY=***

# 可选
HA_OBS_HOST=10.0.0.30
HA_DB_STANDBY_HOST=10.0.0.21
```

### 3. 一键部署

```bash
source deploy/ha/inventory.env
./scripts/ha/deploy-ha.sh
```

### 4. 验证

```bash
./scripts/ha/verify-ha.sh
```

## 清单变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `HA_DB_HOST` | 是 | PostgreSQL 主库 IP |
| `HA_APP_HOSTS` | 是 | 逗号分隔，**第一台**跑调度器与迁移 |
| `HA_LB_HOSTS` | 是 | LB 节点 IP |
| `BUGIS_SECRET_KEY` | 是 | JWT 密钥，所有 App 一致 |
| `POSTGRES_PASSWORD` | 是 | 数据库密码 |
| `HA_OBS_HOST` | 否 | 监控节点 |
| `HA_DB_STANDBY_HOST` | 否 | 从库 IP（需手工配置流复制） |
| `BUGIS_RUN_DEMO` | 否 | 生产建议 `false` |

## 多节点行为说明

| 组件 | 节点 1（Leader） | 节点 2+（Follower） |
|------|------------------|---------------------|
| `BUGIS_SCHEDULER_ENABLED` | `true` | `false` |
| `BUGIS_RUN_MIGRATIONS` | `true` | `false` |
| `BUGIS_RUN_SEED` | 首次 `true` | `false` |
| API 请求 | 均可处理 | 均可处理 |

## 数据库高可用（可选）

脚本默认只部署 **单主库**。从库流复制步骤：

1. 在主库创建复制用户与 `pg_hba.conf` 放行从库 IP
2. 从库执行 `pg_basebackup` 拉取基线
3. 故障时手工 `pg_promote` 并修改 `inventory.env` 中 `HA_DB_HOST`

生产更推荐使用云厂商 **托管 PostgreSQL**（自动备份、主从切换）。

## TLS / 域名

1. 将域名解析到 LB 公网 IP
2. 在 LB 节点用 certbot 或上传证书
3. 取消 `deploy/ha/lb/nginx.conf.template` 中 443 server 注释

## 与单机 demo 的区别

| 项目 | demo (`deploy-demo.sh`) | HA (`deploy-ha.sh`) |
|------|-------------------------|---------------------|
| 机器数 | 1 | 4+ |
| 数据库 | 容器内 PostgreSQL | 独立 DB 节点 |
| 调度器 | 单实例 | 仅 Leader App |
| 入口 | :3300 直连 | LB :80/443 |
| 种子数据 | 每次可重置 demo | 生产关闭 `BUGIS_RUN_DEMO` |

## 故障排查

```bash
# App 节点日志
ssh root@<app-ip> 'cd /opt/bugis && docker compose -f docker-compose.ha-app.yml logs --tail=100 backend'

# LB 配置测试
ssh root@<lb-ip> 'docker exec bugis-ha-lb nginx -t'

# DB 连接
psql "postgresql://bugis:***@<db-ip>:5432/bugis" -c 'select 1'
```

## 文件索引

| 文件 | 用途 |
|------|------|
| `deploy/ha/inventory.env.example` | 清单模板 |
| `scripts/ha/generate-inventory.sh` | 交互生成清单 |
| `scripts/ha/deploy-ha.sh` | 总控部署 |
| `docker-compose.ha-app.yml` | App 节点栈 |
| `docker-compose.ha-db.yml` | DB 节点栈 |
| `docker-compose.ha-obs.yml` | 监控栈 |
| `deploy/ha/lb/nginx.conf.template` | LB 配置模板 |

---

准备好服务器信息后，把填好的 `inventory.env` 或上表字段发给我，我可以远程执行 `deploy-ha.sh` 完成部署。
