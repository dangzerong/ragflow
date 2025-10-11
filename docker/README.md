# RAGFlow Docker 服务管理

## 问题解决

原来的配置每次启动 `docker-compose.yml` 都会重新创建 `docker-compose-base.yml` 中的服务，现在已修改为只启动 ragflow 服务。

## 修改内容

1. **移除了 `include` 指令**：不再包含 `docker-compose-base.yml`
2. **使用外部网络**：ragflow 服务连接到已存在的 `ragflow` 网络
3. **移除了 `depends_on`**：不再依赖 postgres 健康检查

## 使用方法

### 首次使用（初始化）
```bash
cd docker
./ragflow.sh init
```

### 日常使用
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