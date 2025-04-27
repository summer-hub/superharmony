#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
XTS测试结果可视化工具

此脚本是XTS测试结果可视化工具的主入口，用于启动GUI界面，
方便用户查看和分析测试结果。

使用方法：
    python test_results_viewer.py
"""

import sys
import os
from PyQt5.QtWidgets import QApplication

# 确保能够导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入GUI模块
from ui.test_results_gui import TestResultsGUI

def main():
    """启动测试结果可视化工具"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName('XTS测试结果可视化工具')
    app.setOrganizationName('XTSTester')
    
    # 创建并显示主窗口
    window = TestResultsGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()