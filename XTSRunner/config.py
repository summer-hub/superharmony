import os
import subprocess
import sys

# 配置路径（Windows环境需修改为实际路径）
DEVECO_DIR = r"D:\huawei\DevEcoStudio5110"
DEVECO_PATH = os.path.join(DEVECO_DIR, r"bin\devecostudio64.exe")

os.environ["PYTHONUNBUFFERED"] = "1"  # 防止终端输出乱码
node_path = os.path.join(r"D:\huawei\command-line-tools\tool\node\node.exe")
hvigor_path = os.path.join(DEVECO_DIR, r"tools\hvigor\bin\hvigorw.js")
npm_path = os.path.join(r"D:\huawei\command-line-tools\tool\node\npm.cmd")
ohpm_path = os.path.join(DEVECO_DIR, r"tools\ohpm\bin\ohpm.bat")

# 报告相关配置
PROJECT_DIR = os.getcwd()
EXCEL_FILE_PATH = os.path.join(PROJECT_DIR, "三方库测试表-部分库.xlsx")
REPORT_DIR = os.path.join(PROJECT_DIR, "results", "test-reports")  # HTML详细报告
ALLURE_RESULTS_DIR = os.path.join(PROJECT_DIR, "results", "allure-results")  # Allure报告
ALLURE_REPORT_DIR = os.path.join(PROJECT_DIR, "results", "allure-report")
HTML_REPORT_DIR = os.path.join(PROJECT_DIR, "results", "html-report")  # HTML总览报告
STATIC_REPORT_DIR = os.path.join(PROJECT_DIR, "results", "allure-report-static")
REPORT_ZIP = os.path.join(PROJECT_DIR, "results", "allure-report-static.zip")
OVERALL_RESULTS_FILE = os.path.join(PROJECT_DIR, "html-report", "overall_results.json")

BUNDLE_NAME_SIG = "cn.openharmony.thrift"
# 添加签名配置
SIGNING_CONFIG_SIG = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001B371411EB0AECFD686E3CB54E5B29DCF5F17745CC96AA17372191C77FB729309862969EFB1DF6DC",
        "profile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.p12",
        "storePassword": "0000001BD66CE64CFBBBC7E00EE55E1A3BC65B60DDEF59D04BD0B0DF00F845E89DA81C05113FC17907258F"
    }
}

BUNDLE_NAME_TPC = "cn.openharmony.mpchart"
# 添加签名配置
SIGNING_CONFIG_TPC = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001BC7F25F48FC9488EDBECC66A9E14258FDA62DEAB81385F289C05B0C87BF4FEB2E593CCA1810471E",
        "profile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.p12",
        "storePassword": "0000001B0F5990A2CCF8E04D97D9C4DB3FDAE2B50BD8B56326275916CD45C6AECEDCB656342C59411DE6CB"
    }
}

BUNDLE_NAME_SAMPLES = "cn.openharmony.box2d"
# 添加签名配置
SIGNING_CONFIG_SAMPLES = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001BB55D1E6B19391DD65C4CDFF9397E543FA281C2F69F0816D4D342824CA4F606B23D1A556F07CE7A",
        "profile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\0419\\XTSTester\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.p12",
        "storePassword": "0000001B4F65AB599FF37812A17702EAA5BCAA7DDFE77CA9829C404B1476B44F2F3B87F93B5BBE8922ADEF"
    }
}

def check_dependencies():
    """检查必要的依赖项是否安装"""
    required = ['git', 'ohpm', 'git']
    for dep in required:
        try:
            subprocess.run([dep, '--version'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        except subprocess.CalledProcessError:
            print(f"错误: {dep} 未正确安装或版本检查失败!")
            sys.exit(1)
        except FileNotFoundError:
            print(f"错误: 找不到{dep}, 请确认已安装并添加到PATH环境变量!")
            sys.exit(1)


# SDK版本与API版本的映射关系
SDK_API_MAPPING = {
    "5.0.0": "12",
    "5.0.1": "13",
    "5.0.2": "14",
    "5.0.3": "15",
    "5.0.4": "16",
    "5.1.0": "18"
}

# 全局变量存储用户选择的SDK版本
selected_sdk_version = None
selected_api_version = None

def set_sdk_version(sdk_version):
    """设置SDK版本和对应的API版本"""
    global selected_sdk_version, selected_api_version
    selected_sdk_version = sdk_version
    selected_api_version = get_api_version(sdk_version)

def get_api_version(sdk_version):
    """根据SDK版本获取对应的API版本号"""
    if sdk_version in SDK_API_MAPPING:
        return SDK_API_MAPPING[sdk_version]
    # 如果找不到对应版本，返回最新版本
    print(f"警告：未找到SDK版本 {sdk_version} 对应的API版本，将使用最新版本")
    return list(SDK_API_MAPPING.values())[-1]


# 添加release模式的全局变量
enable_release_mode = False
def set_release_mode(enable):
    """设置是否启用release模式编译"""
    global enable_release_mode
    enable_release_mode = enable
    print(f"Release模式编译已{'启用' if enable else '禁用'}")

def get_release_mode():
    """获取是否启用release模式编译"""
    return enable_release_mode