#!/bin/bash

# RAGFlow 服务管理脚本

case "$1" in
    "start")
        echo "启动 RAGFlow 服务..."
        ./start-ragflow.sh
        ;;
    "stop")
        echo "停止 RAGFlow 服务..."
        ./stop-ragflow.sh
        ;;
    "restart")
        echo "重启 RAGFlow 服务..."
        ./stop-ragflow.sh
        sleep 5
        ./start-ragflow.sh
        ;;
    "status")
        echo "检查服务状态..."
        echo "=== RAGFlow 服务 ==="
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(ragflow-server|ragflow-postgres|ragflow-redis|ragflow-minio|ragflow-opensearch)"
        ;;
    "logs")
        echo "查看 RAGFlow 日志..."
        docker-compose -f docker-compose.yml logs -f ragflow
        ;;
    "init")
        echo "初始化所有服务（仅首次使用）..."
        docker-compose -f docker-compose-base.yml up -d
        echo "等待基础服务启动..."
        sleep 30
        docker-compose -f docker-compose.yml up -d ragflow
        echo "所有服务启动完成！"
        ;;
    "clean")
        echo "清理所有服务（包括数据）..."
        read -p "确定要删除所有数据吗？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose -f docker-compose.yml down
            docker-compose -f docker-compose-base.yml down -v
            docker network rm ragflow 2>/dev/null || true
            echo "所有服务已清理"
        else
            echo "操作已取消"
        fi
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs|init|clean}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动 RAGFlow 服务（不重新创建基础服务）"
        echo "  stop    - 停止 RAGFlow 服务（保留基础服务）"
        echo "  restart - 重启 RAGFlow 服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看 RAGFlow 日志"
        echo "  init    - 初始化所有服务（仅首次使用）"
        echo "  clean   - 清理所有服务（包括数据）"
        exit 1
        ;;
esac
