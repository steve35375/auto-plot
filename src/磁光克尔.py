import os
import zipfile
import tempfile
import io
import sys
import time
import threading
import pandas as pd
import originpro as op
import tkinter as tk
from tkinter import filedialog, messagebox

class TextRedirector:
    """利用 after() 建立线程安全传达室，严禁后台线程直接修改组件，彻底根治假死"""
    def __init__(self, widget):
        self.widget = widget
    def write(self, str_val):
        # 将写入动作安全地托管回主线程排队执行
        self.widget.after(0, lambda: self._safe_write(str_val))
    def _safe_write(self, str_val):
        self.widget.insert(tk.END, str_val)
        self.widget.see(tk.END)
    def flush(self):
        pass

def clean_path(path_str):
    # 清理前后空格和引号，并统一换成 Windows 标准的反斜杠
    return path_str.strip().strip('"').strip("'").strip().replace('/', '\\')

# ================== 🛠️ 后台纯净业务核心模块（业务逻辑严格保持不变） ==================

def backend_extract_data(root, root_dir, save_dir, origin_file_name):
    """后台线程执行：仅数据提取"""
    print("--- [开始执行：数据提取] ---")
    
    if not origin_file_name.endswith('.opju'):
        origin_file_name += '.opju'
    final_save_path = os.path.join(save_dir, origin_file_name).replace('/', '\\')

    zip_files = []
    if os.path.isfile(root_dir) and root_dir.lower().endswith('.zip'):
        zip_files.append(root_dir)
    else:
        for r, dirs, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith('.zip'):
                    zip_files.append(os.path.join(r, file).replace('/', '\\'))

    if not zip_files:
        print("❌ 没有找到任何 .zip 格式的压缩包。")
        return None

    print(f"共找到了 {len(zip_files)} 个压缩包。正在后台静默启动 Origin 软件...")
    op.set_show(False)  # 隐身运行，削减渲染开销

    book = op.new_book('w', 'MOKE_Summary')
    is_first_sheet = True

    with tempfile.TemporaryDirectory() as master_tmpdir:
        print("正在解压所有压缩包，请稍候...")
        for idx, zip_path in enumerate(zip_files):
            zip_base_name = os.path.splitext(os.path.basename(zip_path))[0]
            extract_sub_dir = os.path.join(master_tmpdir, f"zip_{idx}_{zip_base_name}")
            os.makedirs(extract_sub_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_sub_dir)
            except Exception as e:
                print(f"    --> 解压 {os.path.basename(zip_path)} 失败: {e}")

        valid_files = []
        for r, dirs, files in os.walk(master_tmpdir):
            for file in files:
                if file.lower().endswith(('.svp', '.csv')):
                    valid_files.append((r, file))

        total_files = len(valid_files)
        if total_files == 0:
            print("❌ 压缩包内未发现任何有效的 .svp 或 .csv 总表。")
            op.exit()
            return None
            
        print(f"共发现 {total_files} 个有效数据总表，开始提取清洗...")

        for index, (r, file) in enumerate(valid_files):
            file_path = os.path.join(r, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                wafer_id = "未知"
                for line in lines:
                    if 'WaferID:' in line:
                        wafer_id = line.split(':', 1)[1].strip()
                        break
                
                header_index = -1
                for i, line in enumerate(lines):
                    if 'Location,X,Y,Theta' in line:
                        header_index = i
                        break
                
                if header_index == -1:
                    continue
                
                data_string = "".join(lines[header_index:])
                df = pd.read_csv(io.StringIO(data_string))
                
                df_0 = df[df['Theta'] == 0][['X', 'Y', 'Hc', 'M2']]
                df_90 = df[df['Theta'] == 90][['X', 'Y', 'Hc', 'M2']]
                
                if not df_0.empty:
                    sheet_name_0 = f"{wafer_id}_0"[:30]
                    sheet_0 = book[0] if is_first_sheet else book.add_sheet(sheet_name_0)
                    if is_first_sheet:
                        sheet_0.name = sheet_name_0
                        is_first_sheet = False
                    sheet_0.from_df(df_0)
                    sheet_0.cols_axis('XYZZ')
                    for col_idx in range(4):
                        sheet_0.set_label(col_idx, sheet_name_0, 'C')
                        
                if not df_90.empty:
                    sheet_name_90 = f"{wafer_id}_90"[:30]
                    sheet_90 = book[0] if is_first_sheet else book.add_sheet(sheet_name_90)
                    if is_first_sheet:
                        sheet_90.name = sheet_name_90
                        is_first_sheet = False
                    sheet_90.from_df(df_90)
                    sheet_90.cols_axis('XYZZ')
                    for col_idx in range(4):
                        sheet_90.set_label(col_idx, sheet_name_90, 'C')
                print(f"  [{index+1}/{total_files}] 成功清洗: {file} -> ID: {wafer_id}")
            except Exception as file_err:
                print(f"  [{index+1}/{total_files}] ❌ 处理文件 {file} 失败: {file_err}")

    print("正在保存整合后的 Origin 项目文件...")
    if os.path.exists(final_save_path):
        try: os.remove(final_save_path)
        except: pass
    op.save(final_save_path)
    print(f"🎉 数据提取整合成功！文件已保存。")
    op.exit()
    return final_save_path

def backend_plot_data(root, opju_path, hc_template, m2_template):
    """后台线程执行：仅自动绘图"""
    print("\n--- [开始执行：克隆模板自动绘图] ---")
    PLOT_CONFIG = {'Hc': hc_template, 'M2': m2_template}

    print("正在后台静默打开 Origin 软件并加载数据项目...")
    op.set_show(False)
    op.open(opju_path)

    book = op.find_book()
    if not book:
        book = op.find_book('MOKE_Summary')
    if not book:
        print("❌ 没有找到任何有效的数据工作簿 (Book)。")
        op.exit()
        return

    print(f"成功挂载数据源: {book.name}，开始自动替换数据源绘图...")
    total_sheets = len(book)

    for index, sheet in enumerate(book):
        sheet_name = sheet.name
        print(f" 绘图进度: [{index + 1}/{total_sheets}] 正在渲染工作表: {sheet_name}")

        for prop_name, t_path in PLOT_CONFIG.items():
            if t_path and os.path.exists(t_path):
                try:
                    graph = sheet.plot_cloneable(t_path)
                    if graph:
                        graph.name = f"{sheet_name}_{prop_name}"[:30]
                except Exception as plot_err:
                    print(f"    --> 工作表 {sheet_name} 套用 {prop_name} 模板失败: {plot_err}")

    print("所有图形渲染完毕，正在原位保存项目文件...")
    op.save()
    print("🎉 绘图任务圆满结束！")
    op.exit()

def backend_one_click_flow(root, root_dir, save_dir, origin_file_name, hc_template, m2_template):
    """后台线程执行：一键全自动一条龙流水线"""
    print("--- [开始执行：一键全自动一条龙流水线] ---")
    
    if not origin_file_name.endswith('.opju'):
        origin_file_name += '.opju'
    final_save_path = os.path.join(save_dir, origin_file_name).replace('/', '\\')

    zip_files = []
    if os.path.isfile(root_dir) and root_dir.lower().endswith('.zip'):
        zip_files.append(root_dir)
    else:
        for r, dirs, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith('.zip'):
                    zip_files.append(os.path.join(r, file).replace('/', '\\'))

    if not zip_files:
        print("❌ 没有找到任何 .zip 格式的压缩包。")
        return

    print(f"共找到了 {len(zip_files)} 个压缩包。正在后台静默启动 Origin 软件...")
    op.set_show(False)

    book = op.new_book('w', 'MOKE_Summary')
    is_first_sheet = True

    with tempfile.TemporaryDirectory() as master_tmpdir:
        print("正在解压所有压缩包，请稍候...")
        for idx, zip_path in enumerate(zip_files):
            zip_base_name = os.path.splitext(os.path.basename(zip_path))[0]
            extract_sub_dir = os.path.join(master_tmpdir, f"zip_{idx}_{zip_base_name}")
            os.makedirs(extract_sub_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_sub_dir)
            except Exception as e:
                print(f"    --> 解压 {os.path.basename(zip_path)} 失败: {e}")

        valid_files = []
        for r, dirs, files in os.walk(master_tmpdir):
            for file in files:
                if file.lower().endswith(('.svp', '.csv')):
                    valid_files.append((r, file))

        total_files = len(valid_files)
        if total_files == 0:
            print("❌ 压缩包内未发现任何有效的 .svp 或 .csv 总表。")
            op.exit()
            return
            
        print(f"共发现 {total_files} 个有效数据总表，开始提取清洗...")

        for index, (r, file) in enumerate(valid_files):
            file_path = os.path.join(r, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                wafer_id = "未知"
                for line in lines:
                    if 'WaferID:' in line:
                        wafer_id = line.split(':', 1)[1].strip()
                        break
                
                header_index = -1
                for i, line in enumerate(lines):
                    if 'Location,X,Y,Theta' in line:
                        header_index = i
                        break
                
                if header_index == -1:
                    continue
                
                data_string = "".join(lines[header_index:])
                df = pd.read_csv(io.StringIO(data_string))
                
                df_0 = df[df['Theta'] == 0][['X', 'Y', 'Hc', 'M2']]
                df_90 = df[df['Theta'] == 90][['X', 'Y', 'Hc', 'M2']]
                
                if not df_0.empty:
                    sheet_name_0 = f"{wafer_id}_0"[:30]
                    sheet_0 = book[0] if is_first_sheet else book.add_sheet(sheet_name_0)
                    if is_first_sheet:
                        sheet_0.name = sheet_name_0
                        is_first_sheet = False
                    sheet_0.from_df(df_0)
                    sheet_0.cols_axis('XYZZ')
                    for col_idx in range(4):
                        sheet_0.set_label(col_idx, sheet_name_0, 'C')
                        
                if not df_90.empty:
                    sheet_name_90 = f"{wafer_id}_90"[:30]
                    sheet_90 = book[0] if is_first_sheet else book.add_sheet(sheet_name_90)
                    if is_first_sheet:
                        sheet_90.name = sheet_name_90
                        is_first_sheet = False
                    sheet_90.from_df(df_90)
                    sheet_90.cols_axis('XYZZ')
                    for col_idx in range(4):
                        sheet_90.set_label(col_idx, sheet_name_90, 'C')
                print(f"  [{index+1}/{total_files}] 成功清洗: {file} -> ID: {wafer_id}")
            except Exception as file_err:
                print(f"  [{index+1}/{total_files}] ❌ 处理文件 {file} 失败: {file_err}")

    print("\n--- 数据清洗提取完毕，正在直接进入模板自动绘图阶段 ---")
    
    PLOT_CONFIG = {'Hc': hc_template, 'M2': m2_template}
    total_sheets = len(book)

    for index, sheet in enumerate(book):
        sheet_name = sheet.name
        print(f" 绘图进度: [{index + 1}/{total_sheets}] 正在渲染工作表: {sheet_name}")

        for prop_name, t_path in PLOT_CONFIG.items():
            if t_path and os.path.exists(t_path):
                try:
                    graph = sheet.plot_cloneable(t_path)
                    if graph:
                        graph.name = f"{sheet_name}_{prop_name}"[:30]
                except Exception as plot_err:
                    print(f"    --> 工作表 {sheet_name} 套用 {prop_name} 模板失败: {plot_err}")

    print("\n所有图表绘制完毕，正在执行总存盘...")
    if os.path.exists(final_save_path):
        try: os.remove(final_save_path)
        except: pass
    op.save(final_save_path)
    print(f"🎉 一条龙自动化任务圆满结束！Origin 项目已安全落盘。")
    op.exit()

# ================== 🎨 启动器专用动态对接与异步调度层 ==================

def build_sub_interface(parent):
    root = parent.winfo_toplevel()

    current_script_dir = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
    auto_hc_path = ""
    auto_m2_path = ""
    
    if os.path.exists(current_script_dir):
        for f in os.listdir(current_script_dir):
            if f.lower().endswith('.otpu'):
                full_template_path = os.path.join(current_script_dir, f).replace('/', '\\')
                if 'hc' in f.lower():
                    auto_hc_path = full_template_path
                elif 'm2' in f.lower():
                    auto_m2_path = full_template_path

    def browse_file(entry_widget, is_zip=False, is_opju=False, is_otpu=False):
        if is_zip:
            p = filedialog.askopenfilename(filetypes=[("Zip 压缩包", "*.zip")])
        elif is_opju:
            p = filedialog.askopenfilename(filetypes=[("Origin 项目", "*.opju")])
        elif is_otpu:
            p = filedialog.askopenfilename(filetypes=[("Origin 模板", "*.otpu")])
        else:
            p = filedialog.askdirectory()
        if p:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, p.replace('/', '\\'))

    def set_buttons_state(state):
        """线程安全切换本板块内所有按钮的使能状态"""
        root.after(0, lambda: btn1.config(state=state))
        root.after(0, lambda: btn2.config(state=state))
        root.after(0, lambda: btn3.config(state=state))

    # 异步多线程车道配置
    def run_btn1_async():
        root_dir = clean_path(entry_src.get())
        save_dir = clean_path(entry_sdir.get())
        origin_file_name = entry_fname.get().strip()
        if not root_dir or not save_dir or not origin_file_name:
            messagebox.showerror("错误", "数据提取部分的所有输入框都不能为空！")
            return
            
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try:
                if not os.path.exists(root_dir) or not os.path.exists(save_dir):
                    print("❌ 找不到输入的数据路径或保存路径，请检查。")
                    return
                path = backend_extract_data(root, root_dir, save_dir, origin_file_name)
                if path:
                    root.after(0, lambda: messagebox.showinfo("成功", "数据提取并整合成功！"))
            finally:
                set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    def run_btn2_async():
        opju_path = clean_path(entry_opju.get())
        hc_template = clean_path(entry_hc.get())
        m2_template = clean_path(entry_m2.get())
        if not opju_path:
            messagebox.showerror("错误", "Origin项目文件路径不能为空！")
            return
            
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try:
                if not os.path.exists(opju_path):
                    print("❌ 找不到 Origin 项目文件，请检查路径。")
                    return
                backend_plot_data(root, opju_path, hc_template, m2_template)
                root.after(0, lambda: messagebox.showinfo("成功", "所有绘图任务已顺利全部完成！"))
            finally:
                set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    def run_btn3_async():
        root_dir = clean_path(entry_src.get())
        save_dir = clean_path(entry_sdir.get())
        origin_file_name = entry_fname.get().strip()
        hc_template = clean_path(entry_hc.get())
        m2_template = clean_path(entry_m2.get())
        if not root_dir or not save_dir or not origin_file_name:
            messagebox.showerror("错误", "数据提取部分的所有输入框都不能为空！")
            return
            
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try:
                if not os.path.exists(root_dir) or not os.path.exists(save_dir):
                    print("❌ 找不到输入的数据路径或保存路径，请检查。")
                    return
                backend_one_click_flow(root, root_dir, save_dir, origin_file_name, hc_template, m2_template)
                root.after(0, lambda: messagebox.showinfo("成功", "一键全自动一条龙任务已顺利全部完成！"))
            finally:
                set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    # 1. 数据提取设置组件区
    frame_ext = tk.LabelFrame(parent, text=" 1. 数据提取设置 (支持直接拖入文件或点击选择) ", padx=10, pady=10)
    frame_ext.pack(fill="x", padx=15, pady=5)

    tk.Label(frame_ext, text="数据源路径:").grid(row=0, column=0, sticky="w", pady=3)
    entry_src = tk.Entry(frame_ext, width=50)
    entry_src.grid(row=0, column=1, padx=5, pady=3)
    tk.Button(frame_ext, text="选择压缩包", command=lambda: browse_file(entry_src, is_zip=True)).grid(row=0, column=2, padx=2)
    tk.Button(frame_ext, text="选择文件夹", command=lambda: browse_file(entry_src)).grid(row=0, column=3, padx=2)

    tk.Label(frame_ext, text="保存文件夹:").grid(row=1, column=0, sticky="w", pady=3)
    entry_sdir = tk.Entry(frame_ext, width=50)
    entry_sdir.grid(row=1, column=1, padx=5, pady=3)
    tk.Button(frame_ext, text=" 浏 览 ", command=lambda: browse_file(entry_sdir)).grid(row=1, column=2, columnspan=2, sticky="we", padx=2)

    tk.Label(frame_ext, text="Origin文件名:").grid(row=2, column=0, sticky="w", pady=3)
    entry_fname = tk.Entry(frame_ext, width=50)
    entry_fname.insert(0, "汇总结果.opju")
    entry_fname.grid(row=2, column=1, padx=5, pady=3, sticky="w")

    # 2. 模板绘图设置组件区
    frame_plot = tk.LabelFrame(parent, text=" 2. 模板绘图设置 (自动识别同级目录模板，无需手动选择) ", padx=10, pady=10)
    frame_plot.pack(fill="x", padx=15, pady=5)

    tk.Label(frame_plot, text="仅画图时的OPJU:").grid(row=0, column=0, sticky="w", pady=3)
    entry_opju = tk.Entry(frame_plot, width=50)
    entry_opju.grid(row=0, column=1, padx=5, pady=3)
    tk.Button(frame_plot, text=" 选 择 ", command=lambda: browse_file(entry_opju, is_opju=True)).grid(row=0, column=2, columnspan=2, sticky="we", padx=2)

    tk.Label(frame_plot, text="Hc 模板路径:").grid(row=1, column=0, sticky="w", pady=3)
    entry_hc = tk.Entry(frame_plot, width=50)
    if auto_hc_path:
        entry_hc.insert(0, auto_hc_path)
    entry_hc.grid(row=1, column=1, padx=5, pady=3)
    tk.Button(frame_plot, text=" 更 换 ", command=lambda: browse_file(entry_hc, is_otpu=True)).grid(row=1, column=2, columnspan=2, sticky="we", padx=2)

    tk.Label(frame_plot, text="M2 模板路径:").grid(row=2, column=0, sticky="w", pady=3)
    entry_m2 = tk.Entry(frame_plot, width=50)
    if auto_m2_path:
        entry_m2.insert(0, auto_m2_path)
    entry_m2.grid(row=2, column=1, padx=5, pady=3)
    tk.Button(frame_plot, text=" 更 换 ", command=lambda: browse_file(entry_m2, is_otpu=True)).grid(row=2, column=2, columnspan=2, sticky="we", padx=2)

    # 3. 核心功能操作控制区
    frame_btn = tk.Frame(parent, pady=5)
    frame_btn.pack(fill="x", padx=15)

    btn1 = tk.Button(frame_btn, text="功能 1：仅数据提取", bg="#E1F5FE", fg="black", height=2, command=run_btn1_async)
    btn1.pack(side="left", expand=True, fill="x", padx=5)

    btn2 = tk.Button(frame_btn, text="功能 2：仅自动绘图", bg="#E8F5E9", fg="black", height=2, command=run_btn2_async)
    btn2.pack(side="left", expand=True, fill="x", padx=5)

    btn3 = tk.Button(frame_btn, text="⚡ 功能 3：一键全自动一条龙", bg="#FFF9C4", fg="black", height=2, font=("Helvetica", 9, "bold"), command=run_btn3_async)
    btn3.pack(side="left", expand=True, fill="x", padx=5)

    # 4. 实时运行日志显示框
    frame_log = tk.LabelFrame(parent, text=" 运行日志输出 ")
    frame_log.pack(fill="both", expand=True, padx=15, pady=10)
    
    scrollbar = tk.Scrollbar(frame_log)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    txt_log = tk.Text(frame_log, bg="white", fg="black", font=("Consolas", 9), yscrollcommand=scrollbar.set)
    txt_log.pack(fill="both", expand=True, padx=5, pady=5)
    scrollbar.config(command=txt_log.yview)