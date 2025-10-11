#!/bin/bash

# 停止脚本：只停止 ragflow 服务，保留基础服务

echo "停止 ragflow 服务..."
docker-compose -f docker-compose.yml down

echo "ragflow 服务已停止"
echo "基础服务（postgres、redis、minio、opensearch）仍在运行"
