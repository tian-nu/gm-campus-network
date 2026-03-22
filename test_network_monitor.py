#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络监听器测试脚本
测试网络变化监听功能
"""

import sys
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 添加项目路径
sys.path.insert(0, r'd:\PYC项目\自动登录工贸校园网')

from campus_net_auth.utils.network_monitor import (
    NetworkMonitor, NetworkEventHandler, NetworkEvent, NetworkEventType
)


def on_network_event(event: NetworkEvent) -> None:
    """网络事件回调"""
    print(f"\n[事件] {event.event_type.name}")
    print(f"  时间: {time.strftime('%H:%M:%S', time.localtime(event.timestamp))}")
    if event.old_value:
        print(f"  旧值: {event.old_value}")
    if event.new_value:
        print(f"  新值: {event.new_value}")
    if event.details:
        print(f"  详情: {event.details}")
    print()


def test_network_monitor():
    """测试网络监听器"""
    print("=" * 50)
    print("网络监听器测试")
    print("=" * 50)
    print("\n功能测试:")
    print("1. IP地址变化检测")
    print("2. 网卡切换检测（有线/无线）")
    print("3. 网络连接状态变化")
    print("4. 网关变化检测")
    print("5. 系统休眠/唤醒检测")
    print("\n请尝试以下操作来测试:")
    print("- 切换网络（有线<->无线）")
    print("- 断开/连接网络")
    print("- 让系统进入休眠再唤醒")
    print("\n按 Ctrl+C 停止测试\n")

    # 创建网络监听器
    monitor = NetworkMonitor(
        on_event=on_network_event,
        check_interval=2.0  # 2秒检测一次
    )

    # 创建事件处理器
    handler = NetworkEventHandler(
        on_reconnect_required=lambda: print("[动作] 触发重新连接！")
    )

    # 启动监听器
    monitor.start()

    try:
        # 持续运行，等待事件
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n停止测试...")
    finally:
        monitor.stop()

    # 打印统计
    stats = handler.get_stats()
    print("\n事件统计:")
    print(f"  总事件数: {stats['total_events']}")
    for event_type, count in stats['event_stats'].items():
        print(f"  {event_type}: {count}")


def test_network_info():
    """测试网络信息获取"""
    print("\n" + "=" * 50)
    print("网络信息获取测试")
    print("=" * 50 + "\n")

    monitor = NetworkMonitor()

    print(f"当前IP地址: {monitor._get_current_ip()}")
    print(f"主网卡: {monitor._get_primary_adapter()}")
    print(f"所有网卡: {monitor._get_all_adapters()}")
    print(f"默认网关: {monitor._get_default_gateway()}")
    print(f"网络连通性: {'已连接' if monitor._check_internet_connectivity() else '未连接'}")


if __name__ == "__main__":
    # 先测试网络信息获取
    test_network_info()

    # 然后测试网络监听
    print("\n")
    test_network_monitor()
