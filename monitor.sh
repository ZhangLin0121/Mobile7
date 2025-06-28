#!/bin/bash

# E-Mobile 7 打卡服务监控脚本
# 用于检查服务状态、日志分析和健康监控

SERVICE_NAME="emobile-checkin"
INSTALL_DIR="/opt/emobile-checkin"
LOG_FILE="$INSTALL_DIR/emobile_checkin.log"
RECORDS_FILE="$INSTALL_DIR/punch_records.json"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 显示帮助信息
show_help() {
    echo "E-Mobile 7 打卡服务监控脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  status      显示服务状态"
    echo "  logs        显示最近日志"
    echo "  records     显示最近打卡记录"
    echo "  health      健康检查"
    echo "  stats       统计信息"
    echo "  restart     重启服务"
    echo "  help        显示此帮助信息"
    echo ""
}

# 检查服务状态
check_status() {
    echo -e "${BLUE}=== 服务状态 ===${NC}"
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "状态: ${GREEN}运行中${NC}"
        echo "启动时间: $(systemctl show $SERVICE_NAME --property=ActiveEnterTimestamp --value)"
        echo "进程ID: $(systemctl show $SERVICE_NAME --property=MainPID --value)"
    else
        echo -e "状态: ${RED}已停止${NC}"
    fi
    
    echo ""
    echo "启用状态: $(systemctl is-enabled $SERVICE_NAME)"
    echo ""
}

# 显示最近日志
show_logs() {
    echo -e "${BLUE}=== 最近日志 (最后50行) ===${NC}"
    
    if [[ -f "$LOG_FILE" ]]; then
        tail -n 50 "$LOG_FILE" | while IFS= read -r line; do
            if [[ $line == *"ERROR"* ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ $line == *"WARN"* ]]; then
                echo -e "${YELLOW}$line${NC}"
            elif [[ $line == *"✅"* ]] || [[ $line == *"成功"* ]]; then
                echo -e "${GREEN}$line${NC}"
            else
                echo "$line"
            fi
        done
    else
        echo "日志文件不存在: $LOG_FILE"
    fi
    
    echo ""
}

# 显示打卡记录
show_records() {
    echo -e "${BLUE}=== 最近打卡记录 (最后10条) ===${NC}"
    
    if [[ -f "$RECORDS_FILE" ]]; then
        python3 -c "
import json
import sys
try:
    with open('$RECORDS_FILE', 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    for record in records[-10:]:
        print(f\"{record['timestamp'][:19]} | {record['display_name']} | {'上班' if record['sign_type'] == 'on' else '下班'} | {record['message']}\")
except Exception as e:
    print(f'读取记录失败: {e}')
"
    else
        echo "打卡记录文件不存在: $RECORDS_FILE"
    fi
    
    echo ""
}

# 健康检查
health_check() {
    echo -e "${BLUE}=== 健康检查 ===${NC}"
    
    # 检查服务状态
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "服务状态: ${GREEN}正常${NC}"
    else
        echo -e "服务状态: ${RED}异常${NC}"
        return 1
    fi
    
    # 检查端口
    if netstat -tuln | grep -q ":8080 "; then
        echo -e "健康检查端口: ${GREEN}正常${NC}"
    else
        echo -e "健康检查端口: ${YELLOW}未监听${NC}"
    fi
    
    # 检查日志文件
    if [[ -f "$LOG_FILE" ]]; then
        log_size=$(du -h "$LOG_FILE" | cut -f1)
        echo "日志文件大小: $log_size"
        
        # 检查最近是否有错误
        recent_errors=$(tail -n 100 "$LOG_FILE" | grep -c "ERROR" || true)
        if [[ $recent_errors -gt 0 ]]; then
            echo -e "最近错误数: ${YELLOW}$recent_errors${NC}"
        else
            echo -e "最近错误数: ${GREEN}0${NC}"
        fi
    else
        echo -e "日志文件: ${RED}不存在${NC}"
    fi
    
    # 检查磁盘空间
    disk_usage=$(df "$INSTALL_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        echo -e "磁盘使用率: ${RED}${disk_usage}%${NC}"
    elif [[ $disk_usage -gt 80 ]]; then
        echo -e "磁盘使用率: ${YELLOW}${disk_usage}%${NC}"
    else
        echo -e "磁盘使用率: ${GREEN}${disk_usage}%${NC}"
    fi
    
    echo ""
}

# 统计信息
show_stats() {
    echo -e "${BLUE}=== 统计信息 ===${NC}"
    
    if [[ -f "$RECORDS_FILE" ]]; then
        python3 -c "
import json
from datetime import datetime, timedelta
from collections import defaultdict

try:
    with open('$RECORDS_FILE', 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    if not records:
        print('暂无打卡记录')
        exit()
    
    # 总体统计
    print(f'总打卡次数: {len(records)}')
    
    # 按类型统计
    type_stats = defaultdict(int)
    for record in records:
        type_stats[record['sign_type']] += 1
    
    print(f'上班打卡: {type_stats[\"on\"]}次')
    print(f'下班打卡: {type_stats[\"off\"]}次')
    
    # 最近7天统计
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    recent_records = [
        r for r in records 
        if datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) > week_ago
    ]
    
    print(f'最近7天打卡: {len(recent_records)}次')
    
    # 最后一次打卡
    if records:
        last_record = records[-1]
        print(f'最后打卡: {last_record[\"timestamp\"][:19]} ({\"上班\" if last_record[\"sign_type\"] == \"on\" else \"下班\"})')

except Exception as e:
    print(f'统计失败: {e}')
"
    else
        echo "无打卡记录文件"
    fi
    
    echo ""
}

# 重启服务
restart_service() {
    echo -e "${BLUE}=== 重启服务 ===${NC}"
    
    echo "正在重启服务..."
    if systemctl restart $SERVICE_NAME; then
        echo -e "重启: ${GREEN}成功${NC}"
        sleep 2
        check_status
    else
        echo -e "重启: ${RED}失败${NC}"
        return 1
    fi
}

# 主函数
main() {
    case "${1:-status}" in
        "status")
            check_status
            ;;
        "logs")
            show_logs
            ;;
        "records")
            show_records
            ;;
        "health")
            health_check
            ;;
        "stats")
            show_stats
            ;;
        "restart")
            restart_service
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 '$0 help' 查看帮助信息"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 