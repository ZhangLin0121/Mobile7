#!/bin/bash

# E-Mobile 7 企业级打卡服务自动部署脚本
# 适用于 Ubuntu/Debian 服务器

set -e

# 配置变量
SERVICE_NAME="emobile-checkin"
INSTALL_DIR="/opt/emobile-checkin"
SERVICE_USER="emobile"
PYTHON_VERSION="3.9"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo $0"
        exit 1
    fi
}

# 检查操作系统
check_os() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "无法确定操作系统版本"
        exit 1
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        log_warn "此脚本主要针对Ubuntu/Debian，其他系统可能需要调整"
    fi
    
    log_info "操作系统: $PRETTY_NAME"
}

# 更新系统包
update_system() {
    log_step "更新系统包..."
    apt update && apt upgrade -y
    apt install -y curl wget git vim htop python3 python3-pip python3-venv
}

# 创建服务用户
create_user() {
    log_step "创建服务用户..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        log_info "用户 $SERVICE_USER 已存在"
    else
        useradd --system --shell /bin/bash --home-dir $INSTALL_DIR --create-home $SERVICE_USER
        log_info "已创建用户: $SERVICE_USER"
    fi
}

# 创建安装目录
setup_directory() {
    log_step "设置安装目录..."
    
    mkdir -p $INSTALL_DIR
    chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    chmod 755 $INSTALL_DIR
    
    log_info "安装目录: $INSTALL_DIR"
}

# 安装Python虚拟环境
setup_python_env() {
    log_step "设置Python虚拟环境..."
    
    cd $INSTALL_DIR
    
    # 创建虚拟环境
    sudo -u $SERVICE_USER python3 -m venv .venv
    
    # 激活虚拟环境并安装依赖
    sudo -u $SERVICE_USER .venv/bin/pip install --upgrade pip
    
    log_info "Python虚拟环境已创建"
}

# 部署应用文件
deploy_application() {
    log_step "部署应用文件..."
    
    # 复制应用文件
    cp enhanced_scheduled_checkin_service.py $INSTALL_DIR/
    cp production_config.yaml $INSTALL_DIR/
    cp requirements_production.txt $INSTALL_DIR/
    
    # 设置文件权限
    chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR/*
    chmod 644 $INSTALL_DIR/*.py $INSTALL_DIR/*.yaml $INSTALL_DIR/*.txt
    chmod +x $INSTALL_DIR/enhanced_scheduled_checkin_service.py
    
    # 安装Python依赖
    cd $INSTALL_DIR
    sudo -u $SERVICE_USER .venv/bin/pip install -r requirements_production.txt
    
    log_info "应用文件部署完成"
}

# 配置systemd服务
setup_systemd_service() {
    log_step "配置systemd服务..."
    
    # 复制服务文件
    cp emobile-checkin.service /etc/systemd/system/
    
    # 重新加载systemd配置
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable $SERVICE_NAME
    
    log_info "systemd服务配置完成"
}

# 配置日志轮转
setup_log_rotation() {
    log_step "配置日志轮转..."
    
    cat > /etc/logrotate.d/$SERVICE_NAME << EOF
$INSTALL_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF
    
    log_info "日志轮转配置完成"
}

# 配置防火墙
setup_firewall() {
    log_step "配置防火墙..."
    
    if command -v ufw &> /dev/null; then
        # 允许健康检查端口
        ufw allow 8080/tcp comment "E-Mobile Health Check"
        log_info "UFW防火墙规则已添加"
    else
        log_warn "未检测到UFW防火墙，请手动配置"
    fi
}

# 测试配置
test_configuration() {
    log_step "测试配置..."
    
    cd $INSTALL_DIR
    
    # 测试Python环境
    sudo -u $SERVICE_USER .venv/bin/python -c "import requests, schedule, yaml; print('依赖检查通过')"
    
    # 测试应用启动
    sudo -u $SERVICE_USER timeout 10 .venv/bin/python enhanced_scheduled_checkin_service.py --test --test-type off || true
    
    log_info "配置测试完成"
}

# 启动服务
start_service() {
    log_step "启动服务..."
    
    systemctl start $SERVICE_NAME
    systemctl status $SERVICE_NAME --no-pager
    
    log_info "服务启动完成"
}

# 显示后续配置说明
show_next_steps() {
    log_step "部署完成！"
    
    echo ""
    echo "🎉 E-Mobile 7 打卡服务部署成功！"
    echo ""
    echo "📝 后续配置步骤："
    echo "1. 编辑配置文件: sudo nano $INSTALL_DIR/production_config.yaml"
    echo "2. 填入您的真实用户名和密码"
    echo "3. 重启服务: sudo systemctl restart $SERVICE_NAME"
    echo ""
    echo "🔧 常用命令："
    echo "  查看服务状态: sudo systemctl status $SERVICE_NAME"
    echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
    echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
    echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
    echo ""
    echo "📊 监控信息："
    echo "  健康检查: http://localhost:8080/health"
    echo "  日志文件: $INSTALL_DIR/emobile_checkin.log"
    echo "  打卡记录: $INSTALL_DIR/punch_records.json"
    echo ""
    echo "⚠️  重要提醒："
    echo "  - 请确保服务器时区设置正确"
    echo "  - 建议定期检查日志文件"
    echo "  - 节假日会自动跳过打卡"
    echo ""
}

# 主函数
main() {
    echo "🚀 开始部署 E-Mobile 7 企业级打卡服务..."
    echo ""
    
    check_root
    check_os
    update_system
    create_user
    setup_directory
    setup_python_env
    deploy_application
    setup_systemd_service
    setup_log_rotation
    setup_firewall
    test_configuration
    start_service
    show_next_steps
}

# 执行主函数
main "$@" 