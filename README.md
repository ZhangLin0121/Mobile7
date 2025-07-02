# E-Mobile 7 自动打卡系统

## 📋 项目概述

极简高效的 E-Mobile 7 自动打卡服务，支持多用户、定时打卡、简洁配置。

## 🎯 核心特性

- ✅ **多用户支持** - 一个服务管理多个用户账号
- ✅ **工作日打卡** - 自动识别工作日进行上下班打卡
- ✅ **简洁配置** - 只需配置基本信息即可运行
- ✅ **自动重连** - 认证失败自动重新登录
- ✅ **systemd服务** - 开机自启动，故障自动重启
- ✅ **打卡记录** - 记录所有打卡结果，方便查询

## 📁 项目结构

```
E-Mobile 7/
├── checkin_service.py    # 主打卡服务程序 (307行)
├── config.yaml          # 配置文件
├── checkin.service       # systemd服务配置
├── requirements.txt      # Python依赖
├── README.md            # 项目说明
├── punch_records.json   # 打卡记录
└── checkin.log          # 运行日志
```

## 🚀 快速部署

### 1. 上传文件到服务器

```bash
# 上传到服务器
scp checkin_service.py checkin.service requirements.txt root@47.122.68.192:/opt/emobile-checkin/
```

### 2. 安装依赖

```bash
ssh root@47.122.68.192
cd /opt/emobile-checkin
pip3 install -r requirements.txt
```

### 3. 配置服务

```bash
# 复制服务文件
cp checkin.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable checkin
systemctl start checkin
```

## ⚙️ 配置文件说明

### config.yaml 示例

```yaml
server:
  base_url: http://223.76.229.248:11032
  auth_url: http://223.76.229.248:8999

users:
  - username: 请修改为你的用户名
    password: 请修改为你的密码
    display_name: 请修改为显示名称
    enabled: true
    location:
      latitude: '30.487572428385416'
      longitude: '114.50522216796875'
      position: 中国武汉市洪山区高新大道772号武汉东湖新技术开发区
  
  # 添加更多用户
  # - username: user2
  #   password: password2
  #   display_name: 用户2
  #   enabled: true
  #   location:
  #     latitude: '30.487572428385416'
  #     longitude: '114.50522216796875'
  #     position: 中国武汉市洪山区高新大道772号武汉东湖新技术开发区

schedule:
  morning:
    start: '06:00'    # 上班打卡开始时间
    end: '07:00'      # 上班打卡结束时间
  evening:
    start: '17:30'    # 下班打卡开始时间
    end: '18:00'      # 下班打卡结束时间
```

### 用户配置说明

- `username`: E-Mobile登录用户名
- `password`: E-Mobile登录密码
- `display_name`: 显示名称（用于日志）
- `enabled`: 是否启用该用户（true/false）
- `location`: 打卡地理位置信息

## 📊 使用方法

### 测试打卡

```bash
# 测试下班打卡
python3 checkin_service.py --test --type off

# 测试上班打卡
python3 checkin_service.py --test --type on

# 使用自定义配置文件测试
python3 checkin_service.py --config my_config.yaml --test
```

### 运行服务

```bash
# 直接运行
python3 checkin_service.py

# 使用systemd管理
systemctl start checkin
systemctl status checkin
systemctl stop checkin
```

### 查看日志

```bash
# 查看服务日志
journalctl -u checkin -f

# 查看程序日志
tail -f /opt/emobile-checkin/checkin.log

# 查看打卡记录
cat /opt/emobile-checkin/punch_records.json
```

## 🕒 打卡时间

- **上班打卡**: 周一至周五 06:00-07:00 随机时间
- **下班打卡**: 周一至周五 17:30-18:00 随机时间
- **周末**: 自动跳过

### 时间区间配置

系统会在指定时间区间内**随机选择打卡时间**，避免固定时间被检测：

```yaml
schedule:
  morning:
    start: '06:00'    # 最早 6:00
    end: '07:00'      # 最晚 7:00
  evening:
    start: '17:30'    # 最早 17:30
    end: '18:00'      # 最晚 18:00
```

每次启动服务时，会为每天生成不同的随机时间，例如：
- 周一: 上班 06:51, 下班 17:31
- 周二: 上班 06:04, 下班 17:56
- 周三: 上班 06:56, 下班 17:32

## 📈 打卡记录

所有打卡结果保存在 `punch_records.json` 中，包含：

```json
{
  "timestamp": "2025-07-03T01:30:06.145447",
  "user": "张志远",
  "type": "off",
  "time": "2025-07-03 01:30:06",
  "message": "打卡成功！"
}
```

## 🔧 管理命令

```bash
# 服务状态
systemctl status checkin

# 重启服务
systemctl restart checkin

# 查看实时日志
journalctl -u checkin -f

# 查看最近100条打卡记录
tail -100 punch_records.json
```

## 🎯 架构优势

### 代码对比

- **原版本**: 820行（冗余功能多）
- **新版本**: 307行（减少62%）

### 移除冗余功能

❌ 健康检查HTTP服务器  
❌ 复杂节假日API检测  
❌ 通知系统  
❌ 信号处理器  
❌ 复杂错误重试机制  
❌ 详细日志轮转  

### 保留核心功能

✅ 用户认证登录  
✅ 多用户管理  
✅ 打卡功能（上班/下班）  
✅ 定时调度（工作日）  
✅ 基本配置管理  
✅ 打卡记录保存  

## 📞 技术支持

如遇问题请检查：
1. 配置文件格式是否正确
2. 用户名密码是否有效
3. 网络连接是否正常
4. 服务是否正常启动

---

**🎉 极简架构，高效运行！** 