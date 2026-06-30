# Arc 投产部署 Runbook (B 类阻断修复)

> 适用: 云托管 k8s (EKS/ACK/GKE) + 云托管 DB/Redis + kube-prometheus-stack 监控。
> 对应 `docs/versions/v6.19.0-current.md` 续13 投产门禁。A1/A2/B5/B6/B7 已在代码/manifest 落地, B1/B2/B3/B4 为部署侧配置。

## 前置 helm 依赖

```bash
# B7: cert-manager (ingress TLS)
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true
# 替换 cert-manager-issuer.yml 中 email 后: kubectl apply -f k8s/cert-manager-issuer.yml

# B2: kube-prometheus-stack (Prometheus + Alertmanager + Grafana)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prom-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# B3: external-secrets (Secret 管理)
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```

## B1 数据库 (云托管 PG, P0 备份)

生产用云托管 PG (AWS RDS / 阿里云 RDS / Cloud SQL), 内置自动备份 + PITR:
- `ARC_DATABASE_URL` 指向云 RDS 实例 (k8s Secret `arc-secrets`)
- 备份/恢复由云厂商负责: 配置保留期 + PITR 窗口 (通常 RPO<5min, RTO<1h)
- `k8s/db.yml` (StatefulSet PG) **仅开发自管, 生产不部署**
- BaaS `ARC_SUPABASE_DB_URL` 同理指向云 Supabase/PG

## B2 监控告警 (P0 闭环)

```bash
kubectl apply -f k8s/monitoring/prometheusrule.yml
```

`/metrics` 抓取带 A2 bearer token (`ARC_PROMETHEUS_TOKEN`):
1. Secret `arc-secrets` 加 `prometheus-token: <base64(ARC_PROMETHEUS_TOKEN)>`
2. backend Service port 加 `name: http` (若未设)
3. apply 下方 ServiceMonitor:

```yaml
# k8s/monitoring/servicemonitor.yml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: arc-backend
  namespace: arc
  labels:
    prometheus: kube-prometheus-stack-prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: arc-backend
  endpoints:
    - port: http
      path: /metrics
      bearerTokenSecret:
        name: arc-secrets
        key: prometheus-token
```

告警通知: kube-prometheus-stack Alertmanager helm values 配 slack/email/webhook。

## B3 Secret 加密 (External Secrets)

云 Secret Manager (AWS Secrets Manager / 阿里云 KMS / GCP Secret Manager):

```yaml
# k8s/external-secret.yml (参数化云厂商)
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: arc-cloud-secrets
  namespace: arc
spec:
  provider: {}  # aws/alicloud/gcp 按云厂商填
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: arc-secrets
  namespace: arc
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: arc-cloud-secrets
    kind: SecretStore
  target:
    name: arc-secrets
  data:
    - secretKey: jwt_secret
      remoteRef:
        key: arc/jwt-secret  # 云 Secret Manager 中的 key
    # ... 其余 ARC_* secret 同理映射
```

替代方案: sealed-secrets (git 提交加密 secret, 无需云服务)。轮换: 云 Secret Manager 轮换 + ExternalSecret `refreshInterval` 同步。

## B4 Redis (云托管, P1 持久化)

生产用云托管 Redis (ElastiCache / 阿里云 Redis):
- `ARC_REDIS_URL` 指向云 Redis (k8s Secret `arc-secrets`)
- 云 Redis 自带持久化 + 高可用 (解决 emptyDir 易失)
- `k8s/redis.yml` (emptyDir) **仅开发自管, 生产不部署**
- B5 限流自动切 Redis (`redis_url` 非空时共享计数, 多副本生效)

## 已落地 (代码/manifest)

| 阻断 | 落地 | 位置 |
|------|------|------|
| A1 | 默认 admin 越权修复 | entity/service/route + migration z22 |
| A2 | /metrics bearer token | main.py /metrics + ARC_PROMETHEUS_TOKEN |
| B5 | 限流切 Redis 后端 | rate_limit.py (redis_url 非空时) |
| B6 | pod graceful | backend.yml grace 60s + preStop |
| B7 | ingress TLS | ingress.yml + cert-manager-issuer.yml |

## 投产 checklist

- [ ] A1: 首用户特例可用 + admin 提权 API (`PATCH /api/users/{id}/role`)
- [ ] A2: `ARC_PROMETHEUS_TOKEN` 配置 + scraper 带 Bearer
- [ ] B1: `ARC_DATABASE_URL` 指向云 RDS + 备份策略确认
- [ ] B2: kube-prometheus-stack 部署 + prometheusrule/servicemonitor apply + Alertmanager 通知
- [ ] B3: External Secrets 对接云 Secret Manager + 轮换流程
- [ ] B4: `ARC_REDIS_URL` 指向云 Redis (持久化)
- [ ] B5: `ARC_REDIS_URL` 非空 (限流多副本共享)
- [ ] B6: backend.yml grace 生效
- [ ] B7: ingress 域名替换 (`arc.example.com` → 真实) + TLS 证书签发
