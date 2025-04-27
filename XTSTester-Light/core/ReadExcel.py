import os
import sys
import pandas as pd

from utils.config import EXCEL_FILE_PATH


def read_libraries_from_excel(library_name=None):
    """从Excel文件中读取库列表"""
    try:
        # 检查Excel文件是否存在
        if not os.path.exists(EXCEL_FILE_PATH):
            print(f"错误：找不到Excel文件 {EXCEL_FILE_PATH}")
            sys.exit(1)

        # 读取Excel文件
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=0)

        # 检查是否有"三方库名称"列
        if "三方库名称" not in df.columns:
            print("错误：Excel文件中没有'三方库名称'列")
            sys.exit(1)

        # 检查是否有"URL"列
        if "URL" not in df.columns:
            print("错误：Excel文件中没有'URL'列")
            sys.exit(1)

        # 提取三方库名称列和URL列的数据
        libraries = []
        urls = {}

        for index, row in df.iterrows():
            lib_name = row["三方库名称"]
            url = row["URL"]
            if pd.notna(lib_name) and pd.notna(url):
                # 检查URL是否有效
                owner, name, _ = parse_git_url(url)
                if owner and name:
                    libraries.append(lib_name)
                    urls[lib_name] = url
                else:
                    print(f"警告：跳过无效URL的库 {lib_name} - {url}")

        if not libraries:
            print("警告：Excel文件中没有找到任何库")
            sys.exit(1)

        # 如果没有指定库名，使用第一个库名
        component_name = library_name if library_name else libraries[0]
        # 返回库列表、当前处理的组件名和URL字典
        return libraries, component_name, urls

    except Exception as e:
        print(f"读取Excel文件出错: {str(e)}")
        sys.exit(1)

def parse_git_url(url):
    """
    解析Git URL，提取owner、name和sub_dir

    例如：
    - https://gitcode.com/openharmony-tpc/commonmark
      owner: openharmony-tpc, name: commonmark, sub_dir: ""
    - https://gitcode.com/openharmony-tpc/openharmony_tpc_samples/tree/master/GSYVideoPlayer-filters
      owner: openharmony-tpc, name: openharmony_tpc_samples, sub_dir: GSYVideoPlayer-filters
    """
    try:
        # 确保URL是字符串
        if not isinstance(url, str):
            return None, None, None

        # 移除URL末尾的斜杠（如果有）
        url = url.rstrip('/')

        # 分割URL以提取路径部分
        parts = url.split('/')

        # 确保URL格式正确
        if len(parts) < 5:
            print(f"警告：URL格式不正确 - {url} (至少需要5部分: {parts})")
            return None, None, None

        # 提取owner和name
        owner = parts[3]
        name = parts[4]

        # 检查是否有子目录
        sub_dir = ""
        if len(parts) > 5 and "tree" in parts:
            # 找到"tree"的索引
            tree_index = parts.index("tree")
            # 子目录是"tree/branch"之后的所有部分
            if tree_index + 2 < len(parts):
                sub_dir = '/'.join(parts[tree_index + 2:])

        return owner, name, sub_dir

    except Exception as e:
        print(f"解析Git URL出错: {str(e)}")
        return None, None, None

def get_repo_info(library_name):
    """
    获取指定库的仓库信息

    参数：
    - library_name: 库名称，可以是字符串或字典（包含name字段）

    返回：
    - owner: 仓库所有者
    - name: 仓库名称
    - sub_dir: 子目录（如果有）
    """
    try:
        # 处理字典类型的库名参数
        actual_library_name = library_name
        if isinstance(library_name, dict) and 'name' in library_name:
            actual_library_name = library_name['name']

        # 获取库列表和URL字典
        _, _, urls = read_libraries_from_excel()

        # 检查指定的库是否存在
        if actual_library_name not in urls:
            print(f"错误：找不到库 {actual_library_name} 的URL信息")
            return None, None, None

        # 获取库的URL
        url = urls[actual_library_name]

        # 解析URL
        owner, name, sub_dir = parse_git_url(url)

        return owner, name, sub_dir

    except Exception as e:
        print(f"获取仓库信息出错: {str(e)}")
        return None, None, None


def filter_library_by_repo_type(library_name, repo_type):
    """
    根据仓库类型过滤库
    
    参数:
        library_name: 库名称，可以是字符串或字典（包含name字段）
        repo_type: 仓库类型 (openharmony-sig, openharmony-tpc, openharmony_tpc_samples)
        
    返回:
        bool: 如果库属于指定的仓库类型，则返回True，否则返回False
    """
    try:
        # 处理字典类型的库名参数
        actual_library_name = library_name
        if isinstance(library_name, dict) and 'name' in library_name:
            actual_library_name = library_name['name']
            
        # 获取库的URL
        _, _, urls = read_libraries_from_excel()
        
        if actual_library_name not in urls:
            return False
            
        url = urls[actual_library_name]
        
        # 解析URL获取仓库信息
        owner, name, _ = parse_git_url(url)
        
        if not owner or not name:
            return False
            
        # 根据仓库类型进行过滤
        if repo_type == "openharmony-sig" and owner == "openharmony-sig":
            return True
        elif repo_type == "openharmony-tpc" and owner == "openharmony-tpc" and name != "openharmony_tpc_samples":
            return True
        elif repo_type == "openharmony_tpc_samples" and name == "openharmony_tpc_samples":
            return True
            
        return False
        
    except Exception as e:
        print(f"过滤库时出错: {str(e)}")
        return False


def fuzzy_match_libraries(search_term):
    """
    模糊匹配库名称
    
    参数:
        search_term: 搜索关键词
        
    返回:
        匹配到的库名列表
    """
    try:
        # 读取Excel文件中的所有库
        libraries, _, urls = read_libraries_from_excel()
        
        # 如果搜索词为空，返回所有库
        if not search_term:
            return libraries
            
        # 转换为小写进行不区分大小写的匹配
        search_term = search_term.lower()
        
        # 模糊匹配
        matched_libraries = []
        for lib in libraries:
            if search_term in lib.lower():
                matched_libraries.append({
                    'name': lib,
                    'version': '',
                    'type': ''
                })
        
        return matched_libraries
        
    except Exception as e:
        print(f"模糊匹配库时出错: {str(e)}")
        return []
