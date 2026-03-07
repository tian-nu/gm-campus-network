"""
配置管理器
负责配置的加载、保存、合并和验证
"""

import json
import logging
import os
import sys
import winreg
from datetime import datetime, timedelta
from typing import Optional

from .defaults import DEFAULT_CONFIG, AppConfig


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        self._config: Optional[dict] = None

    def load(self) -> dict:
        """
        加载配置，自动合并默认值

        Returns:
            完整的配置字典
        """
        try:
            if not os.path.exists(self.config_file):
                self.logger.info(f"配置文件不存在，使用默认配置: {self.config_file}")
                return DEFAULT_CONFIG.copy()

            with open(self.config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # 合并配置（确保所有默认键都存在）
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)

            self._config = config
            self.logger.debug(f"配置加载成功: {self.config_file}")
            return config

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件 JSON 解析错误，使用默认配置: {e}")
            return DEFAULT_CONFIG.copy()
        except Exception as e:
            self.logger.error(f"加载配置失败，使用默认配置: {e}")
            return DEFAULT_CONFIG.copy()

    def save(self, config: dict) -> bool:
        """
        保存配置到文件

        Args:
            config: 配置字典

        Returns:
            是否保存成功
        """
        try:
            # 确保配置目录存在
            config_dir = os.path.dirname(self.config_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self._config = config
            self.logger.info(f"配置已保存: {self.config_file}")
            return True

        except PermissionError as e:
            self.logger.error(f"保存配置失败，权限不足: {e}")
            return False
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False

    def reset(self) -> dict:
        """
        重置为默认配置

        Returns:
            默认配置字典
        """
        config = DEFAULT_CONFIG.copy()
        self.save(config)
        self.logger.info("配置已重置为默认值")
        return config

    def get(self, key: str, default=None):
        """
        获取配置项

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        if self._config is None:
            self._config = self.load()
        return self._config.get(key, default)

    def set(self, key: str, value) -> bool:
        """
        设置配置项

        Args:
            key: 配置键
            value: 配置值

        Returns:
            是否设置成功
        """
        if self._config is None:
            self._config = self.load()
        self._config[key] = value
        return self.save(self._config)

    def clean_old_logs(self, log_file: str = "campus_net.log", retention_days: int = 7) -> None:
        """
        清理过期日志

        Args:
            log_file: 日志文件路径
            retention_days: 日志保留天数
        """
        try:
            if not os.path.exists(log_file):
                return

            file_stats = os.stat(log_file)
            file_age = datetime.now() - datetime.fromtimestamp(file_stats.st_mtime)

            if file_age > timedelta(days=retention_days):
                # 备份旧日志
                backup_name = f"{log_file}.{datetime.now().strftime('%Y%m%d')}"
                os.rename(log_file, backup_name)
                self.logger.info(f"已备份旧日志到: {backup_name}")

                # 创建新日志文件
                open(log_file, "w", encoding="utf-8").close()
                self.logger.info("已创建新日志文件")

        except Exception as e:
            self.logger.error(f"清理日志失败: {e}")

    def to_app_config(self) -> AppConfig:
        """
        转换为 AppConfig 数据类

        Returns:
            AppConfig 实例
        """
        if self._config is None:
            self._config = self.load()
        return AppConfig.from_dict(self._config)

    def set_startup(self, enable: bool) -> bool:
        """
        设置开机自启动

        Args:
            enable: 是否启用开机自启

        Returns:
            是否设置成功
        """
        try:
            # 获取当前可执行文件路径
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的 exe
                exe_path = sys.executable
            else:
                # 开发环境，使用 pythonw.exe 运行 main.py
                exe_path = f'"{sys.executable}" "{os.path.abspath("main.py")}"'

            app_name = "CampusNetAuth"
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

            # 打开注册表
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )

            if enable:
                # 添加开机自启
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                self.logger.info(f"已启用开机自启: {exe_path}")
            else:
                # 移除开机自启
                try:
                    winreg.DeleteValue(key, app_name)
                    self.logger.info("已禁用开机自启")
                except FileNotFoundError:
                    # 键不存在，忽略
                    pass

            winreg.CloseKey(key)
            return True

        except PermissionError as e:
            self.logger.error(f"设置开机自启失败，权限不足: {e}")
            return False
        except Exception as e:
            self.logger.error(f"设置开机自启失败: {e}")
            return False

    def is_startup_enabled(self) -> bool:
        """
        检查是否已启用开机自启

        Returns:
            是否已启用
        """
        try:
            app_name = "CampusNetAuth"
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_QUERY_VALUE
            )

            try:
                winreg.QueryValueEx(key, app_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False

        except Exception as e:
            self.logger.debug(f"检查开机自启状态失败: {e}")
            return False
