"""
GUI 组件测试
测试 GUI 控件的基本功能
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 跳过 GUI 测试如果没有显示器
try:
    from tkinter import Tk, END
    HAS_DISPLAY = True
except Exception:
    HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(not HAS_DISPLAY, reason="No display available")


class TestWidgets:
    """控件测试"""

    @pytest.fixture
    def root(self):
        """创建测试用根窗口"""
        root = Tk()
        root.withdraw()  # 隐藏窗口
        yield root
        root.destroy()

    def test_labeled_entry(self, root):
        """测试 LabeledEntry 控件"""
        from campus_net_auth.gui.widgets import LabeledEntry

        entry = LabeledEntry(root, label_text="测试:")
        entry.pack()

        # 测试设置和获取值
        entry.set("test_value")
        assert entry.get() == "test_value"

        # 测试空值
        entry.set("")
        assert entry.get() == ""

    def test_status_label(self, root):
        """测试 StatusLabel 控件"""
        from campus_net_auth.gui.widgets import StatusLabel

        label = StatusLabel(root, label_text="状态:", initial_text="未知")
        label.pack()

        # 测试设置状态
        label.set_status("已连接", "green")
        assert label.value_label.cget("text") == "已连接"
        assert label.value_label.cget("fg") == "green"

        # 测试预设状态
        label.set_connected()
        assert label.value_label.cget("text") == "已连接"

        label.set_disconnected()
        assert label.value_label.cget("text") == "未连接"

        label.set_unknown()
        assert label.value_label.cget("text") == "未知"

    def test_setting_checkbox(self, root):
        """测试 SettingCheckbox 控件"""
        from campus_net_auth.gui.widgets import SettingCheckbox

        checkbox = SettingCheckbox(root, text="测试选项")
        checkbox.pack()

        # 测试默认值
        assert checkbox.get() is False

        # 测试设置值
        checkbox.set(True)
        assert checkbox.get() is True

        checkbox.set(False)
        assert checkbox.get() is False

    def test_setting_spinbox(self, root):
        """测试 SettingSpinbox 控件"""
        from campus_net_auth.gui.widgets import SettingSpinbox

        spinbox = SettingSpinbox(
            root,
            label_text="数值:",
            min_val=0,
            max_val=100,
            default_val=50
        )
        spinbox.pack()

        # 测试默认值
        assert spinbox.get() == 50

        # 测试设置值
        spinbox.set(75)
        assert spinbox.get() == 75

    def test_action_button(self, root):
        """测试 ActionButton 控件"""
        from campus_net_auth.gui.widgets import ActionButton

        clicked = []

        def on_click():
            clicked.append(True)

        button = ActionButton(root, text="测试", command=on_click, style="primary")
        button.pack()

        # 测试加载状态
        button.set_loading(True, "加载中...")
        assert button.cget("state") == "disabled"
        assert button.cget("text") == "加载中..."

        button.set_loading(False)
        assert button.cget("state") == "normal"
        assert button.cget("text") == "测试"


class TestLoginTab:
    """登录标签页测试"""

    @pytest.fixture
    def root(self):
        """创建测试用根窗口"""
        root = Tk()
        root.withdraw()
        yield root
        root.destroy()

    def test_login_tab_creation(self, root):
        """测试登录标签页创建"""
        from campus_net_auth.gui.tabs.login import LoginTab

        tab = LoginTab(root)
        tab.pack()

        # 验证控件存在
        assert tab.username_entry is not None
        assert tab.password_entry is not None
        assert tab.login_btn is not None

    def test_set_credentials(self, root):
        """测试设置凭证"""
        from campus_net_auth.gui.tabs.login import LoginTab

        tab = LoginTab(root)
        tab.pack()

        tab.set_credentials("test_user", "test_pass")

        username, password = tab.get_credentials()
        assert username == "test_user"
        assert password == "test_pass"

    def test_update_network_status(self, root):
        """测试更新网络状态"""
        from campus_net_auth.gui.tabs.login import LoginTab

        tab = LoginTab(root)
        tab.pack()

        tab.update_network_status(True)
        assert tab.network_status.value_label.cget("text") == "已连接"

        tab.update_network_status(False)
        assert tab.network_status.value_label.cget("text") == "未连接"


class TestLogsTab:
    """日志标签页测试"""

    @pytest.fixture
    def root(self):
        """创建测试用根窗口"""
        root = Tk()
        root.withdraw()
        yield root
        root.destroy()

    def test_logs_tab_creation(self, root):
        """测试日志标签页创建"""
        from campus_net_auth.gui.tabs.logs import LogsTab

        tab = LogsTab(root)
        tab.pack()

        assert tab.log_text is not None

    def test_append_log(self, root):
        """测试添加日志"""
        from campus_net_auth.gui.tabs.logs import LogsTab

        tab = LogsTab(root)
        tab.pack()

        tab.append_log("Test log message\n")

        content = tab.get_log_content()
        assert "Test log message" in content

    def test_clear_log_content(self, root):
        """测试清空日志内容（不弹窗）"""
        from campus_net_auth.gui.tabs.logs import LogsTab

        tab = LogsTab(root)
        tab.pack()

        # 添加日志
        tab.append_log("Test message\n")

        # 直接清空（不通过按钮，避免弹窗）
        tab.log_text.config(state="normal")
        tab.log_text.delete("1.0", END)
        tab.log_text.config(state="disabled")

        content = tab.get_log_content()
        assert content.strip() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
