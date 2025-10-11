#!/bin/bash

# 启动脚本：只启动 ragflow 服务，不重新创建基础服务

echo "检查基础服务是否运行..."

# 检查基础服务是否在运行
if ! docker ps --format "table {{.Names}}" | grep -q "ragflow-postgres\|ragflow-redis\|ragflow-minio\|ragflow-opensearch-01"; then
    echo "基础服务未运行，正在启动基础服务..."
    docker-compose -f docker-compose-base.yml up -d
    echo "等待基础服务启动完成..."
    sleep 30
else
    echo "基础服务已在运行"
fi

# 检查网络是否存在
if ! docker network ls --format "{{.Name}}" | grep -q "ragflow"; then
    echo "创建 ragflow 网络..."
    docker network create ragflow
fi

echo "启动 ragflow 服务..."
docker-compose -f docker-compose.yml up -d ragflow

echo "ragflow 服务启动完成！"
echo "访问地址: http://localhost:${SVR_HTTP_PORT:-9380}"
