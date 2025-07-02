# E-Mobile 7 企业级自动打卡系统

## 📋 项目概述

这是一个基于HAR文件分析开发的E-Mobile 7企业级自动打卡系统，支持节假日检测、周末打卡、随机时间、自动重登等企业级功能。

## 🎯 核心特性

- ✅ **节假日自动检测** - 集成中国节假日API，自动跳过法定节假日
- ✅ **周末正常打卡** - 支持周六周日独立配置打卡时间
- ✅ **随机时间打卡** - 在指定时间范围内随机打卡，避免检测
- ✅ **自动重新登录** - 每小时自动检查登录状态并重新认证
- ✅ **系统级服务** - systemd服务配置，开机自启动和故障重启
- ✅ **完整监控** - 日志轮转、健康检查、统计分析
- ✅ **多用户支持** - 支持多个用户账号同时管理

## 📁 项目结构

### 🚀 企业级部署文件
- `enhanced_scheduled_checkin_service.py` - 增强版定时打卡服务主程序
- `production_config.yaml` - 生产环境配置文件
- `emobile-checkin.service` - systemd服务配置
- `deploy.sh` - 自动部署脚本
- `monitor.sh` - 服务监控脚本
- `requirements_production.txt` - 生产环境Python依赖
- `DEPLOYMENT_GUIDE.md` - 完整部署指南
- `emobile-deployment.tar.gz` - 一键部署包

### 📚 开发参考文件
- `emobile_login_with_checkin.py` - 原始开发版本（参考）
- `Stream-2025-06-28 20:07:12.har` - HAR抓包文件（分析源）
- `*.txt` - HAR分析过程文档

### 🔧 手动打卡工具
- `manual_checkin.py` - 手动/补打卡工具，支持一次性打卡和帮助同事打卡

## 🚀 快速部署

### 1. 上传到服务器

```bash
# 上传部署包到服务器
scp emobile-deployment.tar.gz root@47.122.68.192:/tmp/

# 登录服务器并解压
ssh root@47.122.68.192
cd /tmp
tar -xzf emobile-deployment.tar.gz
```

### 2. 执行自动部署

```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. 配置用户信息

```bash
sudo nano /opt/emobile-checkin/production_config.yaml
# 修改用户名和密码
sudo systemctl restart emobile-checkin
```

## 📊 服务管理

```bash
# 查看服务状态
sudo systemctl status emobile-checkin

# 查看实时日志
sudo journalctl -u emobile-checkin -f

# 使用监控脚本
/opt/emobile-checkin/monitor.sh status   # 服务状态
/opt/emobile-checkin/monitor.sh logs     # 查看日志
/opt/emobile-checkin/monitor.sh records  # 打卡记录
/opt/emobile-checkin/monitor.sh health   # 健康检查
/opt/emobile-checkin/monitor.sh stats    # 统计信息
```

## ⚙️ 打卡配置

### 时间配置
- **工作日上班**: 7:30-8:00 随机时间
- **工作日下班**: 18:00-19:00 随机时间  
- **周末上班**: 8:00-8:30 随机时间
- **周末下班**: 17:30-18:30 随机时间

### 节假日处理
- 自动检测中国法定节假日
- 节假日自动跳过打卡
- 支持手动开关节假日检测

## 🎯 一次性打卡助手

### 功能说明
专门为帮助同事临时打卡而设计的工具，**无需将同事信息配置到服务器**，适用于偶尔帮忙的场景。

### 快速使用
```bash
python3 manual_checkin.py
```

### 使用步骤

1. **运行脚本**
   ```bash
   python3 manual_checkin.py
   ```

2. **输入信息**
   - 👤 **用户名/手机号**: 输入同事的E-Mobile用户名或手机号
   - 🔑 **密码**: 输入同事的E-Mobile密码

3. **选择打卡类型**
   - `on` - 上班打卡
   - `off` - 下班打卡

### 使用场景
- ✅ 同事临时请假，需要代为打卡
- ✅ 同事手机没电或网络问题
- ✅ 偶尔帮忙，不需要长期配置
- ✅ 补打漏掉的卡
- ❌ 不适用于长期代打卡（请使用服务器配置）

### 打卡信息
- **打卡地点**: 武汉光谷（自动定位）
- **地理坐标**: 纬度 30.487572, 经度 114.505221
- **具体位置**: 中国武汉市洪山区高新大道772号武汉东湖新技术开发区

### 注意事项

1. **隐私保护**: 
   - 脚本不会保存任何用户信息
   - 每次使用都需要重新输入

2. **安全性**:
   - 仅在本地执行，不上传到服务器
   - 使用完毕后不留痕迹

3. **网络要求**:
   - 需要能访问 E-Mobile 服务器
   - 确保网络连接稳定

4. **时间限制**:
   - 遵循公司打卡时间规定
   - 建议在正常打卡时间内使用

## 🔍 技术架构

- **后端**: Python 3.9+
- **任务调度**: schedule库
- **配置管理**: YAML
- **服务管理**: systemd
- **日志管理**: RotatingFileHandler
- **节假日API**: timor.tech
- **监控**: 健康检查接口

## 📈 监控指标

- 服务运行状态
- 打卡成功率统计
- 连续失败次数监控
- 磁盘空间使用率
- 日志错误统计

## 🔒 安全特性

- 专用服务用户运行
- 最小权限原则
- 系统调用过滤
- 资源使用限制
- 敏感信息保护

## 📞 技术支持

详细部署和使用说明请参考：`DEPLOYMENT_GUIDE.md`

如遇问题请：
1. 查看服务日志
2. 运行健康检查
3. 检查配置文件
4. 验证网络连接

---

**🎉 部署完成后，您的打卡服务将实现完全自动化运行！**

- 节假日智能跳过
- 工作日/周末分别打卡
- 开机自启动
- 故障自动重启
- 完整监控报告 

💡 **提示**: 
- 如需长期自动打卡，请使用服务器部署的企业级服务
- 一次性打卡助手仅适用于临时帮助场景 