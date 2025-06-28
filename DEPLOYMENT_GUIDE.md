# E-Mobile 7 企业级打卡服务部署指南

## 📋 概述

本指南将帮助您在服务器 `47.122.68.192` 上部署 E-Mobile 7 企业级定时打卡服务，支持：

- ✅ 节假日自动检测（跳过法定节假日）
- ✅ 周末正常打卡
- ✅ 工作日和周末分别配置打卡时间
- ✅ 随机时间打卡（避免检测）
- ✅ 自动重新登录
- ✅ 系统级服务（开机自启）
- ✅ 完整的监控和日志

## 🚀 快速部署

### 1. 准备工作

确保您有服务器的 root 权限：

```bash
ssh root@47.122.68.192
```

### 2. 上传部署文件

将以下文件上传到服务器：

```bash
# 在本地打包文件
tar -czf emobile-deployment.tar.gz \
    enhanced_scheduled_checkin_service.py \
    production_config.yaml \
    requirements_production.txt \
    emobile-checkin.service \
    deploy.sh \
    monitor.sh

# 上传到服务器
scp emobile-deployment.tar.gz root@47.122.68.192:/tmp/

# 在服务器上解压
ssh root@47.122.68.192
cd /tmp
tar -xzf emobile-deployment.tar.gz
```

### 3. 执行自动部署

```bash
chmod +x deploy.sh
./deploy.sh
```

部署脚本将自动完成：
- 系统包更新
- 创建服务用户
- 安装 Python 环境
- 配置 systemd 服务
- 设置日志轮转
- 配置防火墙
- 启动服务

### 4. 配置用户信息

编辑配置文件，填入您的真实登录信息：

```bash
sudo nano /opt/emobile-checkin/production_config.yaml
```

修改以下内容：
```yaml
users:
  - username: '您的实际用户名'  # 替换这里
    password: '您的实际密码'    # 替换这里
    user_id: '585'
    display_name: '张志远'
    # ... 其他配置保持不变
```

### 5. 重启服务

```bash
sudo systemctl restart emobile-checkin
```

## 📊 服务管理

### 基本命令

```bash
# 查看服务状态
sudo systemctl status emobile-checkin

# 查看实时日志
sudo journalctl -u emobile-checkin -f

# 重启服务
sudo systemctl restart emobile-checkin

# 停止服务
sudo systemctl stop emobile-checkin

# 启动服务
sudo systemctl start emobile-checkin
```

### 监控脚本

使用提供的监控脚本：

```bash
# 赋予执行权限
chmod +x /opt/emobile-checkin/monitor.sh

# 查看服务状态
./monitor.sh status

# 查看最近日志
./monitor.sh logs

# 查看打卡记录
./monitor.sh records

# 健康检查
./monitor.sh health

# 统计信息
./monitor.sh stats
```

## ⚙️ 配置说明

### 打卡时间配置

```yaml
schedule:
  # 工作日配置
  workday:
    morning:
      enabled: true
      time_range: ['07:30', '08:00']  # 上班时间范围
    evening:
      enabled: true
      time_range: ['18:00', '19:00']  # 下班时间范围
  
  # 周末配置
  weekend:
    morning:
      enabled: true
      time_range: ['08:00', '08:30']  # 周末上班时间
    evening:
      enabled: true
      time_range: ['17:30', '18:30']  # 周末下班时间
  
  # 节假日检测
  holiday_check: true  # 自动跳过法定节假日
```

### 用户打卡规则

```yaml
checkin_rules:
  workday_morning_enabled: true   # 工作日上班打卡
  workday_evening_enabled: true   # 工作日下班打卡
  weekend_morning_enabled: true   # 周末上班打卡
  weekend_evening_enabled: true   # 周末下班打卡
```

## 🔍 监控和维护

### 日志文件位置

- 应用日志：`/opt/emobile-checkin/emobile_checkin.log`
- 系统日志：`journalctl -u emobile-checkin`
- 打卡记录：`/opt/emobile-checkin/punch_records.json`

### 健康检查

服务提供健康检查接口（端口 8080）：

```bash
curl http://localhost:8080/health
```

### 日志轮转

日志文件会自动轮转：
- 每日轮转
- 保留 30 天
- 自动压缩

### 磁盘空间监控

定期检查磁盘使用情况：

```bash
df -h /opt/emobile-checkin
```

## 🛠️ 故障排除

### 服务无法启动

1. 检查配置文件语法：
```bash
python3 -c "import yaml; yaml.safe_load(open('/opt/emobile-checkin/production_config.yaml'))"
```

2. 检查权限：
```bash
ls -la /opt/emobile-checkin/
```

3. 查看详细错误：
```bash
sudo journalctl -u emobile-checkin --no-pager
```

### 打卡失败

1. 检查网络连接：
```bash
curl -I http://223.76.229.248:11032
```

2. 验证用户凭据：
```bash
cd /opt/emobile-checkin
sudo -u emobile .venv/bin/python enhanced_scheduled_checkin_service.py --test --test-type off
```

3. 检查节假日 API：
```bash
curl "http://timor.tech/api/holiday/info/$(date +%Y-%m-%d)"
```

### 性能问题

1. 检查内存使用：
```bash
ps aux | grep emobile
```

2. 检查 CPU 使用：
```bash
top -p $(pgrep -f emobile)
```

## 📈 高级配置

### 通知配置

启用 Webhook 通知：

```yaml
notification:
  enabled: true
  webhook_url: 'https://your-webhook-url.com/notify'
```

### 多用户支持

添加更多用户：

```yaml
users:
  - username: 'user1'
    password: 'pass1'
    user_id: '585'
    display_name: '张志远'
    # ... 配置

  - username: 'user2'
    password: 'pass2'
    user_id: '586'
    display_name: '李四'
    # ... 配置
```

### 自定义时间

根据需要调整打卡时间：

```yaml
# 示例：调整为更早的上班时间
workday:
  morning:
    time_range: ['07:00', '07:30']
```

## 🔒 安全建议

1. **定期更新密码**：建议每 3 个月更新一次密码
2. **监控异常**：定期检查日志中的异常活动
3. **备份配置**：定期备份配置文件
4. **防火墙**：确保只开放必要的端口
5. **权限最小化**：服务以专用用户运行，权限最小

## 📞 支持

如果遇到问题，请：

1. 查看日志文件
2. 运行健康检查
3. 检查网络连接
4. 验证配置文件

---

**部署完成后，您的 E-Mobile 7 打卡服务将：**

- ✅ 每天自动检查是否为节假日
- ✅ 工作日在 7:30-8:00 和 18:00-19:00 随机时间打卡
- ✅ 周末在 8:00-8:30 和 17:30-18:30 随机时间打卡
- ✅ 节假日自动跳过，不进行打卡
- ✅ 开机自动启动，故障自动重启
- ✅ 完整的日志记录和监控

祝您使用愉快！🎉 