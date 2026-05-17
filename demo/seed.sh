#!/bin/bash
# =================================================
# Arc 演示数据一键注入
# 用法: ./demo/seed.sh
# 前提: docker compose up -d 已启动
# =================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🔄 正在注入演示数据..."

docker compose exec -T db psql -U arc -d arc < "$SCRIPT_DIR/seed.sql"

echo ""
echo "✅ 演示数据注入完成！"
echo ""
echo "📋 已创建的演示待办："
echo "   1. 用户登录支持OAuth2.0          [pending]"
echo "   2. 订单导出性能优化               [analyzing] — 含对话"
echo "   3. 商品搜索接入Elasticsearch     [dev] — 含OpenHands执行日志"
echo "   4. 支付回调幂等性改造             [review]"
echo "   5. API接口限流方案实施            [done] — 含经验卡片"
echo "   6. 用户行为埋点系统设计           [pending]"
echo ""
echo "🧠 已创建的经验卡片："
echo "   1. Redis令牌桶限流实战"
echo "   2. MySQL到ES数据同步踩坑记录"
echo ""
echo "🌐 访问 http://localhost:3001 查看演示"
