#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
XTS测试工具主程序

此脚本是XTS测试工具的主入口，用于启动GUI界面，
提供测试执行、配置设置和结果查看等功能。

使用方法：
    python xts_tool.py
"""

import sys
import os
from PyQt5.QtWidgets import QApplication

# 确保能够导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入GUI模块
from ui.main_gui import MainGUI

def main():
    """启动XTS测试工具"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName('XTS测试工具')
    app.setOrganizationName('XTSTester')
    
    # 创建并显示主窗口
    window = MainGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()