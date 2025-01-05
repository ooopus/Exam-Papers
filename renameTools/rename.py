import os
import re
import argparse
import logging
import sys
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(config_path="config.json"):
    """加载配置文件."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"配置文件 {config_path} 未找到，使用默认规则。")
        return {}
    except json.JSONDecodeError:
        logging.error(f"配置文件 {config_path} JSON 格式错误，请检查。")
        return {}

def extract_file_info(filename, config):
    """从文件名中提取年份、月份、考试类型和文件类型，全部使用正则表达式."""
    year_match = None
    month_match = None

    year_regex = config.get("year_regex")
    if year_regex:
        year_match = re.search(year_regex, filename)

    month_regex = config.get("month_regex")
    if month_regex:
        month_match = re.search(month_regex, filename)

    exam_type = "未知"
    for rule in config.get("exam_type_rules", []):
        if re.search(rule["pattern"], filename):
            exam_type = rule["type"]
            break

    file_type = "未知"
    for rule in config.get("file_type_rules", []):
        if re.search(rule["pattern"], filename):
            file_type = rule["type"]
            break

    return year_match, month_match, exam_type, file_type

def generate_new_filename(filename, year_match, month_match, exam_type, file_type):
    """根据提取的文件信息生成新的文件名."""
    file_extension = os.path.splitext(filename)[1]

    if year_match:
        year = year_match.group(1)
        if month_match:
            month = month_match.group(1).zfill(2)
            new_filename = f"{year}.{month}.{exam_type}.{file_type}{file_extension}"
        else:
            new_filename = f"{year}.{exam_type}.{file_type}{file_extension}"
    else:
        new_filename = filename

    return new_filename

def _process_file(directory, filename, config, existing_new_filenames):
    """Helper function to process a single file for renaming."""
    if os.path.isdir(os.path.join(directory, filename)):
        return None, None  # Indicate it's a directory

    year_match, month_match, exam_type, file_type = extract_file_info(filename, config)
    new_filename_base = generate_new_filename(filename, year_match, month_match, exam_type, file_type)
    new_filename = new_filename_base

    if new_filename in existing_new_filenames:
        return None, (filename, new_filename)  # Conflict
    else:
        return (os.path.join(directory, filename), os.path.join(directory, new_filename)), None

def collect_rename_pairs(directory, recursive, config):
    """收集需要重命名的文件对，使用配置文件."""
    rename_pairs = []
    conflict_files = []
    existing_new_filenames = set()

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)

        if os.path.isdir(item_path) and recursive:
            sub_rename_pairs, sub_conflict_files, sub_existing_new_filenames = collect_rename_pairs(item_path, True, config)
            rename_pairs.extend(sub_rename_pairs)
            conflict_files.extend(sub_conflict_files)
            existing_new_filenames.update(sub_existing_new_filenames)
        elif not os.path.isdir(item_path):
            rename_info, conflict_info = _process_file(directory, item, config, existing_new_filenames)
            if rename_info:
                rename_pairs.append(rename_info)
                existing_new_filenames.add(os.path.basename(rename_info[1]))
            elif conflict_info:
                conflict_files.append(conflict_info)

    return rename_pairs, conflict_files, existing_new_filenames

def display_preview(rename_pairs, conflict_files, dry_run):
    """显示重命名预览."""
    operation = "将要执行的重命名操作预览" if dry_run else "即将执行的重命名操作预览"
    print(f"\n{operation}:")
    for old_path, new_path in rename_pairs:
        print(f"  重命名: {os.path.basename(old_path)} -> {os.path.basename(new_path)}")

    if conflict_files:
        print("\n以下文件由于目标文件已存在而将被跳过:")
        for filename, new_filename in conflict_files:
            print(f"  跳过: {filename} (目标: {new_filename})")
    else:
        print("\n没有文件因冲突而被跳过。")

    if not dry_run:
        while True:
            confirmation = input("\n确认执行重命名 (y/n)? ").strip().lower()
            if confirmation == 'y':
                return True
            elif confirmation == 'n':
                return False
            else:
                print("无效输入，请回答 'y' 或 'n'。")
    return True  # 对于 dry-run，始终返回 True

def rename_files(rename_pairs, dry_run):
    """重命名文件."""
    if dry_run:
        logging.info("以 dry-run 模式运行，未执行实际重命名。")
        return

    for old_path, new_path in rename_pairs:
        try:
            os.rename(old_path, new_path)
            logging.info(f"已重命名: {os.path.basename(old_path)} -> {os.path.basename(new_path)}")
        except FileNotFoundError:
            logging.error(f"重命名失败: 文件未找到 - {os.path.basename(old_path)}")
        except PermissionError:
            logging.error(f"重命名失败: 权限不足 - 无法重命名 {os.path.basename(old_path)}")
        except Exception as e:
             logging.error(f"重命名失败: {os.path.basename(old_path)} 到 {os.path.basename(new_path)} - {e}")

def main():
    parser = argparse.ArgumentParser(description="批量重命名文件工具")
    parser.add_argument("directory", nargs='?', help="要处理的目录路径")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归处理子文件夹")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不执行实际重命名")

    args = parser.parse_args()

    config = load_config()  # 加载配置文件

    directory = args.directory

    if not directory:
        while True:
            directory = input("请输入要处理的目录路径: ").strip()
            if os.path.isdir(directory):
                break
            else:
                print("错误：指定的目录不存在，请重新输入。")

    recursive = False
    if args.recursive:
        recursive = True
    else:
        while True:
            recursive_input = input("是否需要递归处理子文件夹？ (y/n): ").strip().lower()
            if recursive_input == 'y':
                recursive = True
                break
            elif recursive_input == 'n':
                recursive = False
                break
            else:
                print("无效输入，请回答 'y' 或 'n'。")

    if not os.path.isdir(directory):
        print("错误：指定的目录不存在。")
        if getattr(sys, 'frozen', False):
            input("按回车键退出...")
        return

    rename_pairs, conflict_files, _ = collect_rename_pairs(directory, recursive, config)

    if rename_pairs or conflict_files:
        if display_preview(rename_pairs, conflict_files, args.dry_run):
            rename_files(rename_pairs, args.dry_run)
            print("\n文件重命名操作已完成。")
        else:
            print("\n重命名操作已取消。")
    else:
        print("\n没有需要重命名的文件。")

    if getattr(sys, 'frozen', False):
        input("按回车键退出...")

if __name__ == "__main__":
    main()