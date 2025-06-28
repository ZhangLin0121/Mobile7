#!/usr/bin/env python3
"""
E-Mobile 7 一次性打卡脚本
用于帮助同事临时打卡，无需配置到服务器
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any

# 智能代理处理：检测代理是否可用，不可用则禁用
def check_proxy_available():
    """检查系统代理是否可用"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 7890))
        sock.close()
        return result == 0
    except:
        return False

if not check_proxy_available():
    print("🔍 检测到代理不可用，临时禁用代理以访问E-Mobile服务器")
    # 仅在代理不可用时才禁用
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
    os.environ.pop('ALL_PROXY', None)
    os.environ.pop('all_proxy', None)
else:
    print("🔍 检测到代理可用，保持代理设置")

class OneTimeCheckin:
    """一次性打卡类"""
    
    def __init__(self):
        self.base_url = 'http://223.76.229.248:11032'
        self.auth_url = 'http://223.76.229.248:8999'
        self.session = requests.Session()
        
        # 彻底禁用代理
        self.session.proxies = {
            'http': '',
            'https': ''
        }
        self.session.trust_env = False
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # 固定位置信息（武汉光谷）
        self.location = {
            'latitude': '30.487572428385416',
            'longitude': '114.50522216796875',
            'position': '中国武汉市洪山区高新大道772号武汉东湖新技术开发区'
        }
    
    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        try:
            print(f"🔐 正在认证用户: {username}")
            
            # 调用真正的登录API
            login_url = f"{self.auth_url}/emp/passport/login"
            login_data = {
                'loginid': username,
                'password': password,
                'device_type': '1',
                'client_type': '2'
            }
            
            # 设置登录请求的headers
            login_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Accept-Language': 'zh-CN,zh;q=0.9'
            }
            
            response = self.session.post(login_url, json=login_data, headers=login_headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # 检查登录是否成功
                    if data.get('errcode') == 0:
                        # 提取用户信息
                        user_id = data.get('base_user_id')
                        access_token = data.get('access_token')
                        user_name = data.get('base_user_name')
                        
                        if user_id and access_token:
                            # 设置认证信息
                            self.session.cookies.set('loginidweaver', str(user_id))
                            self.session.headers.update({
                                'emheadercode': access_token,
                                'emaccesstk': access_token,
                                'emheaderuserid': str(user_id)
                            })
                            
                            print(f"✅ 用户 {username} 认证成功")
                            print(f"   用户ID: {user_id}")
                            print(f"   姓名: {user_name}")
                            return True
                        else:
                            print(f"❌ 登录响应中缺少用户ID或访问token")
                            print(f"   响应数据: {data}")
                            return False
                    else:
                        error_msg = data.get('errmsg') or '登录失败'
                        print(f"❌ 登录失败: {error_msg}")
                        return False
                        
                except json.JSONDecodeError:
                    print(f"❌ 登录响应不是有效的JSON格式")
                    print(f"   响应内容: {response.text[:200]}...")
                    return False
            else:
                print(f"❌ 登录请求失败: HTTP {response.status_code}")
                print(f"   响应内容: {response.text[:200]}...")
                return False
            
        except Exception as e:
            print(f"❌ 登录异常: {str(e)}")
            return False
    
    def get_buttons(self) -> Optional[Dict[str, Any]]:
        """获取打卡按钮信息"""
        try:
            url = f"{self.base_url}/api/hrm/kq/attendanceButton/getButtons"
            params = {
                'latitude': self.location['latitude'],
                'longitude': self.location['longitude']
            }
            
            # 尝试POST方法（根据HAR文件分析，可能需要POST）
            response = self.session.post(url, json=params, timeout=10)
            
# 调试信息已移除，如需调试请取消注释下面两行
            # print(f"🔍 调试信息: 状态码={response.status_code}")
            # print(f"🔍 调试信息: 响应内容={response.text[:200]}...")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('status') == '1':
                        return data
                    else:
                        print(f"❌ API返回错误: {data}")
                        return None
                except json.JSONDecodeError:
                    print(f"❌ 响应不是有效的JSON格式")
                    return None
            
            print(f"❌ HTTP请求失败: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"❌ 获取打卡按钮异常: {str(e)}")
            return None
    
    def punch_card(self, button_type: str = 'off') -> bool:
        """执行打卡"""
        try:
            print(f"⏰ 开始执行{'下班' if button_type == 'off' else '上班'}打卡")
            
            # 获取按钮信息
            buttons_data = self.get_buttons()
            if not buttons_data:
                return False
            
            # 执行打卡
            url = f"{self.base_url}/api/hrm/kq/attendanceButton/punchButton"
            current_time = datetime.now()
            punch_data = {
                "signdate": current_time.strftime("%Y-%m-%d"),
                "signtime": current_time.strftime("%H:%M:%S"),
                "belongdate": current_time.strftime("%Y-%m-%d"),
                "active": "1",
                "time": "",
                "needSign": "1", 
                "type": button_type,
                "canSignTime": "23:59:59" if button_type == "off" else "00:00:00",
                "locationshowaddress": "",
                "longitude": self.location["longitude"],
                "latitude": self.location["latitude"], 
                "position": self.location["position"],
                "browser": "1"
            }
            
            response = self.session.post(url, data=punch_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('success') == '1':
                    sign_time = data.get('signtime', datetime.now().strftime('%H:%M:%S'))
                    print(f"✅ 打卡成功！")
                    print(f"   打卡时间: {sign_time}")
                    print(f"   打卡位置: {self.location['position']}")
                    print(f"   坐标信息: 纬度{self.location['latitude']}, 经度{self.location['longitude']}")
                    print(f"   返回信息: {data.get('message', '打卡成功')}")
                    return True
                else:
                    print(f"❌ 打卡失败: {data.get('message', '未知错误')}")
                    return False
            else:
                print(f"❌ 打卡请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 打卡异常: {str(e)}")
            return False
    
    def one_time_checkin(self, username: str, password: str, checkin_type: str = 'off') -> bool:
        """一次性打卡流程"""
        print("=" * 50)
        print("🎯 E-Mobile 7 一次性打卡服务")
        print("=" * 50)
        
        # 登录
        if not self.login(username, password):
            return False
        
        # 打卡
        success = self.punch_card(checkin_type)
        
        if success:
            print("=" * 50)
            print("🎉 一次性打卡完成！")
        else:
            print("=" * 50)
            print("❌ 打卡失败，请检查用户信息或网络连接")
        
        print("=" * 50)
        return success

def main():
    """主函数"""
    print("\n🚀 E-Mobile 7 一次性打卡助手")
    print("=" * 60)
    print("💡 用于帮助同事临时打卡，无需配置到服务器")
    print("📍 打卡地点: 武汉光谷（自动定位）")
    print("=" * 60)
    
    try:
        # 获取用户输入
        print("\n📝 请输入打卡信息:")
        username = input("👤 用户名/手机号: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            return
        
        password = input("🔑 密码: ").strip()
        if not password:
            print("❌ 密码不能为空")
            return
        
        print("\n⏰ 请选择打卡类型:")
        print("1. 上班打卡 (on)")
        print("2. 下班打卡 (off)")
        choice = input("请选择 (1或2，默认为2-下班): ").strip()
        
        checkin_type = 'on' if choice == '1' else 'off'
        type_name = '上班' if checkin_type == 'on' else '下班'
        
        print(f"\n🎯 准备为 {username} 执行{type_name}打卡...")
        input("按回车键继续...")
        
        # 执行打卡
        checkin = OneTimeCheckin()
        success = checkin.one_time_checkin(username, password, checkin_type)
        
        if success:
            print(f"\n🎊 恭喜！{username} 的{type_name}打卡已完成")
        else:
            print(f"\n😞 抱歉，{username} 的{type_name}打卡失败")
            print("💡 请检查:")
            print("   - 用户名和密码是否正确")
            print("   - 网络连接是否正常")
            print("   - 是否在正确的打卡时间")
        
    except KeyboardInterrupt:
        print("\n\n👋 用户取消操作")
    except Exception as e:
        print(f"\n❌ 程序异常: {str(e)}")
    
    print("\n👋 感谢使用一次性打卡助手！")

if __name__ == "__main__":
    main()