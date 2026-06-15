import os
import io
import sys
import time
import re
import threading
import pandas as pd
import originpro as op
import tkinter as tk
from tkinter import filedialog, messagebox

class TextRedirector:
    """【核心修复点一】：利用 after() 建立线程安全传达室，严禁后台线程直接修改组件，彻底根治假死"""
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
    """清理路径中的引号与空格，并强行统一切换为 Windows 标准反斜杠，杜绝 Origin 备份报错"""
    return path_str.strip().strip('"').strip("'").strip().replace('/', '\\')

def get_summary_file(data_file_name, folder_files):
    """智能前缀反向寻桩：通过长名表智能抠出并对准对应的短名总结表"""
    base, ext = os.path.splitext(data_file_name)
    p1 = re.sub(r'\d{14}$', '', base)
    p2 = re.sub(r'[-_]\d+$', '', base)
    p3 = re.sub(r'[-_][\u4e00-\u9fa5a-zA-Z0-9]+$', '', base)
    
    for p in [p1, p2, p3, base]:
        if p != base and p:
            candidate = p + ext
            for f in folder_files:
                if f.lower() == candidate.lower():
                    return f
    return None

# ================== 🛠️ 核心高通量数据解析与多特征海选去重引擎 ==================

def parse_resistivity_data(long_path):
    """精准解析电阻率数据表：自动定位表头，精准提取 X, Y, Ave 三列核心物理数据"""
    with open(long_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    header_idx = -1
    for i, line in enumerate(lines):
        if 'PointNo' in line and 'X' in line and 'Y' in line:
            header_idx = i
            break
            
    if header_idx == -1:
        raise ValueError("该 CSV 数据表中未寻找到包含 PointNo, X, Y 关键坐标的有效表头")
        
    data_lines = [lines[header_idx].strip()]
    for line in lines[header_idx+1:]:
        if line.strip().startswith('"POINT"') or line.strip().startswith('POINT'):
            data_lines.append(line.strip())
            
    df = pd.read_csv(io.StringIO("\n".join(data_lines)))
    cols = [col.strip().strip('"').strip() for col in df.columns]
    df.columns = cols
    
    idx_x, idx_y, idx_ave = -1, -1, -1
    for idx, col in enumerate(cols):
        if col.lower() == 'x': idx_x = idx
        elif col.lower() == 'y': idx_y = idx
        elif col.lower() == 'ave': idx_ave = idx
        
    if idx_x == -1 or idx_y == -1 or idx_ave == -1:
        for idx, col in enumerate(cols):
            if 'x' in col.lower() and idx_x == -1: idx_x = idx
            elif 'y' in col.lower() and idx_y == -1: idx_y = idx
            elif 'ave' in col.lower() and idx_ave == -1: idx_ave = idx
            
    if idx_x == -1 or idx_y == -1 or idx_ave == -1:
        raise ValueError("表格中缺少必要的 X, Y 坐标或 Ave 电阻率平均值列")
        
    df_clean = df[[cols[idx_x], cols[idx_y], cols[idx_ave]]].copy()
    df_clean.columns = ['X', 'Y', 'Ave']
    
    df_clean['X'] = pd.to_numeric(df_clean['X'], errors='coerce')
    df_clean['Y'] = pd.to_numeric(df_clean['Y'], errors='coerce')
    df_clean['Ave'] = pd.to_numeric(df_clean['Ave'], errors='coerce')
    df_clean = df_clean.dropna()
    
    return df_clean

def find_best_trials_in_total_folder(main_folder):
    """
    大文件夹隔离海选内核：
    1. 样品子文件夹之间绝对空间隔离，拒绝跨仓交叉评比。
    2. 全面测试（249点）和自定义测试通过点数与位置拓扑双重锁定，各自进行错点大比拼。
    """
    if not os.path.exists(main_folder):
        print("❌ 找不到输入的大文件夹路径。")
        return []

    subfolders = [os.path.join(main_folder, d) for d in os.listdir(main_folder) if os.path.isdir(os.path.join(main_folder, d))]
    if not subfolders:
        subfolders = [main_folder]

    final_winners = []
    long_file_pattern = re.compile(r'^(.*)(\d{14})\.[cC][sS][vV]$')

    print("--- 📊 开启电阻率多样品绝对空间隔离海选流水线 ---")

    for subfolder in subfolders:
        folder_name = os.path.basename(subfolder)
        if folder_name.startswith('__') or folder_name.lower() == 'features':
            continue

        print(f"\n🔒 [空间隔离] 正在独立评估样品仓: {folder_name}")
        all_files = os.listdir(subfolder)
        csv_files = [f for f in all_files if f.lower().endswith('.csv')]
        
        data_files_info = []
        for f in csv_files:
            if long_file_pattern.match(f) or ("-" in f and len(f) > len(folder_name) + 8):
                full_path = os.path.join(subfolder, f).replace('/', '\\')
                try:
                    df_data = parse_resistivity_data(full_path)
                    point_count = len(df_data)
                    if point_count == 0:
                        continue
                        
                    summary_f = get_summary_file(f, csv_files)
                    summary_path = os.path.join(subfolder, summary_f) if summary_f else None
                    
                    err_count = 0
                    if summary_path and os.path.exists(summary_path):
                        with open(summary_path, 'r', encoding='utf-8', errors='ignore') as sf:
                            err_count = sf.read().upper().count('ERR')
                    else:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as df_file:
                            err_count = df_file.read().upper().count('ERR')
                    
                    coords_sig = tuple(sorted([(round(row['X'], 2), round(row['Y'], 2)) for _, row in df_data.iterrows()]))
                    
                    data_files_info.append({
                        'filename': f,
                        'full_path': full_path,
                        'df': df_data,
                        'point_count': point_count,
                        'coords_sig': coords_sig,
                        'err_count': err_count
                    })
                except:
                    continue

        if not data_files_info:
            print(f"  --> 该样品仓内未扫描到任何有效结构化长名电阻率数据。")
            continue

        groups = {}
        for item in data_files_info:
            if item['point_count'] == 249:
                key = "comprehensive_249"
            else:
                key = (item['point_count'], item['coords_sig'])
            
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        for key, pool in groups.items():
            if not pool:
                continue
            desc = "249点全面测试组" if key == "comprehensive_249" else f"自定义测试组(点数:{key[0]})"
            print(f"  📦 发现符合 [{desc}] 特征的内部候选批次共 {len(pool)} 个，开始坏点比拼...")
            
            winner = min(pool, key=lambda x: x['err_count'], default=None)
            if winner:
                print(f"    🏆 该组优选胜出: [{winner['filename']}] (异常坏点最少: {winner['err_count']} 个)")
                final_winners.append(winner)

    return final_winners

# ================== 📥 后台静默数据注入与落盘引擎 ==================

def save_trials_to_origin_backend(best_trials, save_dir, origin_file_name):
    """在后台线程中静默控制 Origin 写入，完全杜绝界面假死卡盘"""
    if not origin_file_name.endswith('.opju'):
        origin_file_name += '.opju'
    final_save_path = os.path.join(save_dir, origin_file_name).replace('/', '\\')

    print("\n正在后台静默启动 Origin 进行高通量成果注入...")
    op.set_show(False)
    
    try:
        book = op.new_book('w', 'Resistivity_Summary')
        is_first_sheet = True

        for idx, trial in enumerate(best_trials):
            sheet_name = trial['filename_no_ext'][:30]
            sheet = book[0] if is_first_sheet else book.add_sheet(sheet_name)
            if is_first_sheet:
                sheet.name = sheet_name
                is_first_sheet = False
                
            sheet.from_df(trial['df'])
            sheet.cols_axis('XYZ')
            
            for col_idx in range(3):
                sheet.set_label(col_idx, trial['full_label'], 'C')
            print(f"  [{idx+1}/{len(best_trials)}] 成功向内存填入数据页: {sheet_name}")
            
        if os.path.exists(final_save_path):
            try: os.remove(final_save_path)
            except: pass
            
        op.save(final_save_path)
        print(f"🎉 高通量电阻率数据整合大功告成！项目文件保存在：\n{final_save_path}")
        return final_save_path
    except Exception as e:
        print(f"❌ 后台写入 Origin 时发生意外错误: {e}")
        return None
    finally:
        op.exit()

# ================== 🖥️ 后台车道异步任务执行器 ==================

def gui_extract_batch_worker(root, main_folder, save_dir, origin_file_name):
    winners = find_best_trials_in_total_folder(main_folder)
    if not winners:
        print("❌ 空间隔离海选完毕，未筛选到任何有效候选数据。")
        return
        
    formatted_trials = []
    for w in winners:
        formatted_trials.append({
            'df': w['df'],
            'filename_no_ext': os.path.splitext(w['filename'])[0],
            'full_label': os.path.splitext(w['filename'])[0]
        })
        
    path = save_trials_to_origin_backend(formatted_trials, save_dir, origin_file_name)
    if path:
        root.after(0, lambda: messagebox.showinfo("成功", "大文件夹多样品高通量海选提取整合成功！"))

def gui_extract_direct_csv_worker(root, save_dir, origin_file_name, files_selected):
    formatted_trials = []
    for f_path in files_selected:
        clean_f_path = clean_path(f_path)
        base_name = os.path.basename(clean_f_path)
        try:
            df_data = parse_resistivity_data(clean_f_path)
            formatted_trials.append({
                'df': df_data,
                'filename_no_ext': os.path.splitext(base_name)[0],
                'full_label': os.path.splitext(base_name)[0]
            })
            print(f"  -> [强提成功] 散落原始表: {base_name}")
        except Exception as e:
            print(f"  ❌ 该 CSV 文件不符合标准数据行列格式 [{base_name}]: {e}")
            
    if not formatted_trials:
        print("❌ 未成功强提到任何有效的电阻率数据。")
        return
        
    path = save_trials_to_origin_backend(formatted_trials, save_dir, origin_file_name)
    if path:
        root.after(0, lambda: messagebox.showinfo("成功", "散落 CSV 数据直接强行导入归档成功！"))

def gui_plot_only_worker(root, opju_path, t_path):
    print("\n--- [开始执行：电阻率高通量自动替换绘图] ---")
    print("正在后台静默加载 Origin 项目...")
    op.set_show(False)
    try:
        op.open(opju_path)
        book = op.find_book()
        if not book:
            print("❌ 未在项目中找到有效的数据工作簿 (Book)。")
            return
            
        total_sheets = len(book)
        for index, sheet in enumerate(book):
            sheet_name = sheet.name
            print(f" 绘图渲染进度: [{index + 1}/{total_sheets}] 正在套用电阻率模板: {sheet_name}")
            try:
                graph = sheet.plot_cloneable(t_path)
                if graph:
                    graph.name = f"{sheet_name}_Res"[:30]
            except Exception as plot_err:
                print(f"    --> 工作表 {sheet_name} 电阻率模板套用失败: {plot_err}")
                
        op.save()
        print("🎉 高通量电阻率图全部批量绘制圆满结束！")
        root.after(0, lambda: messagebox.showinfo("成功", "电阻率自动模板绘图已顺利全部完成！"))
    except Exception as e:
        print(f"❌ 批量绘图过程中发生错误: {e}")
    finally:
        op.exit()

def gui_one_click_flow_worker(root, main_folder, save_dir, origin_file_name, t_path):
    print("--- [开始执行：电阻率全自动海选绘图一条龙流水线] ---")
    winners = find_best_trials_in_total_folder(main_folder)
    if not winners:
        print("❌ 未能成功海选出有效资产，流水线中断。")
        return

    if not origin_file_name.endswith('.opju'):
        origin_file_name += '.opju'
    final_save_path = os.path.join(save_dir, origin_file_name).replace('/', '\\')

    print("\n正在后台启动 Origin 连贯进行内存数据注入与直接绘图...")
    op.set_show(False)
    try:
        book = op.new_book('w', 'Resistivity_Summary')
        is_first_sheet = True

        for w in winners:
            sheet_name = os.path.splitext(w['filename'])[0][:30]
            sheet = book[0] if is_first_sheet else book.add_sheet(sheet_name)
            if is_first_sheet:
                sheet.name = sheet_name
                is_first_sheet = False
                
            sheet.from_df(w['df'])
            sheet.cols_axis('XYZ')
            for col_idx in range(3):
                sheet.set_label(col_idx, os.path.splitext(w['filename'])[0], 'C')
                
        print("\n--- 最优数据提取标注完毕，直接在内存中触发模板绘图渲染 ---")
        total_sheets = len(book)
        for index, sheet in enumerate(book):
            sheet_name = sheet.name
            print(f" 绘图流水线进度: [{index + 1}/{total_sheets}] 正在渲染: {sheet_name}")
            try:
                graph = sheet.plot_cloneable(t_path)
                if graph:
                    graph.name = f"{sheet_name}_Res"[:30]
            except Exception as plot_err:
                print(f"    --> 流水线渲染 {sheet_name} 失败: {plot_err}")

        if os.path.exists(final_save_path):
            try: os.remove(final_save_path)
            except: pass
            
        op.save(final_save_path)
        print(f"🎉 电阻率海选一条龙全自动化流水线顺利圆满结束！项目已安全落盘。")
        root.after(0, lambda: messagebox.showinfo("成功", "电阻率一条龙全自动化任务已全部顺利完成！"))
    except Exception as e:
        print(f"❌ 流水线运行中途发生意外错误: {e}")
    finally:
        op.exit()

# ================== 🎨 启动器图形界面高适配布局入口 ==================

def build_sub_interface(parent):
    root = parent.winfo_toplevel()

    # 智能寻找同级目录下的电阻率画图模板 (.otpu)
    current_script_dir = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
    auto_template_path = ""
    if os.path.exists(current_script_dir):
        for f in os.listdir(current_script_dir):
            if f.lower().endswith('.otpu'):
                if 'res' in f.lower() or 'r' in f.lower():
                    auto_template_path = os.path.join(current_script_dir, f).replace('/', '\\')
                    break

    def browse_file(entry_widget, is_folder=False, is_opju=False):
        if is_folder:
            p = filedialog.askdirectory()
        elif is_opju:
            p = filedialog.askopenfilename(filetypes=[("Origin 项目", "*.opju")])
        if p:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, p.replace('/', '\\'))

    def set_buttons_state(state):
        """【核心修复点二】：将误写的 btn2 改正为真实存在的 btn_direct_pick"""
        root.after(0, lambda: btn1.config(state=state))
        root.after(0, lambda: btn_direct_pick.config(state=state))
        root.after(0, lambda: btn3.config(state=state))
        root.after(0, lambda: btn4.config(state=state))

    def run_btn1_async():
        main_folder = entry_src.get()
        save_dir = entry_sdir.get()
        origin_file_name = entry_fname.get().strip()
        if not main_folder or not save_dir or not origin_file_name:
            messagebox.showerror("错误", "大文件夹海选部分的所有输入框都不能为空！")
            return
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try: gui_extract_batch_worker(root, main_folder, save_dir, origin_file_name)
            finally: set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    def run_btn2_async():
        save_dir = entry_sdir.get()
        origin_file_name = entry_fname.get().strip()
        if not save_dir or not origin_file_name:
            messagebox.showerror("错误", "请先在上方设置好‘数据保存文件夹’与‘Origin 项目名称’！")
            return
        files_selected = filedialog.askopenfilenames(filetypes=[("CSV 数据表", "*.csv")])
        if not files_selected:
            return
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try: gui_extract_direct_csv_worker(root, save_dir, origin_file_name, files_selected)
            finally: set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    def run_btn3_async():
        opju_path = clean_path(entry_opju.get())
        t_path = clean_path(entry_template.get())
        if not opju_path or not t_path:
            messagebox.showerror("错误", "Origin 项目路径和模板路径不能为空！")
            return
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try: gui_plot_only_worker(root, opju_path, t_path)
            finally: set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    def run_btn4_async():
        main_folder = entry_src.get()
        save_dir = entry_sdir.get()
        origin_file_name = entry_fname.get().strip()
        t_path = clean_path(entry_template.get())
        if not main_folder or not save_dir or not origin_file_name or not t_path:
            messagebox.showerror("错误", "一条龙流水线的所有输入框都不能为空！")
            return
        txt_log.delete('1.0', tk.END)
        sys.stdout = TextRedirector(txt_log)
        sys.stderr = TextRedirector(txt_log)
        set_buttons_state(tk.DISABLED)
        
        def run():
            try: gui_one_click_flow_worker(root, main_folder, save_dir, origin_file_name, t_path)
            finally: set_buttons_state(tk.NORMAL)
        threading.Thread(target=run, daemon=True).start()

    frame_ext = tk.LabelFrame(parent, text=" 1. 批量大文件夹设置 (支持样品子仓绝对空间隔离与点阵拓扑去重海选) ", padx=10, pady=10)
    frame_ext.pack(fill="x", padx=15, pady=4)

    tk.Label(frame_ext, text="样品总大文件夹:").grid(row=0, column=0, sticky="w", pady=3)
    entry_src = tk.Entry(frame_ext, width=50)
    entry_src.grid(row=0, column=1, padx=5, pady=3)
    tk.Button(frame_ext, text=" 浏 览 ", command=lambda: browse_file(entry_src, is_folder=True)).grid(row=0, column=2, padx=2)

    tk.Label(frame_ext, text="数据保存文件夹:").grid(row=1, column=0, sticky="w", pady=3)
    entry_sdir = tk.Entry(frame_ext, width=50)
    entry_sdir.grid(row=1, column=1, padx=5, pady=3)
    tk.Button(frame_ext, text=" 浏 览 ", command=lambda: browse_file(entry_sdir, is_folder=True)).grid(row=1, column=2, padx=2)

    tk.Label(frame_ext, text="Origin 项目名称:").grid(row=2, column=0, sticky="w", pady=3)
    entry_fname = tk.Entry(frame_ext, width=50)
    entry_fname.insert(0, "高通量电阻率汇总结果.opju")
    entry_fname.grid(row=2, column=1, padx=5, pady=3, sticky="w")

    frame_direct = tk.LabelFrame(parent, text=" 2. 外部散落 CSV 直接强提通道 (免海选过滤，直接提取当前选中的物理数据) ", padx=10, pady=8)
    frame_direct.pack(fill="x", padx=15, pady=4)
    
    tk.Label(frame_direct, text="快捷多选强提:").grid(row=0, column=0, sticky="w")
    btn_direct_pick = tk.Button(frame_direct, text=" 📂 点此多选外部散落 .csv 文件并直接强行提取 ", bg="#E0F7FA", fg="black", padx=20, command=run_btn2_async)
    btn_direct_pick.grid(row=0, column=1, padx=10, sticky="w")

    frame_plot = tk.LabelFrame(parent, text=" 3. 电阻率热力图模板配置 (支持文件夹同级模板自动对准预填) ", padx=10, pady=10)
    frame_plot.pack(fill="x", padx=15, pady=4)

    tk.Label(frame_plot, text="仅画图时的OPJU:").grid(row=0, column=0, sticky="w", pady=3)
    entry_opju = tk.Entry(frame_plot, width=50)
    entry_opju.grid(row=0, column=1, padx=5, pady=3)
    tk.Button(frame_plot, text=" 选 择 ", command=lambda: browse_file(entry_opju, is_opju=True)).grid(row=0, column=2, padx=2)

    tk.Label(frame_plot, text="电阻率模板路径:").grid(row=1, column=0, sticky="w", pady=3)
    entry_template = tk.Entry(frame_plot, width=50)
    if auto_template_path:
        entry_template.insert(0, auto_template_path)
    entry_template.grid(row=1, column=1, padx=5, pady=3)
    tk.Button(frame_plot, text=" 更 换 ", command=lambda: browse_file(entry_template, is_opju=True)).grid(row=1, column=2, padx=2)

    frame_btn = tk.Frame(parent, pady=4)
    frame_btn.pack(fill="x", padx=15)

    btn1 = tk.Button(frame_btn, text="功能 1：批量大文件夹海选提取", bg="#E1F5FE", fg="black", height=2, command=run_btn1_async)
    btn1.pack(side="left", expand=True, fill="x", padx=5)

    btn3 = tk.Button(frame_btn, text="功能 2：仅自动模板绘图", bg="#E8F5E9", fg="black", height=2, command=run_btn3_async)
    btn3.pack(side="left", expand=True, fill="x", padx=5)

    btn4 = tk.Button(frame_btn, text="⚡ 功能 3：大文件夹一键全自动一条龙", bg="#FFF9C4", fg="black", height=2, font=("Helvetica", 9, "bold"), command=run_btn4_async)
    btn4.pack(side="left", expand=True, fill="x", padx=5)

    frame_log = tk.LabelFrame(parent, text=" 运行日志输出 ")
    frame_log.pack(fill="both", expand=True, padx=15, pady=8)
    
    scrollbar = tk.Scrollbar(frame_log)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    txt_log = tk.Text(frame_log, bg="white", fg="black", font=("Consolas", 9), yscrollcommand=scrollbar.set)
    txt_log.pack(fill="both", expand=True, padx=5, pady=5)
    scrollbar.config(command=txt_log.yview)