"""
配置管理器测试
包含属性测试和单元测试
"""

import json
import os
import tempfile
import pytest
from hypothesis import given, strategies as st, settings

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campus_net_auth.config.manager import ConfigManager
from campus_net_auth.config.defaults import DEFAULT_CONFIG, AppConfig


class TestConfigManagerProperties:
    """配置管理器属性测试"""

    @given(st.dictionaries(
        keys=st.sampled_from(list(DEFAULT_CONFIG.keys())),
        values=st.one_of(
            st.text(max_size=100),
            st.integers(min_value=0, max_value=1000),
            st.booleans()
        ),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_config_round_trip(self, partial_config):
        """
        **Feature: campus-net-refactor, Property 6: Configuration round-trip**
        **Validates: Requirements 3.4, 3.5**

        For any valid configuration dictionary, saving it to JSON and then
        loading it back should produce an equivalent configuration.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        try:
            manager = ConfigManager(temp_file)

            # 创建完整配置
            full_config = DEFAULT_CONFIG.copy()
            full_config.update(partial_config)

            # 保存配置
            assert manager.save(full_config) is True

            # 重新加载
            loaded_config = manager.load()

            # 验证所有原始键值都被保留
            for key, value in full_config.items():
                assert key in loaded_config, f"Key '{key}' missing after round-trip"
                assert loaded_config[key] == value, f"Value mismatch for key '{key}'"

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    @given(st.dictionaries(
        keys=st.sampled_from(list(DEFAULT_CONFIG.keys())[:5]),
        values=st.one_of(
            st.text(max_size=50),
            st.integers(min_value=0, max_value=100),
            st.booleans()
        ),
        min_size=0,
        max_size=3
    ))
    @settings(max_examples=100)
    def test_config_default_merge(self, partial_config):
        """
        **Feature: campus-net-refactor, Property 7: Configuration default merge**
        **Validates: Requirements 3.2**

        For any partial configuration (missing some keys), loading it should
        produce a complete configuration with missing keys filled from defaults.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        try:
            # 写入部分配置
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(partial_config, f)

            manager = ConfigManager(temp_file)
            loaded_config = manager.load()

            # 验证所有默认键都存在
            for key in DEFAULT_CONFIG.keys():
                assert key in loaded_config, f"Default key '{key}' missing after merge"

            # 验证用户配置覆盖了默认值
            for key, value in partial_config.items():
                assert loaded_config[key] == value, f"User value for '{key}' not preserved"

            # 验证缺失的键使用默认值
            for key in DEFAULT_CONFIG.keys():
                if key not in partial_config:
                    assert loaded_config[key] == DEFAULT_CONFIG[key], \
                        f"Default value for '{key}' not applied"

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestConfigManagerUnit:
    """配置管理器单元测试"""

    def test_load_nonexistent_file(self):
        """测试加载不存在的配置文件"""
        manager = ConfigManager("nonexistent_config_12345.json")
        config = manager.load()

        # 应该返回默认配置
        assert config == DEFAULT_CONFIG

    def test_load_corrupted_json(self):
        """测试加载损坏的 JSON 文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_file = f.name

        try:
            manager = ConfigManager(temp_file)
            config = manager.load()

            # 应该返回默认配置
            assert config == DEFAULT_CONFIG
        finally:
            os.unlink(temp_file)

    def test_save_and_load(self):
        """测试保存和加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        try:
            manager = ConfigManager(temp_file)

            test_config = {
                "username": "test_user",
                "password": "test_pass",
                "timeout": 15,
                "enable_heartbeat": False,
            }

            # 保存
            assert manager.save(test_config) is True

            # 加载
            loaded = manager.load()

            # 验证
            assert loaded["username"] == "test_user"
            assert loaded["password"] == "test_pass"
            assert loaded["timeout"] == 15
            assert loaded["enable_heartbeat"] is False

        finally:
            os.unlink(temp_file)

    def test_reset_config(self):
        """测试重置配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        try:
            manager = ConfigManager(temp_file)

            # 先保存自定义配置
            custom_config = {"username": "custom", "timeout": 99}
            manager.save(custom_config)

            # 重置
            reset_config = manager.reset()

            # 验证重置为默认值
            assert reset_config == DEFAULT_CONFIG

            # 验证文件也被更新
            loaded = manager.load()
            assert loaded["username"] == ""
            assert loaded["timeout"] == 10

        finally:
            os.unlink(temp_file)

    def test_get_and_set(self):
        """测试 get 和 set 方法"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        try:
            manager = ConfigManager(temp_file)

            # 测试 get 默认值
            assert manager.get("nonexistent_key", "default") == "default"

            # 测试 set
            assert manager.set("username", "new_user") is True
            assert manager.get("username") == "new_user"

        finally:
            os.unlink(temp_file)


class TestAppConfig:
    """AppConfig 数据类测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        config = AppConfig(username="test", timeout=20)
        d = config.to_dict()

        assert d["username"] == "test"
        assert d["timeout"] == 20
        assert "enable_heartbeat" in d

    def test_from_dict(self):
        """测试从字典创建"""
        data = {"username": "test", "timeout": 20, "unknown_field": "ignored"}
        config = AppConfig.from_dict(data)

        assert config.username == "test"
        assert config.timeout == 20
        # unknown_field 应该被忽略
        assert not hasattr(config, "unknown_field")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
