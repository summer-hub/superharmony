import os
import subprocess
import sys
import json

# 配置文件路径
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(PROJECT_DIR, "config", "settings.json")

# 默认配置路径（Windows环境）
DEFAULT_DEVECO_DIR = r"D:\huawei\DevEcoStudio5110"
DEFAULT_NODE_PATH = r"D:\huawei\command-line-tools\tool\node\node.exe"
DEFAULT_NPM_PATH = r"D:\huawei\command-line-tools\tool\node\npm.cmd"

# 配置路径（可通过GUI修改）
DEVECO_DIR = DEFAULT_DEVECO_DIR
DEVECO_PATH = os.path.join(DEVECO_DIR, r"bin\devecostudio64.exe")

os.environ["PYTHONUNBUFFERED"] = "1"  # 防止终端输出乱码
os.environ['PYTHONIOENCODING'] = 'utf-8'
node_path = DEFAULT_NODE_PATH
hvigor_path = os.path.join(DEVECO_DIR, r"tools\hvigor\bin\hvigorw.js")
npm_path = DEFAULT_NPM_PATH
ohpm_path = os.path.join(DEVECO_DIR, r"tools\ohpm\bin\ohpm.bat")

# 报告相关配置
EXCEL_FILE_PATH = os.path.join(PROJECT_DIR, "data", "三方库测试表-UI库.xlsx")
REPORT_DIR = os.path.join(PROJECT_DIR, "results", "test-reports")  # HTML详细报告
HTML_REPORT_DIR = os.path.join(PROJECT_DIR, "results", "html-report")  # HTML总览报告
OVERALL_RESULTS_FILE = os.path.join(PROJECT_DIR, "results", "html-report", "overall_results.json")

BUNDLE_NAME_SIG = "cn.openharmony.thrift"
# 添加签名配置
SIGNING_CONFIG_SIG = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001B371411EB0AECFD686E3CB54E5B29DCF5F17745CC96AA17372191C77FB729309862969EFB1DF6DC",
        "profile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_thrift_SNUdGdEm4_e_sD3WVcgiTN_H9x4IrYSdcOrS8IzdwY8=.p12",
        "storePassword": "0000001BD66CE64CFBBBC7E00EE55E1A3BC65B60DDEF59D04BD0B0DF00F845E89DA81C05113FC17907258F"
    }
}

BUNDLE_NAME_TPC = "cn.openharmony.mpchart"
# 添加签名配置
SIGNING_CONFIG_TPC = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001BC7F25F48FC9488EDBECC66A9E14258FDA62DEAB81385F289C05B0C87BF4FEB2E593CCA1810471E",
        "profile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_ohos_mpchart_84LmUC5SeYxhZC7SHANqsLFCw4ZZvNGI2S7yEjGXJxY=.p12",
        "storePassword": "0000001B0F5990A2CCF8E04D97D9C4DB3FDAE2B50BD8B56326275916CD45C6AECEDCB656342C59411DE6CB"
    }
}

BUNDLE_NAME_SAMPLES = "cn.openharmony.box2d"
# 添加签名配置
SIGNING_CONFIG_SAMPLES = {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
        "certpath": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.cer",
        "keyAlias": "debugKey",
        "keyPassword": "0000001BB55D1E6B19391DD65C4CDFF9397E543FA281C2F69F0816D4D342824CA4F606B23D1A556F07CE7A",
        "profile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "D:\\code\\PycharmProjects\\XTSTester-tool\\data\\signconfig\\default_box2d_IkXvxyk9_kPV6wrimrxGH3DN7OeXSVG1pyM1WpsEmMY=.p12",
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
    "5.0.5": "17",
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


# 配置保存和加载功能
def save_config():
    """保存当前配置到配置文件"""
    # 确保配置目录存在
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    # 准备配置数据
    config_data = {
        "deveco_dir": DEVECO_DIR,
        "node_path": node_path,
        "npm_path": npm_path,
        "excel_file_path": EXCEL_FILE_PATH,
        "sdk_version": selected_sdk_version or list(SDK_API_MAPPING.keys())[-1],
        "release_mode": enable_release_mode
    }
    
    # 保存到文件
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)# type: ignore
        print(f"配置已保存到 {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"保存配置失败: {str(e)}")
        return False

def load_config():
    """从配置文件加载配置"""
    global DEVECO_DIR, DEVECO_PATH, node_path, npm_path, hvigor_path, ohpm_path, EXCEL_FILE_PATH
    
    # 检查配置文件是否存在
    if not os.path.exists(CONFIG_FILE):
        print(f"配置文件不存在，将使用默认配置")
        return False
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 更新全局变量
        DEVECO_DIR = config_data.get("deveco_dir", DEFAULT_DEVECO_DIR)
        DEVECO_PATH = os.path.join(DEVECO_DIR, r"bin\devecostudio64.exe")
        node_path = config_data.get("node_path", DEFAULT_NODE_PATH)
        npm_path = config_data.get("npm_path", DEFAULT_NPM_PATH)
        hvigor_path = os.path.join(DEVECO_DIR, r"tools\hvigor\bin\hvigorw.js")
        ohpm_path = os.path.join(DEVECO_DIR, r"tools\ohpm\bin\ohpm.bat")
        EXCEL_FILE_PATH = config_data.get("excel_file_path", os.path.join(PROJECT_DIR, "data", "三方库测试表-UI库.xlsx"))
        
        # 设置SDK版本和Release模式
        sdk_version = config_data.get("sdk_version", list(SDK_API_MAPPING.keys())[-1])
        set_sdk_version(sdk_version)
        
        release_mode = config_data.get("release_mode", False)
        set_release_mode(release_mode)
        
        print(f"已从 {CONFIG_FILE} 加载配置")
        return True
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        return False

# 尝试加载配置文件
try:
    load_config()
except Exception as e:
    print(f"初始化配置时出错: {str(e)}")
    print("将使用默认配置")