#!/usr/bin/env python3
"""
直接运行主程序
"""

import sys
sys.path.insert(0, '.')

from tkinter import Tk
from campus_net_auth.gui.app import CampusNetApp

if __name__ == "__main__":
    root = Tk()
    app = CampusNetApp(root)
    app.run()
