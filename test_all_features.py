#!/usr/bin/env python3
"""
全面功能测试脚本
测试所有核心功能
"""

import sys
import time
import threading
from unittest.mock import Mock, patch

sys.path.insert(0, '.')

def test_proxy_detection():
    """测试代理检测功能"""
    print("\n" + "=" * 60)
    print("测试1: 代理检测功能")
    print("=" * 60)
    
    from campus_net_auth.utils.network_info import get_proxy_detector
    
    detector = get_proxy_detector()
    result = detector.detect_all()
    
    print(f"✓ 代理检测器创建成功")
    print(f"  - 应该阻止: {result['should_block']}")
    print(f"  - 检测详情:")
    for name, detail in result['details'].items():
        has_proxy = detail.get('has_proxy', False)
        proxies_campus = detail.get('proxies_campus', False)
        status = "🔴 危险" if proxies_campus else ("🟡 有代理" if has_proxy else "🟢 安全")
        print(f"    {name}: {status}")
    
    # 测试校园网模式匹配
    test_cases = [
        ("http://cas.gzittc.com/login", True),
        ("10.10.21.129/portal.do", True),
        ("xykd.gzittc.edu.cn", True),
        ("http://www.baidu.com", False),
    ]
    
    print(f"\n  - 校园网模式匹配测试:")
    all_passed = True
    for url, expected in test_cases:
        result = detector._matches_campus_patterns(url)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"    {status} '{url}' -> {'匹配' if result else '不匹配'} (期望: {'匹配' if expected else '不匹配'})")
    
    return all_passed

def test_authenticator():
    """测试认证器"""
    print("\n" + "=" * 60)
    print("测试2: 认证器功能")
    print("=" * 60)
    
    from campus_net_auth.core.authenticator import CampusNetAuthenticator
    
    config = {
        "timeout": 5,
        "strict_proxy_check": True,
        "mac_address": "00:11:22:33:44:55"
    }
    
    auth = CampusNetAuthenticator(config)
    print(f"✓ 认证器创建成功")
    print(f"  - 超时设置: {auth.timeout}秒")
    print(f"  - 严格代理检测: {config['strict_proxy_check']}")
    print(f"  - 网络信息: {auth.network_info}")
    
    # 测试代理检测阻止登录
    print(f"\n  - 测试代理检测阻止登录:")
    
    # 模拟代理检测返回阻止
    with patch('campus_net_auth.core.authenticator.get_proxy_detector') as mock_get_detector:
        mock_detector = Mock()
        mock_detector.should_block_campus_login.return_value = (True, "检测到Clash代理")
        mock_get_detector.return_value = mock_detector
        
        success, message = auth.login("test_user", "test_pass")
        if not success and "代理" in message:
            print(f"    ✓ 代理检测正确阻止登录")
            print(f"      返回消息: {message[:50]}...")
        else:
            print(f"    ✗ 代理检测未能阻止登录")
            return False
    
    return True

def test_heartbeat_service():
    """测试心跳服务"""
    print("\n" + "=" * 60)
    print("测试3: 心跳服务")
    print("=" * 60)
    
    from campus_net_auth.core.network import HeartbeatService
    
    # 创建心跳服务
    service = HeartbeatService(
        interval=1,
        url="http://127.0.0.1:9999/test",  # 不存在的地址，用于测试
        timeout=1
    )
    
    print(f"✓ 心跳服务创建成功")
    print(f"  - 间隔: {service.interval}秒")
    print(f"  - URL: {service.url}")
    print(f"  - 运行状态: {service.is_running}")
    
    # 测试启动和停止
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        service.start()
        print(f"  - 启动后状态: {service.is_running}")
        
        time.sleep(0.5)
        
        service.stop()
        print(f"  - 停止后状态: {service.is_running}")
    
    return True

def test_reconnect_service():
    """测试重连服务"""
    print("\n" + "=" * 60)
    print("测试4: 重连服务")
    print("=" * 60)
    
    from campus_net_auth.core.network import ReconnectService
    
    # 创建重连服务
    service = ReconnectService(
        check_interval=1,
        cooldown=1,
        network_checker=lambda: True,  # 始终返回网络正常
        login_func=lambda: (True, "OK")
    )
    
    print(f"✓ 重连服务创建成功")
    print(f"  - 检测间隔: {service.check_interval}秒")
    print(f"  - 冷却时间: {service.cooldown}秒")
    print(f"  - 运行状态: {service.is_running}")
    
    # 测试启动和停止
    service.start()
    print(f"  - 启动后状态: {service.is_running}")
    
    time.sleep(0.5)
    
    service.stop()
    print(f"  - 停止后状态: {service.is_running}")
    
    return True

def test_config_manager():
    """测试配置管理器"""
    print("\n" + "=" * 60)
    print("测试5: 配置管理器")
    print("=" * 60)
    
    from campus_net_auth.config.manager import ConfigManager
    import tempfile
    import os
    
    # 使用临时目录测试
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        
        # 创建配置管理器
        manager = ConfigManager()
        manager.config_file = config_path  # 修改配置路径
        
        print(f"✓ 配置管理器创建成功")
        
        # 测试保存配置
        test_config = {
            "username": "test_user",
            "password": "test_pass",
            "auto_login": True,
            "strict_proxy_check": True
        }
        
        manager.save(test_config)
        print(f"  - 配置保存成功")
        
        # 测试加载配置
        loaded = manager.load()
        print(f"  - 配置加载成功")
        print(f"    - 用户名: {loaded.get('username')}")
        print(f"    - 自动登录: {loaded.get('auto_login')}")
        print(f"    - 严格代理检测: {loaded.get('strict_proxy_check')}")
        
        # 验证数据一致性
        if loaded.get('username') == test_config['username']:
            print(f"    ✓ 数据一致性检查通过")
        else:
            print(f"    ✗ 数据一致性检查失败")
            return False
    
    return True

def test_network_info():
    """测试网络信息工具"""
    print("\n" + "=" * 60)
    print("测试6: 网络信息工具")
    print("=" * 60)
    
    from campus_net_auth.utils.network_info import NetworkInfo
    
    # 测试IP获取
    ip = NetworkInfo.get_ip_address()
    print(f"✓ IP地址获取: {ip}")
    
    # 测试MAC获取
    mac = NetworkInfo.get_mac_address()
    print(f"✓ MAC地址获取: {mac}")
    
    # 测试网络信息
    info = NetworkInfo.get_network_info()
    print(f"✓ 完整网络信息:")
    print(f"    - IP: {info['ip']}")
    print(f"    - MAC: {info['mac']}")
    print(f"    - 时间戳: {info['timestamp']}")
    
    # 测试IP验证
    valid_ips = ["192.168.1.1", "10.0.0.1", "255.255.255.255"]
    invalid_ips = ["256.1.1.1", "192.168.1", "abc"]
    
    print(f"\n  - IP验证测试:")
    for ip in valid_ips:
        result = NetworkInfo.is_valid_ip(ip)
        status = "✓" if result else "✗"
        print(f"    {status} {ip} -> {'有效' if result else '无效'}")
    
    for ip in invalid_ips:
        result = NetworkInfo.is_valid_ip(ip)
        status = "✓" if not result else "✗"
        print(f"    {status} {ip} -> {'无效' if not result else '有效'} (期望: 无效)")
    
    return True

def test_constants():
    """测试常量定义"""
    print("\n" + "=" * 60)
    print("测试7: 常量定义")
    print("=" * 60)
    
    from campus_net_auth.core.constants import Constants
    
    print(f"✓ 网络常量:")
    print(f"  - Portal IP: {Constants.PORTAL_IP}")
    print(f"  - CAS域名: {Constants.CAS_DOMAIN}")
    print(f"  - 测试URLs: {len(Constants.TEST_URLS)}个")
    
    print(f"\n✓ GUI常量:")
    print(f"  - 窗口标题: {Constants.WINDOW_TITLE}")
    print(f"  - 窗口大小: {Constants.WINDOW_SIZE}")
    
    print(f"\n✓ 超时和重试:")
    print(f"  - 默认超时: {Constants.DEFAULT_TIMEOUT}秒")
    print(f"  - 默认重试: {Constants.DEFAULT_MAX_RETRIES}次")
    
    print(f"\n✓ 心跳和重连:")
    print(f"  - 心跳间隔: {Constants.DEFAULT_HEARTBEAT_INTERVAL}秒")
    print(f"  - 重连间隔: {Constants.DEFAULT_RECONNECT_INTERVAL}秒")
    
    return True

def test_tray():
    """测试系统托盘"""
    print("\n" + "=" * 60)
    print("测试8: 系统托盘")
    print("=" * 60)
    
    from campus_net_auth.gui.tray import SystemTray, TRAY_AVAILABLE
    
    print(f"✓ 托盘模块加载成功")
    print(f"  - 托盘可用: {TRAY_AVAILABLE}")
    
    tray = SystemTray()
    print(f"  - 托盘实例创建成功")
    print(f"  - 运行状态: {tray.is_running}")
    
    if TRAY_AVAILABLE:
        # 测试启动（不实际显示）
        print(f"\n  - 托盘功能可用，跳过实际显示测试")
        print(f"    如需测试托盘显示，请运行: python test_tray.py")
    else:
        print(f"\n  ⚠️ 托盘不可用，请安装: pip install pystray Pillow")
    
    return True

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("校园网自动认证工具 - 全面功能测试")
    print("=" * 60)
    
    tests = [
        ("代理检测", test_proxy_detection),
        ("认证器", test_authenticator),
        ("心跳服务", test_heartbeat_service),
        ("重连服务", test_reconnect_service),
        ("配置管理", test_config_manager),
        ("网络信息", test_network_info),
        ("常量定义", test_constants),
        ("系统托盘", test_tray),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name}测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，请检查")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
