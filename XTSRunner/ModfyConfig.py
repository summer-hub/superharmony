import os
import re
import json
import shutil

from core.ReadExcel import get_repo_info, read_libraries_from_excel, parse_git_url, fuzzy_match_libraries
from config import selected_sdk_version


def _run_config_scripts():
    """运行配置脚本"""
    print("开始更新项目配置...")

    # 重新导入以确保获取最新的值
    from config import selected_sdk_version, selected_api_version

    if not selected_sdk_version or not selected_api_version:
        print("错误：未设置SDK版本，请确保在主程序开始时输入了正确的SDK版本")
        return

    # 修改build-profile.json5的SDK版本配置
    _modify_build_profile(selected_sdk_version, selected_api_version)

    # 更新build-profile.json5的签名配置
    _update_config()

    # 更新app.json5的bundleName
    _update_appname()

    # 注释特定库的armeabi-v7配置
    _comment_armeabi_v7()

    # 执行特定库的额外配置
    _run_library_specific_scripts()

    print("项目配置更新完成")


def _comment_armeabi_v7():
    """注释特定库的armeabi-v7配置"""
    print("开始检查并处理armeabi-v7配置...")

    # 获取当前库名
    current_library = _get_current_library_name()
    if not current_library:
        print("无法确定当前库名，跳过armeabi-v7配置处理")
        return

    # 将当前库名转为小写，用于不区分大小写的匹配
    current_library_lower = current_library.lower()
    print(f"正在处理库: {current_library}")

    # 获取当前工作目录
    current_dir = os.getcwd()

    # 定义库名和对应的配置文件路径映射
    library_config_paths = {
        "ohos_mqtt": os.path.join(current_dir, 'ohos_Mqtt', 'build-profile.json5'),
        "ohos_coap": os.path.join(current_dir, 'libcoap', 'build-profile.json5'),
        "ohos_ijkplayer": os.path.join(current_dir, 'ijkplayer', 'build-profile.json5'),
        "mp4parser": os.path.join(current_dir, 'library', 'build-profile.json5'),
        "lottieArkTS": os.path.join(current_dir, 'library', 'build-profile.json5'),
    }

    # 库名的显示名称映射
    library_display_names = {
        "ohos_mqtt": "ohos_Mqtt",
        "ohos_coap": "libcoap (ohos_coap)",
        "ohos_ijkplayer": "ijkplayer",
        "mp4parser": "mp4parser (library目录)",
        "lottieArkTS": "lottieArkTS (library目录)"
    }

    # 检查当前库是否在需要处理的库列表中
    need_process = False
    for lib_key in library_config_paths:
        if lib_key in current_library_lower:
            print(f"正在处理库: {library_display_names.get(lib_key, lib_key)}")
            config_path = library_config_paths[lib_key]
            if os.path.exists(config_path):
                _process_armeabi_config(config_path)
                need_process = True
            else:
                print(f"警告：找不到文件 {config_path}")

    # 如果不是预定义的库，只处理library/build-profile.json5文件
    if not need_process:
        print(f"当前库不在预定义列表中，只处理library/build-profile.json5文件...")

        # 只处理library目录下的build-profile.json5文件
        library_config_path = os.path.join(current_dir, 'library', 'build-profile.json5')

        if os.path.exists(library_config_path):
            print(f"找到配置文件: {library_config_path}")
            _process_armeabi_config(library_config_path)
        else:
            print(f"警告：找不到library/build-profile.json5文件")

            # 如果没有找到library/build-profile.json5，尝试查找根目录下的build-profile.json5
            root_config_path = os.path.join(current_dir, 'build-profile.json5')
            if os.path.exists(root_config_path):
                print(f"找到根目录配置文件: {root_config_path}")
                _process_armeabi_config(root_config_path)
            else:
                print("未找到任何build-profile.json5文件")

    print("armeabi-v7配置处理完成")


def _process_armeabi_config(config_path):
    """处理单个配置文件的armeabi-v7配置"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查是否存在未注释的armeabi-v7行
            armeabi_pattern = r'^(?!//\s*).*armeabi-v7.*$'
            if not re.search(armeabi_pattern, content, flags=re.MULTILINE):
                print(f"{config_path} 中的armeabi-v7配置已经被注释，无需处理")
                return

            # 注释掉包含armeabi-v7的未注释行
            content = re.sub(
                armeabi_pattern,
                r'// \g<0>',
                content,
                flags=re.MULTILINE
            )

            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"已注释 {config_path} 中的armeabi-v7配置")
        except Exception as e:
            print(f"处理 {config_path} 时出错: {str(e)}")
    else:
        print(f"警告：找不到文件 {config_path}")


def _modify_build_profile(sdk_version, api_version):
    """修改build-profile.json5文件，更新SDK版本配置"""
    try:
        build_profile_path = os.path.join(os.getcwd(), 'build-profile.json5')
        if not os.path.exists(build_profile_path):
            print(f"警告：找不到build-profile.json5文件: {build_profile_path}")
            return False

        # 读取文件内容
        with open(build_profile_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试解析JSON5（这里简化处理，将JSON5视为JSON）
        try:
            # 移除注释行
            content_clean = clean_json5_content(content)
            config = json.loads(content_clean)

            # 修改app层级的配置
            if 'app' in config:
                # 删除app层级的compileSdkVersion和compatibleSdkVersion
                if 'compileSdkVersion' in config['app']:
                    del config['app']['compileSdkVersion']
                if 'compatibleSdkVersion' in config['app']:
                    del config['app']['compatibleSdkVersion']

                # 修改products配置
                if 'products' in config['app']:
                    for product in config['app']['products']:
                        # 删除product层级的compileSdkVersion和targetSdkVersion
                        if 'compileSdkVersion' in product:
                            del product['compileSdkVersion']
                        if 'targetSdkVersion' in product:
                            del product['targetSdkVersion']

                        # 设置product层级的compatibleSdkVersion和runtimeOS
                        product['compatibleSdkVersion'] = f"{sdk_version}({api_version})"
                        product['runtimeOS'] = "HarmonyOS"
                        product['signingConfig'] = "default"

            # 将修改后的配置写回文件
            with open(build_profile_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)  # type: ignore

            print(f"成功修改build-profile.json5文件")

            # 新增：处理hvigor目录
            hvigor_dir = os.path.join(os.getcwd(), 'hvigor')
            if os.path.exists(hvigor_dir):
                # 删除hvigor-wrapper.js
                hvigor_wrapper_path = os.path.join(hvigor_dir, 'hvigor-wrapper.js')
                if os.path.exists(hvigor_wrapper_path):
                    os.remove(hvigor_wrapper_path)
                    print(f"已删除 {hvigor_wrapper_path}")

                # 修改hvigor-config.json5
                hvigor_config_path = os.path.join(hvigor_dir, 'hvigor-config.json5')
                if os.path.exists(hvigor_config_path):
                    with open(hvigor_config_path, 'r', encoding='utf-8') as f:
                        hvigor_config_content = f.read()

                    # 删除hvigorVersion字段和@ohos/hvigor-ohos-plugin字段
                    hvigor_config_content = re.sub(r'"hvigorVersion":\s*"[^"]*",?\s*', '', hvigor_config_content)
                    hvigor_config_content = re.sub(r'"@ohos/hvigor-ohos-plugin":\s*"[^"]*",?\s*', '',
                                                   hvigor_config_content)

                    # 添加或更新modelVersion
                    hvigor_config_content = _add_or_update_model_version(hvigor_config_content, f"{sdk_version}")

                    # 写回文件
                    with open(hvigor_config_path, 'w', encoding='utf-8') as f:
                        f.write(hvigor_config_content)

                    print(f"已更新 {hvigor_config_path}")

            # 新增：修改工程级oh-package.json5
            oh_package_path = os.path.join(os.getcwd(), 'oh-package.json5')
            if os.path.exists(oh_package_path):
                with open(oh_package_path, 'r', encoding='utf-8') as f:
                    oh_package_content = f.read()

                # 添加或更新modelVersion
                oh_package_content = _add_or_update_model_version(oh_package_content, f"{sdk_version}")

                # 写回文件
                with open(oh_package_path, 'w', encoding='utf-8') as f:
                    f.write(oh_package_content)

                print(f"已更新 {oh_package_path}")

            print("项目配置修改成功")
            return True

        except json.JSONDecodeError as e:
            # 如果JSON解析失败，使用正则表达式方法
            print(f"JSON解析失败，使用正则表达式方法: {str(e)}")

            # 删除compileSdkVersion和targetSdkVersion
            content = re.sub(r',?\s*"compileSdkVersion"\s*:\s*\d+', '', content)
            content = re.sub(r',?\s*"targetSdkVersion"\s*:\s*\d+', '', content)

            # 修改compatibleSdkVersion
            content = re.sub(
                r'"compatibleSdkVersion"\s*:\s*\d+',
                '"compatibleSdkVersion": f"{sdk_version}({selected_api_version})"',
                content
            )

            # 修改runtimeOS
            if '"runtimeOS"' in content:
                content = re.sub(
                    r'"runtimeOS"\s*:\s*"[^"]*"',
                    '"runtimeOS": "HarmonyOS"',
                    content
                )
            else:
                # 如果没有runtimeOS字段，在compatibleSdkVersion后添加
                content = re.sub(
                    r'("compatibleSdkVersion"\s*:\s*"[^"]*")(\s*)(,?)',
                    r'\1,\n        "runtimeOS": "HarmonyOS"\3',
                    content
                )

            # 写回文件
            with open(build_profile_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"成功使用正则表达式修改build-profile.json5文件")

            # 同样处理hvigor目录和oh-package.json5
            # 这部分逻辑与上面相同，可以提取为单独的函数
            _process_hvigor_and_oh_package()

            return True

    except Exception as e:
        print(f"修改build-profile.json5文件时出错: {str(e)}")
        return False


def _process_hvigor_and_oh_package():
    """处理hvigor目录和oh-package.json5文件"""
    try:
        # 处理hvigor目录
        hvigor_dir = os.path.join(os.getcwd(), 'hvigor')
        if os.path.exists(hvigor_dir):
            # 删除hvigor-wrapper.js
            hvigor_wrapper_path = os.path.join(hvigor_dir, 'hvigor-wrapper.js')
            if os.path.exists(hvigor_wrapper_path):
                os.remove(hvigor_wrapper_path)
                print(f"已删除 {hvigor_wrapper_path}")

            # 修改hvigor-config.json5
            hvigor_config_path = os.path.join(hvigor_dir, 'hvigor-config.json5')
            if os.path.exists(hvigor_config_path):
                with open(hvigor_config_path, 'r', encoding='utf-8') as f:
                    hvigor_config_content = f.read()

                # 删除hvigorVersion字段和@ohos/hvigor-ohos-plugin字段
                hvigor_config_content = re.sub(r'"hvigorVersion":\s*"[^"]*",?\s*', '', hvigor_config_content)
                hvigor_config_content = re.sub(r'"@ohos/hvigor-ohos-plugin":\s*"[^"]*",?\s*', '', hvigor_config_content)

                # 添加或更新modelVersion
                hvigor_config_content = _add_or_update_model_version(hvigor_config_content, f"{selected_sdk_version}")

                # 写回文件
                with open(hvigor_config_path, 'w', encoding='utf-8') as f:
                    f.write(hvigor_config_content)

                print(f"已更新 {hvigor_config_path}")

        # 修改工程级oh-package.json5
        oh_package_path = os.path.join(os.getcwd(), 'oh-package.json5')
        if os.path.exists(oh_package_path):
            with open(oh_package_path, 'r', encoding='utf-8') as f:
                oh_package_content = f.read()

            # 添加或更新modelVersion
            oh_package_content = _add_or_update_model_version(oh_package_content, f"{selected_sdk_version}")

            # 写回文件
            with open(oh_package_path, 'w', encoding='utf-8') as f:
                f.write(oh_package_content)

            print(f"已更新 {oh_package_path}")

        print("项目配置修改成功")
        return True

    except Exception as e:
        print(f"处理hvigor目录和oh-package.json5时出错: {str(e)}")
        return False


def _add_or_update_model_version(content, version):
    """添加或更新modelVersion字段"""
    # 检查是否已存在modelVersion字段
    if '"modelVersion"' in content:
        # 更新现有的modelVersion
        content = re.sub(
            r'"modelVersion"\s*:\s*"[^"]*"',
            f'"modelVersion": "{version}"',
            content
        )
    else:
        # 在第一个大括号后添加modelVersion字段
        content = re.sub(
            r'{\s*',
            f'{{\n  "modelVersion": "{version}",\n  ',
            content,
            count=1
        )

    return content


def _update_config():
    """更新build-profile.json5文件中的签名配置，对应update_config.js的功能"""
    try:
        config_path = os.path.join(os.getcwd(), 'build-profile.json5')
        if not os.path.exists(config_path):
            print(f"警告：找不到build-profile.json5文件: {config_path}")
            return False

        # 读取文件内容
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试解析JSON5（简化处理）
        try:
            content_clean = clean_json5_content(content)
            config = json.loads(content_clean)

            # 初始化对象层级
            config = config or {}
            config['app'] = config.get('app', {})
            config['app']['signingConfigs'] = config['app'].get('signingConfigs', [])

            # 确保products数组中的每个product都有runtimeOS字段
            if 'products' in config['app']:
                for product in config['app']['products']:
                    if 'runtimeOS' not in product:
                        product['runtimeOS'] = "HarmonyOS"

            # 根据当前库的仓库类型选择签名配置和包名
            repo_type, new_signing_config, bundle_name = _determine_repo_type_and_config()

            # 设置全局变量，供其他函数使用
            global BUNDLE_NAME
            BUNDLE_NAME = bundle_name

            print(f"使用 {repo_type} 仓库类型的签名配置和包名: {BUNDLE_NAME}")

            # 查找同名配置索引
            existing_index = -1
            for i, config_item in enumerate(config['app']['signingConfigs']):
                if config_item.get('name') == new_signing_config['name']:
                    existing_index = i
                    break

            # 更新或添加配置
            if existing_index >= 0:
                config['app']['signingConfigs'][existing_index] = new_signing_config
            else:
                config['app']['signingConfigs'].append(new_signing_config)

            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)  # type: ignore

            print("成功更新build-profile.json5中的签名配置")
            return True

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {str(e)}")
            return False
    except Exception as e:
        print(f"更新签名配置时出错: {str(e)}")
        return False


def _determine_repo_type_and_config():
    """根据当前库的仓库类型选择签名配置和包名"""
    # 导入配置
    from config import SIGNING_CONFIG_SIG, SIGNING_CONFIG_TPC, SIGNING_CONFIG_SAMPLES
    from config import BUNDLE_NAME_SIG, BUNDLE_NAME_TPC, BUNDLE_NAME_SAMPLES

    try:
        # 获取当前库名
        current_library = _get_current_library_name()

        # 默认使用SIG配置
        repo_type = "sig"
        signing_config = SIGNING_CONFIG_SIG
        bundle_name = BUNDLE_NAME_SIG

        if current_library:
            # 使用ReadExcel.py中的get_repo_info获取仓库信息
            owner, _, _ = get_repo_info(current_library)

            # 如果无法通过get_repo_info获取owner，尝试直接从URL解析
            if not owner:
                _, _, urls = read_libraries_from_excel()
                url = urls.get(current_library, "")
                if url:
                    owner, _, _ = parse_git_url(url)

            if owner:
                # 根据owner确定仓库类型
                if "openharmony-sig" in owner.lower():
                    repo_type = "sig"
                    signing_config = SIGNING_CONFIG_SIG
                    bundle_name = BUNDLE_NAME_SIG
                elif "openharmony-tpc" in owner.lower():
                    # 进一步区分是tpc还是samples
                    _, _, urls = read_libraries_from_excel()
                    url = urls.get(current_library, "")
                    if url and "openharmony_tpc_samples" in url.lower():
                        repo_type = "samples"
                        signing_config = SIGNING_CONFIG_SAMPLES
                        bundle_name = BUNDLE_NAME_SAMPLES
                    else:
                        repo_type = "tpc"
                        signing_config = SIGNING_CONFIG_TPC
                        bundle_name = BUNDLE_NAME_TPC
                try:
                    # 尝试模糊匹配库名
                    matched_libraries = fuzzy_match_libraries(current_library)
                    if matched_libraries:
                        # 使用第一个匹配的库来确定类型
                        matched_lib = matched_libraries[0]
                        owner, _, _ = get_repo_info(matched_lib)
                        if owner:
                            if "openharmony-sig" in owner:
                                repo_type = "sig"
                                signing_config = SIGNING_CONFIG_SIG
                                bundle_name = BUNDLE_NAME_SIG
                            elif "openharmony-tpc" in owner:
                                _, _, urls = read_libraries_from_excel()
                                url = urls.get(matched_lib, "")
                                if "openharmony_tpc_samples" in url:
                                    repo_type = "samples"
                                    signing_config = SIGNING_CONFIG_SAMPLES
                                    bundle_name = BUNDLE_NAME_SAMPLES
                                else:
                                    repo_type = "tpc"
                                    signing_config = SIGNING_CONFIG_TPC
                                    bundle_name = BUNDLE_NAME_TPC
                except Exception as e:
                    print(f"模糊匹配库时出错: {str(e)}")
                else:
                    # 默认归类为tpc
                    repo_type = "tpc"
                    signing_config = SIGNING_CONFIG_TPC
                    bundle_name = BUNDLE_NAME_TPC
            else:
                # 如果无法获取owner，尝试根据库名进行匹配
                current_library_lower = current_library.lower()
                if "mpchart" in current_library_lower or "chart" in current_library_lower:
                    repo_type = "tpc"
                    signing_config = SIGNING_CONFIG_TPC
                    bundle_name = BUNDLE_NAME_TPC
                elif "box2d" in current_library_lower or "sample" in current_library_lower:
                    repo_type = "samples"
                    signing_config = SIGNING_CONFIG_SAMPLES
                    bundle_name = BUNDLE_NAME_SAMPLES
                # 其他情况使用默认的SIG配置

        print(f"确定仓库类型为: {repo_type}, 使用对应的签名配置和包名")
        return repo_type, signing_config, bundle_name

    except Exception as e:
        print(f"确定仓库类型时出错: {str(e)}")
        # 出错时使用默认配置
        return "sig", SIGNING_CONFIG_SIG, BUNDLE_NAME_SIG


def _get_current_library_name():
    """获取当前正在测试的库名称"""
    try:
        # 从当前目录名称推断
        current_dir = os.path.basename(os.getcwd())

        # 获取所有库名
        libraries, _, urls = read_libraries_from_excel()

        # 首先尝试直接匹配当前目录与库名
        for lib in libraries:
            if lib.lower() == current_dir.lower():
                print(f"通过目录名精确匹配到库: {lib}")
                return lib

        # 如果没有精确匹配，尝试部分匹配
        for lib in libraries:
            if lib.lower() in current_dir.lower() or current_dir.lower() in lib.lower():
                print(f"通过目录名部分匹配到库: {lib}")
                return lib

        # 如果目录名匹配失败，尝试通过解析URL中的仓库名或子目录匹配
        for lib, url in urls.items():
            owner, name, sub_dir = parse_git_url(url)
            # 检查仓库名是否匹配
            if name and name.lower() == current_dir.lower():
                print(f"通过仓库名匹配到库: {lib}")
                return lib
            # 检查子目录是否匹配
            if sub_dir and sub_dir.lower() == current_dir.lower():
                print(f"通过子目录匹配到库: {lib}")
                return lib

        # 如果无法确定，返回默认库（如果有）
        if libraries:
            print(f"无法匹配库名，使用默认库: {libraries[0]}")
            return libraries[0]

        print("警告: 无法确定当前库名")
        return None

    except Exception as e:
        print(f"获取当前库名时出错: {str(e)}")
        return None


def _run_library_specific_scripts():
    """执行特定库的额外配置脚本"""
    print("开始执行特定库的额外配置...")

    # 获取当前库名
    current_library = _get_current_library_name()
    if not current_library:
        print("无法确定当前库名，跳过特定配置")
        return

    # 将当前库名转为小写，用于不区分大小写的匹配
    current_library_lower = current_library.lower()
    print(f"当前处理的库: {current_library}")

    # 获取当前工作目录
    current_dir = os.getcwd()

    # 处理mqtt库 - 当组件名匹配时执行
    if "ohos_mqtt" in current_library_lower:
        print(f"正在为库 {current_library} 执行MQTT特定配置...")

        # 1. 复制thirdparty文件夹
        mqtt_thirdparty_src = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'reply', 'mqtt', 'thirdparty')
        mqtt_thirdparty_dest = os.path.join(current_dir, 'ohos_Mqtt', 'src', 'main', 'cpp', 'thirdparty')

        if os.path.exists(mqtt_thirdparty_src):
            try:
                # 确保目标目录存在
                os.makedirs(os.path.dirname(mqtt_thirdparty_dest), exist_ok=True)

                # 复制thirdparty文件夹
                shutil.copytree(mqtt_thirdparty_src, mqtt_thirdparty_dest, dirs_exist_ok=True)
                print(f"成功复制thirdparty文件夹到 {mqtt_thirdparty_dest}")
            except Exception as e:
                print(f"复制thirdparty文件夹时出错: {str(e)}")
        else:
            print(f"警告：找不到MQTT thirdparty源目录: {mqtt_thirdparty_src}")

        # 2. 执行modify.sh脚本
        mqtt_path = os.path.join(current_dir, 'ohos_Mqtt', 'src', 'main', 'cpp', 'paho.mqtt.c')
        if os.path.exists(mqtt_path):
            try:
                # 保存当前目录
                current_dir = os.getcwd()
                # 切换到mqtt目录
                os.chdir(mqtt_path)
                if os.path.exists('modify.sh'):
                    # 使用subprocess执行脚本，并处理可能的交互
                    import subprocess
                    import time

                    # 启动脚本进程
                    process = subprocess.Popen(['bash', 'modify.sh'],
                                               stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               universal_newlines=True,
                                               shell=True)

                    # 监控输出，检查是否需要交互
                    while process.poll() is None:
                        # 读取输出
                        output = process.stdout.readline()
                        if output:
                            print(output.strip())
                            # 检查是否出现补丁已应用的提示
                            if "Reversed (or previously applied) patch detected!" in output:
                                print("检测到补丁已应用，自动回车两次...")
                                # 发送两次回车
                                process.stdin.write("\n\n")
                                process.stdin.flush()
                                time.sleep(0.5)  # 等待处理
                    # 获取最终结果
                    stdout, stderr = process.communicate()
                    if stdout:
                        print(stdout)
                    if stderr:
                        print(f"执行脚本时出现警告或错误: {stderr}")

                    print("modify.sh脚本执行完成")
                else:
                    print(f"警告：找不到mqtt库的modify.sh脚本: {mqtt_path}")

                # 3. 修改CMakeLists.txt文件
                cmake_file = os.path.join(mqtt_path, 'CMakeLists.txt')
                if os.path.exists(cmake_file):
                    try:
                        # 读取CMakeLists.txt文件
                        with open(cmake_file, 'r', encoding='utf-8') as f:
                            cmake_content = f.read()

                        # 要添加的内容
                        ssl_config = """
#开启ssl
add_definitions(-DOPENSSL)
#将三方库加入工程中
target_link_libraries(pahomqttc PRIVATE ${NATIVERENDER_ROOT_PATH}/thirdparty/openssl/${OHOS_ARCH}/lib/libssl.a)
target_link_libraries(pahomqttc PRIVATE ${NATIVERENDER_ROOT_PATH}/thirdparty/openssl/${OHOS_ARCH}/lib/libcrypto.a)

#将三方库的头文件加入工程中
target_include_directories(pahomqttc PRIVATE ${NATIVERENDER_ROOT_PATH}/thirdparty/openssl/${OHOS_ARCH}/include)
"""

                        # 检查是否已经添加了SSL配置
                        if "add_definitions(-DOPENSSL)" not in cmake_content:
                            # 在文件末尾添加SSL配置
                            with open(cmake_file, 'a', encoding='utf-8') as f:
                                f.write(ssl_config)
                            print(f"成功在 {cmake_file} 中添加SSL配置")
                        else:
                            print(f"{cmake_file} 中已存在SSL配置，无需添加")
                    except Exception as e:
                        print(f"修改CMakeLists.txt文件时出错: {str(e)}")
                else:
                    print(f"警告：找不到CMakeLists.txt文件: {cmake_file}")
            except Exception as e:
                print(f"处理mqtt库时出错: {str(e)}")
            finally:
                # 确保返回原始目录
                os.chdir(current_dir)
        else:
            print(f"警告：找不到mqtt库目录: {mqtt_path}")

    # 处理coap库 - 当组件名匹配时执行
    elif "ohos_coap" in current_library_lower:
        print(f"正在为库 {current_library} 执行COAP特定配置...")
        coap_path = os.path.join(current_dir, 'src', 'main', 'cpp', 'thirdModule')
        if os.path.exists(coap_path):
            try:
                # 保存当前目录
                current_dir = os.getcwd()
                # 切换到coap目录
                os.chdir(coap_path)
                if os.path.exists('modify.sh'):
                    os.system('./modify.sh')
                    print("成功执行coap库的modify.sh脚本")
                else:
                    print(f"警告：找不到coap库的modify.sh脚本: {coap_path}")
            except Exception as e:
                print(f"处理coap库时出错: {str(e)}")
            finally:
                # 确保返回原始目录
                os.chdir(current_dir)
        else:
            print(f"警告：找不到coap库目录: {coap_path}")

    # 处理ijkplayer库 - 当组件名匹配时执行
    elif "ohos_ijkplayer" in current_library_lower:
        print(f"正在为库 {current_library} 执行IJKPlayer特定配置...")
        ijkplayer_src = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'reply', 'ijkplayer')
        ijkplayer_dest = os.path.join(current_dir, 'ijkplayer', 'src', 'main', 'cpp', 'third_party')

        if os.path.exists(ijkplayer_src) and os.path.exists(ijkplayer_dest):
            try:
                # 拷贝ffmpeg到third_party/ffmpeg
                ffmpeg_src = os.path.join(ijkplayer_src, 'ffmpeg')
                ffmpeg_dest = os.path.join(ijkplayer_dest, 'ffmpeg')
                if os.path.exists(ffmpeg_src):
                    shutil.copytree(ffmpeg_src, ffmpeg_dest, dirs_exist_ok=True)
                    print(f"成功拷贝ffmpeg到 {ffmpeg_dest}")
                else:
                    print(f"警告：找不到ffmpeg源目录: {ffmpeg_src}")

                # 拷贝其他库到third_party
                for lib in ['openssl', 'soundtouch', 'yuv', 'openh264']:
                    lib_src = os.path.join(ijkplayer_src, lib)
                    lib_dest = os.path.join(ijkplayer_dest, lib)
                    if os.path.exists(lib_src):
                        shutil.copytree(lib_src, lib_dest, dirs_exist_ok=True)
                        print(f"成功拷贝{lib}到 {lib_dest}")
                    else:
                        print(f"警告：找不到{lib}源目录: {lib_src}")
            except Exception as e:
                print(f"处理ijkplayer库时出错: {str(e)}")
        else:
            print(f"警告：找不到ijkplayer源目录或目标目录: 源={ijkplayer_src}, 目标={ijkplayer_dest}")
    else:
        print(f"当前库 {current_library} 不需要执行特定配置脚本")

    print("特定库配置执行完成")


def clean_json5_content(content):
    """清理 JSON5 内容，移除注释和尾部逗号"""
    # 移除注释行
    content_no_comments = re.sub(r'//.*?\n', '\n', content)
    # 移除尾部逗号
    content_no_comments = re.sub(r',(\s*[}\]])', r'\1', content_no_comments)
    return content_no_comments


def _update_appname():
    """更新app.json5中的bundleName，对应update_appname.js的功能"""
    try:
        # 处理config.json
        config_path = os.path.join(os.getcwd(), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = f.read()

                config_obj = json.loads(config_data)
                # 对config.json的处理逻辑（原JS脚本中没有具体操作）

                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_obj, f, indent=2)  # type: ignore

            except Exception as e:
                print(f"处理config.json时出错: {str(e)}")

        # 处理app.json5
        app_config_path = os.path.join(os.getcwd(), 'AppScope', 'app.json5')
        if os.path.exists(app_config_path):
            try:
                # 读取文件内容
                with open(app_config_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 尝试解析JSON5
                try:
                    content_clean = clean_json5_content(content)
                    app_data = json.loads(content_clean)

                    # 修改bundleName
                    if 'app' in app_data and 'bundleName' in app_data['app']:
                        app_data['app']['bundleName'] = BUNDLE_NAME

                    # 写回文件
                    with open(app_config_path, 'w', encoding='utf-8') as f:
                        json.dump(app_data, f, indent=2)  # type: ignore
                        f.write('\n')  # 添加结尾换行符

                    print("成功更新app.json5中的bundleName")

                except json.JSONDecodeError as e:
                    # 如果JSON解析失败，使用正则表达式方法
                    print(f"JSON解析失败，使用正则表达式方法: {str(e)}")

                    # 使用正则表达式修改bundleName
                    content = re.sub(
                        r'"bundleName"\s*:\s*"[^"]*"',
                        '"bundleName": "{bundle_name}"',
                        content
                    )

                    # 写回文件
                    with open(app_config_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    print("成功使用正则表达式更新app.json5中的bundleName")

            except Exception as e:
                print(f"处理app.json5时出错: {str(e)}")

        print("配置更新完成")
        return True

    except Exception as e:
        print(f"更新应用名称时出错: {str(e)}")
        return False
