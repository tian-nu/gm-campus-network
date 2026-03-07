# Requirements Document

## Introduction

本项目是对现有校园网自动认证工具的重构优化。原项目是一个单文件 Python 应用（1600+ 行），功能包括校园网 CAS 认证、心跳保持、断线重连和 GUI 界面。重构目标是将代码模块化、提升可维护性、增强健壮性，并保持所有现有功能完全可用。

## Glossary

- **CAS**: Central Authentication Service，中央认证服务，校园网使用的单点登录系统
- **Portal**: 校园网认证门户页面
- **Heartbeat**: 心跳保持，定期发送网络请求以维持连接状态
- **Reconnect**: 断线重连，检测网络断开后自动重新登录
- **Authenticator**: 认证器，负责执行登录认证流程的核心组件
- **ConfigManager**: 配置管理器，负责加载和保存用户配置
- **NetworkInfo**: 网络信息，包括 IP 地址和 MAC 地址

## Requirements

### Requirement 1

**User Story:** As a student, I want to automatically authenticate to the campus network, so that I can access the internet without manual login each time.

#### Acceptance Criteria

1. WHEN the user clicks the login button with valid credentials THEN the Authenticator SHALL complete the CAS authentication flow and establish network connectivity
2. WHEN the network is already connected THEN the Authenticator SHALL detect this state and skip the authentication process
3. WHEN authentication fails due to invalid credentials THEN the Authenticator SHALL return a clear error message indicating the failure reason
4. WHEN authentication fails due to network timeout THEN the Authenticator SHALL return a timeout error message within the configured timeout period
5. IF the CAS login page cannot be reached THEN the Authenticator SHALL return a connection error message

### Requirement 2

**User Story:** As a user, I want the application to maintain my network connection, so that I don't get disconnected during use.

#### Acceptance Criteria

1. WHEN heartbeat is enabled THEN the Authenticator SHALL send periodic requests at the configured interval
2. WHEN the heartbeat detects network disconnection THEN the Authenticator SHALL log the disconnection event
3. WHEN reconnect is enabled and network disconnects THEN the Authenticator SHALL attempt to re-authenticate automatically
4. WHEN reconnect attempts fail THEN the Authenticator SHALL wait for the configured cooldown period before retrying
5. WHILE heartbeat or reconnect threads are running THEN the Authenticator SHALL allow graceful shutdown when stop is requested

### Requirement 3

**User Story:** As a user, I want to save my login credentials and settings, so that I don't have to re-enter them each time.

#### Acceptance Criteria

1. WHEN the user saves configuration THEN the ConfigManager SHALL persist all settings to a JSON file
2. WHEN the application starts THEN the ConfigManager SHALL load existing configuration and merge with default values
3. WHEN the configuration file is corrupted or missing THEN the ConfigManager SHALL use default configuration values
4. WHEN serializing configuration to JSON THEN the ConfigManager SHALL produce valid JSON that can be deserialized back to equivalent configuration
5. WHEN deserializing configuration from JSON THEN the ConfigManager SHALL restore the original configuration values

### Requirement 4

**User Story:** As a user, I want a modern and intuitive graphical interface, so that I can easily manage network authentication with a pleasant user experience.

#### Acceptance Criteria

1. WHEN the application starts THEN the GUI SHALL display a clean, modern login interface with clearly labeled username and password fields
2. WHEN the user clicks login THEN the GUI SHALL disable the login button, show a loading indicator, and prevent duplicate submissions
3. WHEN login completes THEN the GUI SHALL re-enable the login button and display the result with appropriate visual feedback (success/error colors)
4. WHEN the user navigates to settings THEN the GUI SHALL organize options into logical groups with clear labels
5. WHEN the user clicks minimize to tray THEN the GUI SHALL hide the main window and show a system tray icon with context menu
6. WHEN displaying status information THEN the GUI SHALL use color-coded indicators (green for connected, red for disconnected)
7. WHEN the window is resized THEN the GUI SHALL adapt layout responsively without breaking visual elements

### Requirement 5

**User Story:** As a developer, I want the code to be modular and well-organized, so that it is easy to maintain and extend.

#### Acceptance Criteria

1. WHEN organizing the codebase THEN the project SHALL separate concerns into distinct modules (core, gui, utils, config)
2. WHEN implementing the authenticator THEN the Authenticator SHALL be independent of GUI code
3. WHEN implementing configuration THEN the ConfigManager SHALL be reusable across different interfaces
4. WHEN implementing network utilities THEN the NetworkInfo module SHALL provide standalone functions for IP and MAC retrieval
5. WHEN implementing logging THEN the logging module SHALL be configurable and consistent across all components

### Requirement 6

**User Story:** As a user, I want to view application logs, so that I can troubleshoot issues when they occur.

#### Acceptance Criteria

1. WHEN the application performs actions THEN the Logger SHALL record events with timestamps and severity levels
2. WHEN the user views the log tab THEN the GUI SHALL display recent log entries in a scrollable text area
3. WHEN the user clicks clear log THEN the GUI SHALL remove all entries from the log display
4. WHEN the user clicks save log THEN the GUI SHALL export log content to a user-specified file
5. WHEN auto-clean is enabled THEN the ConfigManager SHALL archive logs older than the retention period

### Requirement 7

**User Story:** As a user, I want the original project files preserved, so that I can reference or rollback if needed.

#### Acceptance Criteria

1. WHEN starting the refactor THEN the system SHALL move all original files to an `original/` subdirectory
2. WHEN creating the new project structure THEN the system SHALL place new files in the root directory with clear module organization
3. WHEN the refactor is complete THEN the original files SHALL remain intact in the `original/` directory
