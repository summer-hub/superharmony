#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
XTS测试结果可视化工具启动脚本

此脚本用于启动XTS测试结果可视化界面，方便用户查看测试结果。
也可以通过主界面的"查看测试结果"按钮来启动。
"""

import sys
import os
from PyQt5.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入GUI模块
from ui.test_results_gui import TestResultsGUI
from ui.config_gui import show_config_dialog

def main():
    """启动测试结果可视化工具"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName('XTS测试结果可视化工具')
    app.setOrganizationName('XTSTester')
    
    # 检查配置
    from utils import config
    if not os.path.exists(config.DEVECO_DIR) or not os.path.exists(config.EXCEL_FILE_PATH):
        # 显示配置对话框
        if not show_config_dialog():
            return
    
    # 创建并显示主窗口
    window = TestResultsGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()