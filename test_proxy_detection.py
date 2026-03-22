#!/usr/bin/env python3
"""
代理检测功能测试脚本
"""

import sys
sys.path.insert(0, '.')

from campus_net_auth.utils.network_info import get_proxy_detector, ProxyDetector

def test_proxy_detector():
    """测试代理检测器"""
    print("=" * 60)
    print("代理检测功能测试")
    print("=" * 60)

    # 获取检测器实例
    detector = get_proxy_detector()
    print(f"\n1. 检测器实例创建成功: {type(detector).__name__}")

    # 测试校园网模式匹配
    print("\n2. 测试校园网模式匹配:")
    test_cases = [
        "http://cas.gzittc.com/login",
        "10.10.21.129/portal.do",
        "xykd.gzittc.edu.cn",
        "http://www.baidu.com",  # 不应该匹配
        "192.168.1.1",  # 不应该匹配
    ]

    for test in test_cases:
        matches = detector._matches_campus_patterns(test)
        status = "✓ 匹配" if matches else "✗ 不匹配"
        print(f"   '{test}' -> {status}")

    # 执行完整检测
    print("\n3. 执行完整代理检测:")
    result = detector.detect_all()

    print(f"   应该阻止登录: {result['should_block']}")
    print(f"   阻止原因: {result['reason'] if result['reason'] else '无'}")

    print("\n4. 详细检测结果:")
    for name, detail in result['details'].items():
        has_proxy = detail.get('has_proxy', False)
        proxies_campus = detail.get('proxies_campus', False)
        status = "🔴 危险" if proxies_campus else ("🟡 有代理" if has_proxy else "🟢 安全")
        print(f"   {name}: {status}")
        if detail.get('message'):
            print(f"      └─ {detail['message']}")

    # 测试便捷方法
    print("\n5. 测试便捷方法 should_block_campus_login():")
    should_block, reason = detector.should_block_campus_login()
    print(f"   应该阻止: {should_block}")
    print(f"   原因: {reason if reason else '无'}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_proxy_detector()
