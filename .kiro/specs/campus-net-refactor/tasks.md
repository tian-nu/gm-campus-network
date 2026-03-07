# Implementation Plan

- [x] 1. 备份原项目文件并创建新项目结构


  - [x] 1.1 创建 `original/` 目录并移动所有原项目文件


    - 移动 main.py, config.json, requirements.txt, test.py, README.md 等
    - _Requirements: 7.1, 7.3_
  - [x] 1.2 创建新的模块化目录结构



    - 创建 campus_net_auth/, core/, config/, gui/, utils/, tests/ 目录
    - 创建各目录的 __init__.py 文件
    - _Requirements: 5.1, 7.2_

- [x] 2. 实现核心常量和配置模块


  - [x] 2.1 创建 core/constants.py 常量定义


    - 定义 PORTAL_IP, CAS_DOMAIN, TEST_URLS 等网络常量
    - 定义 GUI 相关常量
    - _Requirements: 5.2_
  - [x] 2.2 创建 config/defaults.py 默认配置


    - 定义 DEFAULT_CONFIG 字典
    - _Requirements: 3.2_
  - [x] 2.3 创建 config/manager.py 配置管理器


    - 实现 load(), save(), reset() 方法
    - 实现配置合并逻辑
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 2.4 编写配置管理器属性测试


    - **Property 6: Configuration round-trip**
    - **Property 7: Configuration default merge**
    - **Validates: Requirements 3.2, 3.4, 3.5**


- [x] 3. 实现网络工具模块

  - [x] 3.1 创建 utils/network_info.py 网络信息工具


    - 实现 get_ip_address(), get_mac_address() 方法
    - _Requirements: 5.4_
  - [x] 3.2 创建 utils/logger.py 日志配置


    - 实现 setup_logging() 函数
    - 支持文件和控制台输出
    - _Requirements: 5.5, 6.1_
  - [x] 3.3 编写日志格式属性测试


    - **Property 8: Log entry format**
    - **Validates: Requirements 6.1**

- [x] 4. 实现认证核心模块


  - [x] 4.1 创建 core/authenticator.py 认证器


    - 实现 CampusNetAuthenticator 类
    - 实现 login() 方法和 CAS 认证流程
    - 实现 detect_network_status() 方法
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 4.2 编写认证器属性测试


    - **Property 1: Network detection consistency**
    - **Property 2: Authentication error messages**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 4.3 创建 core/network.py 网络服务

    - 实现心跳保持线程
    - 实现断线重连线程
    - 实现优雅关闭机制
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 4.4 编写网络服务属性测试


    - **Property 3: Heartbeat interval compliance**
    - **Property 4: Reconnect cooldown enforcement**
    - **Property 5: Thread graceful shutdown**
    - **Validates: Requirements 2.1, 2.4, 2.5**

- [x] 5. Checkpoint - 确保核心模块测试通过


  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 实现 GUI 模块


  - [x] 6.1 创建 gui/widgets.py 自定义控件


    - 实现 ScrollableFrame 可滚动框架
    - 实现通用的 LabeledEntry, StatusLabel 等控件
    - _Requirements: 4.1_
  - [x] 6.2 创建 gui/tabs/login.py 登录标签页


    - 实现登录界面布局
    - 实现登录按钮状态管理
    - 实现状态显示区域
    - _Requirements: 4.1, 4.2, 4.3, 4.6_

  - [x] 6.3 创建 gui/tabs/settings.py 设置标签页

    - 实现设置分组布局
    - 实现保存/重置功能
    - _Requirements: 4.4_
  - [x] 6.4 创建 gui/tabs/logs.py 日志标签页


    - 实现日志显示区域
    - 实现清空/保存/打开日志功能
    - _Requirements: 6.2, 6.3, 6.4_
  - [x] 6.5 创建 gui/tray.py 系统托盘


    - 实现最小化到托盘功能
    - 实现托盘菜单
    - _Requirements: 4.5_
  - [x] 6.6 创建 gui/app.py 主应用


    - 整合所有标签页
    - 实现窗口管理和事件处理
    - _Requirements: 4.7_


- [x] 7. 创建应用入口


  - [x] 7.1 创建 main.py 入口文件

    - 初始化日志、配置、认证器
    - 启动 GUI 应用
    - _Requirements: 4.1_
  - [x] 7.2 更新 requirements.txt


    - 添加 hypothesis, pytest 测试依赖
    - 保留原有依赖
    - _Requirements: 5.1_
  - [x] 7.3 创建新的 README.md


    - 更新项目说明和使用方法
    - 说明新的目录结构
    - _Requirements: 5.1_


- [x] 8. Checkpoint - 确保应用可正常运行

  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. 完善测试覆盖


  - [x] 9.1 编写 ConfigManager 单元测试


    - 测试文件不存在的情况
    - 测试 JSON 解析错误的情况
    - _Requirements: 3.3_
  - [x] 9.2 编写 Authenticator 单元测试

    - 测试超时错误处理
    - 测试连接错误处理
    - _Requirements: 1.4, 1.5_
  - [x] 9.3 编写 GUI 组件单元测试


    - 测试登录按钮状态变化
    - 测试日志清空功能
    - _Requirements: 4.2, 6.3_

- [x] 10. Final Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.
