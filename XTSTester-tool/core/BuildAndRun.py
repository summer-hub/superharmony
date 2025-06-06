import json5
import os
import shutil
import subprocess
import re
import time
from colorama import  Fore
from reports.ExtractTestDetails import extract_test_details, display_test_details
from core.ModifyConfig import _run_config_scripts, _determine_repo_type_and_config
from reports.ReportGenerator import generate_reports
from utils.config import PROJECT_DIR, ohpm_path, node_path, hvigor_path, get_release_mode
from core.ReadExcel import get_repo_info


def clone_and_build(library_name):
    # Pass library_name to _determine_repo_type_and_config
    repo_type, signing_config, BUNDLE_NAME = _determine_repo_type_and_config(library_name)
    """克隆仓库并构建项目，返回测试结果"""
    try:
        # 准备工作
        os.environ["GIT_CLONE_PROTECTION_ACTIVE"] = "false"
        
        # 从ReadExcel获取仓库信息
        owner, name, sub_dir = get_repo_info(library_name)
        print(f"获取到仓库信息: owner={owner}, name={name}, sub_dir={sub_dir}")
        
        # 1. 创建并进入Libraries目录
        libraries_dir = os.path.abspath(os.path.join(os.getcwd(), "Libraries"))
        os.makedirs(libraries_dir, exist_ok=True)
        os.chdir(libraries_dir)
        
        # 2. 克隆或更新仓库
        _clone_repo(library_name)
        
        # 3. 进入项目目录
        # 特殊处理aki库，需要进入到特定的单元测试目录
        if name == "aki":
            target_dir = os.path.join(name, "test", "platform", "ohos", "unittests")
            print(Fore.YELLOW + f"检测到aki库，将进入特定目录: {target_dir}" + Fore.RESET)
        else:
            target_dir = name if not sub_dir else os.path.join(name, sub_dir)
            
        if not os.path.exists(target_dir):
            raise FileNotFoundError(f"目标目录 {target_dir} 不存在")
            
        os.chdir(target_dir)
        print(f"当前工作目录: {os.getcwd()}")

        # 6.启动DevEco Studio
        # _start_deveco_studio()

        # 7.执行配置脚本
        _run_config_scripts(library_name) # Pass library_name here

        # 8.安装ohpm依赖
        _install_ohpm_dependencies()

        # 根据用户选择决定是否执行release模式编译

        if get_release_mode():
            print(Fore.YELLOW + "正在执行release模式编译..." + Fore.RESET)
            _build_release()
        else:
            print(Fore.YELLOW + "执行debug模式编译..." + Fore.RESET)
            # 检查并确保混淆规则文件包含必要的-keep规则
            obfuscation_file = os.path.join("entry", "obfuscation-rules.txt")
            if os.path.exists(obfuscation_file):
                with open(obfuscation_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 获取当前库的依赖项
                dependencies = _get_ohos_name(library_name)
                
                # 检查是否已包含必要的-keep规则
                needs_update = False
                for dep in dependencies:
                    if f"-keep ./oh_modules/{dep}" not in content:
                        needs_update = True
                        break
                
                if needs_update:
                    print(Fore.YELLOW + "添加必要的-keep规则到混淆文件..." + Fore.RESET)
                    with open(obfuscation_file, 'a', encoding='utf-8') as f:
                        for dep in dependencies:
                            f.write(f"\n-keep\n./oh_modules/{dep}\n")
            
            # 执行debug模式构建
            subprocess.run([
                node_path,
                hvigor_path,
                "--sync",
                "-p", "product=default",
                "-p", "buildMode=debug",
                "--analyze=normal",
                "--parallel",
                "--incremental",
                "--daemon"
            ], check=True)

        # 9.构建项目
        _build_project()

        # 10.运行Hap
        # run_hap()

        # 11.运行XTS并获取测试结果
        test_names = extract_test_names()
        if test_names:
            # 调用run_xts函数执行测试，并传入test_names
            output = run_xts(library_name, test_names)
            extracted_data = extract_test_details(output)
            return extracted_data
        else:
            print(Fore.RED + "未找到可执行的测试用例" + Fore.RESET)
            # 修改为返回error状态
            return {"test_results": {"ErrorTestClass": [{"name": "noTestsFound", "status": "error", "time": "1ms", "error_message": "未找到可执行的测试用例"}]},
                    "summary": {"total": 1, "passed": 0, "failed": 0, "error": 1, "ignored": 0, "total_time_ms": 1},
                    "class_times": {"ErrorTestClass": 1}}

    except subprocess.CalledProcessError as e:
        print(f"执行命令失败: {e}")
        # 修改为返回error状态而非passed状态
        return {"test_results": {"ErrorTestClass": [{"name": "errorTest", "status": "error", "time": "1ms", "error_message": str(e)}]},
                "summary": {"total": 1, "passed": 0, "failed": 0, "error": 1, "ignored": 0, "total_time_ms": 1},
                "class_times": {"ErrorTestClass": 1}}
    finally:
        # Return to original working directory
        os.chdir(PROJECT_DIR)



def _install_ohpm_dependencies():
    """安装ohpm依赖"""
    ohpm_registries = "https://ohpm.openharmony.cn/ohpm/"
    subprocess.run([ohpm_path, "install", "--all", "--registry", ohpm_registries, "--strict_ssl", "false"],
                   check=True)

def _build_project():
    """构建项目"""
    # 并行构建参数
    build_args = ["--analyze=normal", "--parallel", "--incremental"]

    # 同步项目
    subprocess.run([node_path, hvigor_path,
                    "--sync",
                    "-p", "product=default",
                    *build_args,
                    "--no-daemon",
                    ], check=True)

    # 检查项目结构，确定是否存在sharedLibrary模块
    has_shared_library = os.path.exists("sharedlibrary") or os.path.exists("sharedLibrary")
    shared_library_name = None
    
    # 确定正确的sharedLibrary目录名称（大小写敏感）
    if os.path.exists("sharedlibrary"):
        shared_library_name = "sharedlibrary"
    elif os.path.exists("sharedLibrary"):
        shared_library_name = "sharedLibrary"
    
    print(f"检测到{'存在' if has_shared_library else '不存在'} sharedLibrary 模块")

    # 根据项目结构选择构建命令
    if has_shared_library:
        # 构建包含sharedLibrary的项目
        try:
            subprocess.run([node_path, hvigor_path,
                            "--mode", "module",
                            "-p", f"module=entry@default,{shared_library_name}@default",
                            "-p", "product=default",
                            "-p", "requireDeviceType=phone",
                            "assembleHap", "assembleHsp", *build_args, "--daemon"
                            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"警告: 构建sharedLibrary模块失败: {e}")
            print("尝试仅构建entry模块...")
            subprocess.run([node_path, hvigor_path,
                            "--mode", "module",
                            "-p", "module=entry@default",
                            "-p", "product=default",
                            "-p", "requireDeviceType=phone",
                            "assembleHap", *build_args, "--daemon"
                            ], check=True)
    else:
        # 构建不包含sharedLibrary的项目
        subprocess.run([node_path, hvigor_path,
                        "--mode", "module",
                        "-p", "product=default",
                        "assembleHap", *build_args, "--daemon"
                        ], check=True)

def _get_ohos_name(library_name):
    """获取oh-package.json5中的主模块名称"""
    try:
        # 处理字典类型的库名参数
        actual_library_name = library_name
        if isinstance(library_name, dict) and 'name' in library_name:
            actual_library_name = library_name['name']
        elif isinstance(library_name, dict):
            # 如果是字典但没有'name'键，可能无法处理，返回空字符串或记录错误
            print(f"警告：接收到字典类型的库名但缺少'name'键: {library_name}")
            return ""

        # 特殊库处理 - 可以在这里添加特殊库的路径
        special_libs = {
            "aki": "platform/ohos/publish/aki/oh-package.json5"
        }
        
        # 确定oh-package.json5路径
        # 使用处理后的 actual_library_name 进行判断和路径拼接
        if actual_library_name in special_libs:
            package_path = os.path.join(os.getcwd(), special_libs[actual_library_name])
        else:
            package_path = os.path.join(os.getcwd(), "oh-package.json5")
            
        if not os.path.exists(package_path):
            # 如果默认路径不存在，尝试在库名目录下查找
            lib_dir_package_path = os.path.join(os.getcwd(), actual_library_name, "oh-package.json5")
            if os.path.exists(lib_dir_package_path):
                package_path = lib_dir_package_path
            else:
                print(f"警告：在 {os.getcwd()} 或 {os.path.join(os.getcwd(), actual_library_name)} 中都找不到 oh-package.json5")
                return ""
            
        with open(package_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 解析主模块名称
        main_pattern = r'"name":\s*"(@ohos/[a-zA-Z0-9_-]+)"'
        match = re.search(main_pattern, content)
        
        return match.group(1) if match else ""
        
    except Exception as e:
        print(f"获取oh-package.json5主模块名称失败: {e}")
        return ""

def _build_release():
    """构建项目为release模式"""
    try:
        # 1. 检查并修改混淆规则文件
        obfuscation_file = os.path.join("entry", "obfuscation-rules.txt")
        if os.path.exists(obfuscation_file):
            with open(obfuscation_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            modified = False
            new_lines = []
            i = 0
            while i < len(lines):
                if (isinstance(lines[i], str) and lines[i].strip() == "-keep" and 
                    i+1 < len(lines) and 
                    isinstance(lines[i+1], str) and 
                    lines[i+1].strip().startswith("./oh_modules/@ohos/")):
                    # Skip both lines
                    i += 2
                    modified = True
                else:
                    new_lines.append(lines[i])
                    i += 1
            
            if modified:
                with open(obfuscation_file, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(Fore.YELLOW + "已移除obfuscation-rules.txt中的特定规则" + Fore.RESET)

        # 2. release模式构建
        try:
            subprocess.run([
                node_path,
                hvigor_path,
                "--sync",
                "-p", "product=default",
                "-p", "buildMode=release",
                "--analyze=normal",
                "--parallel",
                "--incremental",
                "--daemon"
            ], check=True)
        except subprocess.CalledProcessError as build_error:
            # 检查错误信息是否包含armeabi-v7a不支持的提示
            error_output = str(build_error.stderr) if build_error.stderr else ""
            if "armeabi-v7a" in error_output or "armeabi-v7a" in str(build_error):
                print(Fore.YELLOW + "检测到armeabi-v7a不支持错误，尝试自动修复..." + Fore.RESET)
                # 导入并调用_comment_armeabi_v7函数
                from ModifyConfig import _comment_armeabi_v7
                _comment_armeabi_v7()
                # 重新尝试构建
                print(Fore.YELLOW + "正在重新尝试构建..." + Fore.RESET)
                subprocess.run([
                    node_path,
                    hvigor_path,
                    "--sync",
                    "-p", "product=default",
                    "-p", "buildMode=release",
                    "--analyze=normal",
                    "--parallel",
                    "--incremental",
                    "--daemon"
                ], check=True)
            else:
                # 如果不是armeabi-v7a错误，则继续抛出异常
                raise

        print(Fore.GREEN + "Release模式构建完成" + Fore.RESET)

    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"Release模式构建失败: {e}" + Fore.RESET)
        raise

def run_xts(library_name=None, test_names=None):
    """运行XTS测试套件，返回测试输出结果"""
    _, _, BUNDLE_NAME = _determine_repo_type_and_config(library_name)
    try:
        # 获取原始库名
        from core.ReadExcel import read_libraries_from_excel
        libraries, original_name, urls = read_libraries_from_excel(library_name)
        
        # 1.同步项目
        subprocess.run([
            node_path, hvigor_path,
            "--sync",
            "-p", "product=default",
            "--analyze=normal",
            "--parallel",
            "--incremental",
            "--daemon"
        ], check=True)

        # 2.构建XTS工程
        subprocess.run([
            node_path, hvigor_path,
            "--mode", "module",
            "-p", "module=entry@default",
            "-p", "isOhosTest=true",
            "-p", "product=default",
            "-p", "buildMode=test",
            "assembleHap", "assembleHsp",
            "--analyze=normal",
            "--parallel",
            "--incremental",
            "--daemon"
        ], check=True)

        subprocess.run([
            node_path, hvigor_path,
            "--mode", "module",
            "-p", "module=entry@ohosTest",
            "-p", "isOhosTest=true",
            "-p", "buildMode=test",
            "assembleHap",
            "--analyze=normal",
            "--parallel,"
            "--incremental",
            "--daemon"
        ], check=True)

        # 3.运行XTS
        tmp_dir = "data/local/tmp/24141c3f96304b23aec112d51ed45ca5"

        # 卸载已有应用
        subprocess.run(["hdc", "uninstall", BUNDLE_NAME], check=True)
        
        # 创建临时目录
        subprocess.run(["hdc", "shell", "mkdir", tmp_dir], check=True)
        
        # 发送entry模块HAP文件
        subprocess.run([
            "hdc", "file", "send",
            "entry\\build\\default\\outputs\\default\\entry-default-signed.hap",
            tmp_dir
        ], check=True)
        
        # 发送测试HAP文件
        subprocess.run([
            "hdc", "file", "send",
            "entry\\build\\default\\outputs\\ohosTest\\entry-ohosTest-signed.hap",
            tmp_dir
        ], check=True)
        
        # 检查是否存在sharedLibrary模块
        has_shared_library = False
        shared_library_path = None
        
        # 检查不同大小写的sharedLibrary目录
        if os.path.exists("sharedlibrary"):
            shared_library_path = "sharedlibrary\\build\\default\\outputs\\default\\sharedlibrary-default-signed.hsp"
            has_shared_library = os.path.exists(shared_library_path)
        elif os.path.exists("sharedLibrary"):
            shared_library_path = "sharedLibrary\\build\\default\\outputs\\default\\sharedLibrary-default-signed.hsp"
            has_shared_library = os.path.exists(shared_library_path)
        
        # 如果存在sharedLibrary模块，发送HSP文件
        if has_shared_library and shared_library_path:
            print(f"检测到sharedLibrary模块，发送HSP文件: {shared_library_path}")
            try:
                subprocess.run([
                    "hdc", "file", "send",
                    shared_library_path,
                    tmp_dir
                ], check=True)
            except subprocess.CalledProcessError as e:
                print(f"警告: 发送sharedLibrary HSP文件失败: {e}")
        
        # 安装应用
        subprocess.run(["hdc", "shell", "bm", "install", "-p", tmp_dir], check=True)
        
        # 清理临时目录
        subprocess.run(["hdc", "shell", "rm", "-rf", tmp_dir], check=True)

        # 4.运行测试
        print(f"测试名称: {test_names}")
        if test_names:
            output = run_in_new_cmd(test_names, original_name)  # 使用original_name
            
            # 修改这里，直接传递原始输出字符串，不调用display_test_tree
            # display_test_tree(output)
            
            # 从输出中提取测试结果并显示
            extracted_data = extract_test_details(output)
            test_results = extracted_data["test_results"]
            summary = extracted_data["summary"]
            class_times = extracted_data["class_times"]
            
            # 使用ExtractTestDetails.py中的函数显示测试树
            display_test_details(test_results, summary, class_times)
            
            return output
        else:
            print(Fore.RED + "未找到可执行的测试用例" + Fore.RESET)
            return ""

    except subprocess.CalledProcessError as e:
        print(f"XTS测试失败: {e}")
        return f"XTS测试失败: {e}"  # 返回错误信息

def run_in_new_cmd(test_names, library_name):
    _, _, BUNDLE_NAME = _determine_repo_type_and_config(library_name)
    test_classes = ",".join(test_names)
    print(f"Running tests: {test_classes}")

    # 记录开始时间
    start_time = time.time()

    # 首先检查并修正TestRunner目录
    # 查找TestRunner目录的实际名称
    search_dir = os.path.join("entry", "src", "ohosTest", "ets")
    runner_dir = None

    if os.path.exists(search_dir):
        for dirname in os.listdir(search_dir):
            if dirname.lower() == "testrunner":
                runner_dir = dirname  # 保留原始大小写
                print(f"检测到TestRunner目录: {runner_dir}")
                break

    # 如果没有找到TestRunner目录，使用默认值
    if not runner_dir:
        runner_dir = "TestRunner"
        print(f"未找到TestRunner目录，使用默认值: {runner_dir}")

    # 定义module.json5文件路径
    module_json5_path = os.path.join("entry", "src", "ohosTest", "module.json5")

    # 检查并读取module.json5文件
    if os.path.exists(module_json5_path):
        with open(module_json5_path, 'r', encoding='utf-8') as module_file:
            module_data = json5.load(module_file)
            module_name = module_data.get("module", {}).get("name", "entry_test")
            abilities = module_data.get("module", {}).get("abilities", [])
            
            # 处理abilities中的srcEntrance
            for ability in abilities:
                if "srcEntrance" in ability:
                    ability["srcEntrance"] = ability.get("srcEntrance").replace("srcEntrance", "srcEntry")
                else:
                    print(f"没有srcEntrance，直接跳过")
    else:
        print(f"警告： 未找到module.json5文件，使用默认的module名称： entry_test")
        module_name = "entry_test"

    # 使用检测到的路径执行测试
    cmd = (f'hdc shell aa test -b {BUNDLE_NAME} -m {module_name} '
           f'-s unittest /ets/{runner_dir}/OpenHarmonyTestRunner -s class {test_classes} -s timeout 15000')

    print(f"执行测试命令: {cmd}")
    result = subprocess.run(
        ['hdc', 'shell', cmd.split('shell ')[1]],
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    # 计算总执行时间
    end_time = time.time()
    total_time = end_time - start_time
    print(f"测试总执行时间: {total_time:.2f}秒")

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    # 生成测试报告
    generate_reports(result.stdout, library_name)
    
    return result.stdout

def extract_test_names():
    """提取测试目录下所有.test.ets文件中的测试函数名称（递归查找），并排除被注释掉的测试"""
    base_test_dir = os.path.join("entry", "src", "ohosTest", "ets", "test")
    test_names = []
    commented_tests = set()  # 存储被注释掉的测试函数名

    try:
        # 检查测试目录是否存在
        if not os.path.exists(base_test_dir):
            print(f"错误：测试目录 {base_test_dir} 不存在!")
            return None

        # 第一步：先找出所有被注释掉的测试函数调用
        for root, dirs, files in os.walk(base_test_dir):
            for filename in files:
                if filename.endswith(".test.ets") and "List" in filename:
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, os.getcwd())

                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        # 查找testsuite函数中被注释掉的函数调用
                        testsuite_pattern = r"export\s+default\s+function\s+testsuite\(\)\s*{([\s\S]*?)}"
                        testsuite_match = re.search(testsuite_pattern, content)

                        if testsuite_match:
                            testsuite_content = testsuite_match.group(1)
                            # 查找被注释掉的函数调用
                            commented_calls = re.findall(r"//\s*([a-zA-Z0-9_]+)\(\);", testsuite_content)

                            if commented_calls:
                                print(f"在文件{relative_path}中找到被注释掉的测试函数调用: {commented_calls}")
                                commented_tests.update(commented_calls)

                                # 查找这些被注释函数对应的测试名称
                                for commented_call in commented_calls:
                                    # 从函数名推断可能的测试名称
                                    # 例如：mmkvRootJsunit_x86 -> mmkvTest_x86
                                    possible_test_name = re.sub(r"Root.*?Jsunit_", "Test_", commented_call)
                                    if possible_test_name != commented_call:
                                        commented_tests.add(possible_test_name)

                                    # 查找定义这个函数的文件，提取对应的测试名称
                                    for sub_root, sub_dirs, sub_files in os.walk(base_test_dir):
                                        for sub_filename in sub_files:
                                            if sub_filename.endswith(".test.ets") and sub_filename != filename:
                                                sub_filepath = os.path.join(sub_root, sub_filename)

                                                try:
                                                    with open(sub_filepath, "r", encoding="utf-8") as sub_f:
                                                        sub_content = sub_f.read()

                                                    # 查找函数定义
                                                    func_pattern = rf"function\s+{re.escape(commented_call)}\(\)"
                                                    if re.search(func_pattern, sub_content):
                                                        # 提取该文件中的测试名称
                                                        test_pattern = r"describe\(\s*['\"]([a-zA-Z0-9_]*)['\"]"
                                                        test_matches = re.findall(test_pattern, sub_content)

                                                        if test_matches:
                                                            print(
                                                                f"在文件{sub_filepath}中找到被注释函数{commented_call}对应的测试: {test_matches}")
                                                            commented_tests.update(test_matches)
                                                except (KeyError, IndexError, ValueError, TypeError):
                                                    continue
                    except (KeyError, IndexError, ValueError, TypeError) as file_err:
                        print(f"处理文件{relative_path}出错: {file_err}")
                        continue

        # 第二步：提取所有测试名称，但排除被注释的测试
        for root, dirs, files in os.walk(base_test_dir):
            for filename in files:
                if filename.endswith(".test.ets"):
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, os.getcwd())

                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        # 使用正则表达式提取测试名称
                        pattern = r"describe\(\s*['\"]([a-zA-Z0-9_]*)['\"]"  # 匹配describe('test_name')
                        matches = re.findall(pattern, content)  # 查找所有匹配项

                        if matches:
                            # 过滤掉被注释的测试
                            valid_matches = [m for m in matches if m not in commented_tests]
                            if valid_matches:
                                print(f"从文件{relative_path}中提取到有效测试名称: {valid_matches}")
                                test_names.extend(valid_matches)
                    except Exception as file_err:
                        print(f"处理文件{relative_path}出错: {file_err}")
                        continue

        if not test_names:
            print("警告：未在任何测试文件中找到有效的测试名称")
            return test_names
    except Exception as e:
        print(f"提取测试名称出错: {str(e)}")
        return None

    # 去重测试名称
    test_names = list(set(test_names))

    # 打印被排除的测试
    if commented_tests:
        print(f"以下测试被注释掉，将不会执行: {', '.join(commented_tests)}")

    print(f"总共找到{len(test_names)}个有效的唯一测试名称")
    return test_names

def _clone_repo(library_name):
    """处理带子模块的仓库克隆"""
    # 获取仓库信息
    owner, name, sub_dir = get_repo_info(library_name)
    if not owner or not name:
        print(f"错误：无法获取库 {library_name} 的仓库信息")
        return False

    # 需要递归克隆的仓库列表
    recurse_repos = {
        "openharmony_tpc_samples",
        "ohos_grpc_node", 
        "ohos_mqtt",
        "ohos_coap",
        "mp4parser",
        "ohos_videocompressor",
        "jtar"
    }

    # 构建克隆URL
    base_url = f"https://gitcode.com/{owner}/{name}"
    clone_url = f"{base_url}.git"
    target_dir = name if not sub_dir else sub_dir

    # 检查并更新已存在的目录
    if os.path.exists(target_dir):
        print(f"目录 {target_dir} 已存在，执行git pull更新")
        os.chdir(target_dir)
        try:
            subprocess.run(["git", "pull"], check=True)
            print(f"成功更新仓库 {target_dir}")
        except subprocess.CalledProcessError as e:
            print(f"Git pull失败: {e}")
        finally:
            os.chdir("..")
        return True

    # 构建克隆命令
    cmd = ["git", "clone", clone_url]
    if name in recurse_repos:
        cmd.append("--recurse-submodules")
        print(f"克隆仓库 {clone_url} 及其子模块...")
    else:
        print(f"克隆仓库 {clone_url}...")
