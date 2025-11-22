# Product Requirements Document: Horizontal Scaling & High Availability

**Version:** 1.0  
**Status:** Planning (Future Sprint)  
**Sprint Name:** Sprint 12 "The Expandables" - *Expanding across the infrastructure*  
**Target Release:** 0.12.0  
**Author:** GitHub Copilot (Claude Sonnet 4.5)  
**Date:** November 21, 2025  
**Priority:** MEDIUM - Operational Excellence  
**Dependencies:** Sprint 9 (NATS) + Sprint 10 (Multi-platform) + Sprint 11 (Sandboxing) MUST be complete  

---

## Executive Summary

Sprint 12 "The Expandables" delivers **horizontal scaling** - running multiple bot instances across machines for high availability, load distribution, and fault tolerance. With NATS-first architecture (Sprint 9), multi-platform adapters (Sprint 10), and plugin isolation (Sprint 11), we can now scale Rosey across a cluster.

**The Opportunity**: Single bot instance is a single point of failure and limited by one machine's resources. Sprint 12 enables **distributed deployment** across multiple machines.

**The Solution**:
1. **Shared NATS Cluster**: Multiple bot instances connect to same NATS cluster
2. **Shared Database Service**: Single database service handles all instances
3. **Load Balancing**: Platform adapters distribute across instances
4. **Leader Election**: Coordinate singleton tasks (scheduled jobs, etc.)
5. **State Management**: Distributed state via NATS, no local state
6. **Health Monitoring**: Cluster-wide health and failover

**Key Achievement Goal**: Run 5+ bot instances across 3+ machines with automatic failover, zero downtime deployments, and linear scaling.

**Movie Connection**: *The Expandables* - expanding the team (instances) to handle bigger missions (traffic). More instances = more capability. (Yes, this is the terrible knockoff movie, which is perfect for expanding cheaply!)

---

## 1. Goals

### Primary Goals

- **PG-001**: **NATS Clustering** - Multi-node NATS cluster with high availability
- **PG-002**: **Multiple Bot Instances** - 3+ bot instances running simultaneously
- **PG-003**: **Load Balancing** - Distribute platform connections across instances
- **PG-004**: **Shared Database** - Single database service serves all instances
- **PG-005**: **Leader Election** - Coordinate singleton tasks (one leader at a time)
- **PG-006**: **Zero Downtime Deployment** - Rolling updates without service interruption
- **PG-007**: **Auto-Scaling** - Scale instances based on load (Kubernetes HPA)
- **PG-008**: **Monitoring & Observability** - Cluster-wide metrics and dashboards

### Success Metrics

| Metric | Target |
|--------|--------|
| Instance Count | 5+ instances running |
| Failover Time | <10 seconds (leader re-election) |
| Uptime | 99.9% (allow for rolling updates) |
| Message Throughput | Linear scaling (2x instances = 2x throughput) |
| Zero Downtime Deployments | 100% success rate |
| Cross-Instance Latency | <50ms p95 |

---

## 2. High-Level Architecture

### Cluster Topology

```text
┌──────────────────────────────────────────────────────────┐
│                    NATS Cluster                          │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐        │
│   │  NATS   │ ←──→ │  NATS   │ ←──→ │  NATS   │        │
│   │ Server  │      │ Server  │      │ Server  │        │
│   │ Node 1  │      │ Node 2  │      │ Node 3  │        │
│   └─────────┘      └─────────┘      └─────────┘        │
└──────────────────────────────────────────────────────────┘
         ↑                  ↑                  ↑
         │                  │                  │
    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
    │ Machine │        │ Machine │        │ Machine │
    │    1    │        │    2    │        │    3    │
    ├─────────┤        ├─────────┤        ├─────────┤
    │ Bot     │        │ Bot     │        │ Bot     │
    │Instance │        │Instance │        │Instance │
    │   #1    │        │   #2    │        │   #3    │
    ├─────────┤        ├─────────┤        ├─────────┤
    │ Bot     │        │ Bot     │        │ Bot     │
    │Instance │        │Instance │        │Instance │
    │   #4    │        │   #5    │        │   #6    │
    ├─────────┤        ├─────────┤        ├─────────┤
    │Plugins  │        │Plugins  │        │Plugins  │
    │ (2-3)   │        │ (2-3)   │        │ (2-3)   │
    └─────────┘        └─────────┘        └─────────┘
         ↓                  ↓                  ↓
    ┌─────────────────────────────────────────────┐
    │         Shared Database Service             │
    │              (Single Instance)              │
    └─────────────────────────────────────────────┘
```

### Load Distribution Strategies

**Strategy 1: Platform Sharding**
- Each bot instance handles specific platforms
- Instance 1: CyTube
- Instance 2: Discord
- Instance 3: Slack
- Pros: Simple, clear boundaries
- Cons: Uneven load if one platform is busier

**Strategy 2: Channel Sharding**
- Each instance handles subset of channels
- Instance 1: CyTube channel A, Discord guild 1
- Instance 2: CyTube channel B, Discord guild 2
- Instance 3: Slack workspace 1
- Pros: Better load distribution
- Cons: More complex configuration

**Strategy 3: Dynamic Load Balancing**
- NATS queue groups automatically distribute
- All instances subscribe to same subjects with queue group
- NATS distributes messages round-robin
- Pros: Automatic, adaptive
- Cons: Requires stateless handlers

### Leader Election

**Use Cases for Leader**:
- Scheduled tasks (run once, not on every instance)
- Database migrations
- Singleton operations (e.g., periodic cleanup)

**Implementation**: NATS JetStream K/V for leader election
```python
# Leader election using NATS K/V
async def elect_leader(nats_client):
    kv = await nats_client.key_value(bucket="rosey_cluster")
    
    # Try to acquire leader lock
    try:
        await kv.create(key="leader", value=instance_id, ttl=30)
        return True  # We are leader
    except KeyError:
        return False  # Someone else is leader
    
    # Leader must refresh lock every 20 seconds
    # If leader crashes, lock expires after 30 seconds
```

---

## 3. Deployment Models

### Model 1: Docker Compose (Development)
```yaml
version: '3.8'
services:
  nats-1:
    image: nats:latest
    command: "-cluster nats://0.0.0.0:6222"
  
  nats-2:
    image: nats:latest
    command: "-cluster nats://0.0.0.0:6222 -routes nats://nats-1:6222"
  
  database:
    build: ./database
    environment:
      NATS_URL: nats://nats-1:4222
  
  bot-1:
    build: ./bot
    environment:
      INSTANCE_ID: bot-1
      NATS_URL: nats://nats-1:4222,nats://nats-2:4222
  
  bot-2:
    build: ./bot
    environment:
      INSTANCE_ID: bot-2
      NATS_URL: nats://nats-1:4222,nats://nats-2:4222
```

### Model 2: Kubernetes (Production)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rosey-bot
spec:
  replicas: 5
  selector:
    matchLabels:
      app: rosey-bot
  template:
    spec:
      containers:
      - name: bot
        image: rosey-bot:latest
        env:
        - name: NATS_URL
          value: "nats://nats-cluster:4222"
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rosey-bot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rosey-bot
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 4. Implementation Phases

### Phase 1: NATS Clustering (4-6 hours)
- Multi-node NATS server setup
- High availability configuration
- Connection failover testing
- Cluster monitoring

### Phase 2: Stateless Bot Core (6-8 hours)
- Remove local state from bot
- Move state to NATS K/V or external store
- Instance-aware configuration
- Idempotent event handlers

### Phase 3: Load Distribution (4-6 hours)
- NATS queue groups for event distribution
- Platform adapter sharding
- Dynamic load balancing
- Load testing and tuning

### Phase 4: Leader Election (3-4 hours)
- NATS K/V leader election
- Singleton task coordination
- Leader failover testing
- Scheduled job management

### Phase 5: Deployment Automation (6-8 hours)
- Docker Compose setup (development)
- Kubernetes manifests (production)
- Helm charts (optional)
- Rolling update strategy
- Health checks and readiness probes

### Phase 6: Monitoring & Observability (6-8 hours)
- Prometheus metrics per instance
- Grafana dashboards (cluster view)
- Alert rules for cluster health
- Distributed tracing (Jaeger/Zipkin)
- Log aggregation (ELK/Loki)

---

## 5. Success Criteria

**Definition of Done:**
- [ ] NATS cluster with 3+ nodes running
- [ ] 5+ bot instances running across cluster
- [ ] Shared database service handles all instances
- [ ] Load distributed evenly across instances
- [ ] Leader election works with automatic failover
- [ ] Zero downtime rolling updates tested
- [ ] Auto-scaling works (Kubernetes HPA)
- [ ] Monitoring dashboards show cluster health
- [ ] Documentation for cluster deployment
- [ ] Failover tested (kill instances, verify recovery)

---

## 6. Performance Targets

| Scenario | Target |
|----------|--------|
| Message throughput (3 instances) | 3000+ msg/sec |
| Message throughput (5 instances) | 5000+ msg/sec |
| Instance startup time | <30 seconds |
| Leader election time | <10 seconds |
| Rolling update time (5 instances) | <5 minutes |
| Cross-instance message latency | <50ms p95 |
| Failover recovery time | <15 seconds |

---

## 7. Cost Analysis

**Infrastructure Costs (Estimated - AWS):**

| Component | Type | Count | Monthly Cost |
|-----------|------|-------|--------------|
| NATS Servers | t3.medium | 3 | $90 |
| Bot Instances | t3.small | 5 | $75 |
| Database Server | t3.medium | 1 | $30 |
| Load Balancer | ALB | 1 | $20 |
| **Total** | | | **$215/month** |

**Cost Comparison:**
- Single server (current): ~$30-50/month
- Cluster (Sprint 12): ~$215/month
- Cost multiplier: 4-7x
- Benefit: 99.9% uptime, 5x capacity, zero downtime updates

---

## 8. Future Enhancements (Sprint 13+)

- **Geographic Distribution**: Instances in multiple regions
- **Multi-Cluster Federation**: Connect clusters across regions
- **Edge Deployment**: Bot instances close to platform servers
- **Serverless Plugins**: Run plugins as serverless functions
- **Cost Optimization**: Spot instances, auto-shutdown idle instances

---

**Sprint Status**: Planning (Blocked by Sprint 9 + 10 + 11)  
**Estimated Effort**: 29-40 hours (4-6 days)  
**Sprint Goal**: The Expandables - expand across machines for scaling and reliability  
**Movie Tagline**: "They're expanding... cheaply but effectively!" (It's the knockoff, after all)
