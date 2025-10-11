# RAGFlow Docker 服务管理

## 问题解决

原来的配置每次启动 `docker-compose.yml` 都会重新创建 `docker-compose-base.yml` 中的服务，现在已修改为只启动 ragflow 服务。

## Docker Compose 网络命名说明

Docker Compose 会自动为网络名称添加项目前缀：
- **项目名** + **网络名** = 最终网络名称
- 默认项目名通常是目录名：`ragflow-20250916`
- 最终网络名：`ragflow-20250916_ragflow`

## 修改内容

1. **移除了 `include` 指令**：不再包含 `docker-compose-base.yml`
2. **使用外部网络**：ragflow 服务连接到由 `docker-compose-base.yml` 创建的 `ragflow-20250916_ragflow` 网络
3. **移除了 `depends_on`**：不再依赖 postgres 健康检查
4. **网络配置**：
   - `docker-compose-base.yml` 创建名为 `ragflow-20250916_ragflow` 的网络
   - `docker-compose.yml` 使用 `external: true` 连接到已存在的网络
5. **使用项目名**：通过 `-p ragflow` 参数统一项目名

## 使用方法

### 首次使用（初始化）
```bash
# 1. 启动基础服务（创建网络）
docker-compose -p ragflow -f docker-compose-base.yml up -d

# 2. 启动 ragflow 服务
docker-compose -p ragflow -f docker-compose.yml up -d ragflow
```

### 日常使用（只启动 ragflow）
```bash
# 使用脚本（推荐）
./start-ragflow.sh

# 或手动启动
docker-compose -p ragflow -f docker-compose.yml up -d ragflow
```

### 使用 ragflow.sh（完整管理）
```bash
# 启动 RAGFlow 服务（不重新创建基础服务）
./ragflow.sh start

# 停止 RAGFlow 服务（保留基础服务）
./ragflow.sh stop

# 重启 RAGFlow 服务
./ragflow.sh restart

# 查看服务状态
./ragflow.sh status

# 查看日志
./ragflow.sh logs
```

### 手动操作
```bash
# 只启动基础服务
docker-compose -f docker-compose-base.yml up -d

# 只启动 ragflow 服务
docker-compose -f docker-compose.yml up -d ragflow

# 停止 ragflow 服务
docker-compose -f docker-compose.yml down
```

## 服务说明

- **基础服务**：postgres、redis、minio、opensearch
- **应用服务**：ragflow-server
- **网络**：ragflow（外部网络）

## 优势

1. **快速启动**：只启动需要的服务
2. **数据持久**：基础服务数据不会丢失
3. **灵活管理**：可以独立管理各个服务
4. **资源节约**：避免不必要的服务重建