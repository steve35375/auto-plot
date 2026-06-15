# ============================================================
# Features/图片批量导出/图片批量导出.py
#
# 功能：批量扫描文件夹内的 Origin 文件，将全部图形页一键导出为图片
#
# ⚡ 关键修复（v2）：移除 Canvas 包装层，直接在 parent 上 pack，
#    与磁光克尔模块保持相同布局方式，内容自动撑满整个标签页。
#
# ⚠  所有送往 Origin 的路径必须使用 Windows 反斜杠 \（见 clean_path）
# ============================================================

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import originpro as op


# ──────────────────────────────────────────────────────────
# 日志重定向：print() → 界面文本框（线程安全，通过 after 回主线程）
# ──────────────────────────────────────────────────────────
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        try:
            self.widget.after(0, self._insert, text)
        except Exception:
            pass

    def _insert(self, text):
        try:
            self.widget.configure(state='normal')
            self.widget.insert('end', text)
            self.widget.see('end')
            self.widget.configure(state='disabled')
        except Exception:
            pass

    def flush(self):
        pass


# ──────────────────────────────────────────────────────────
# 路径净化：强制全反斜杠，规避 Origin 路径拼接 Bug
# ──────────────────────────────────────────────────────────
def clean_path(path: str) -> str:
    return path.strip().replace('/', '\\')


# ──────────────────────────────────────────────────────────
# 插件主界面入口 —— Launcher.py 通过此函数加载本插件
# ──────────────────────────────────────────────────────────
def build_sub_interface(parent):

    FONT_N   = ('Microsoft YaHei', 10)
    FONT_SM  = ('Microsoft YaHei', 9)
    FONT_LOG = ('Consolas', 9)
    P  = {'padx': 6, 'pady': 4}   # 通用单元格 padding
    PX = {'padx': 6}               # 仅水平 padding

    # ════════════════════════════════════════════════════════
    # ── 变量声明区（放在最前，供下方 UI 和函数共享）─────────
    # ════════════════════════════════════════════════════════
    var_src         = tk.StringVar()
    var_dst         = tk.StringVar()
    var_recursive   = tk.BooleanVar(value=True)
    var_subfolder   = tk.BooleanVar(value=True)
    var_fmt         = tk.StringVar(value='PNG')
    var_dpi         = tk.StringVar(value='300')
    var_color       = tk.StringVar(value='彩色 RGB')
    var_transparent = tk.BooleanVar(value=False)
    var_size_mode   = tk.StringVar(value='origin')
    var_width       = tk.StringVar(value='1600')
    var_height      = tk.StringVar(value='1200')
    var_unit        = tk.StringVar(value='像素')
    var_quality     = tk.StringVar(value='90')
    var_naming      = tk.StringVar(value='图表短名称')
    var_progress    = tk.DoubleVar(value=0)
    _file_paths: list = []          # 存储扫描到的 Origin 文件完整路径

    # ════════════════════════════════════════════════════════
    # ① 文件来源设置
    # ════════════════════════════════════════════════════════
    lf1 = ttk.LabelFrame(parent, text='1. 文件来源设置  （选择包含 Origin 文件的文件夹）')
    lf1.pack(fill='x', padx=10, pady=(8, 4))
    lf1.columnconfigure(1, weight=1)   # 第1列（Entry）随窗口拉伸

    # 第0行：路径输入 + 浏览 + 扫描
    ttk.Label(lf1, text='Origin 文件夹：', font=FONT_N).grid(
        row=0, column=0, sticky='w', **P)
    ttk.Entry(lf1, textvariable=var_src).grid(
        row=0, column=1, sticky='ew', **P)

    f_src_btns = ttk.Frame(lf1)
    f_src_btns.grid(row=0, column=2, **P)
    btn_browse_src = ttk.Button(f_src_btns, text='浏 览', width=7)
    btn_browse_src.pack(side='left', padx=(0, 4))
    btn_scan = ttk.Button(f_src_btns, text='🔍 扫描文件夹', width=12)
    btn_scan.pack(side='left')

    # 第1行：递归选项
    ttk.Checkbutton(lf1, text='递归扫描子文件夹（搜索所有层级）',
                    variable=var_recursive).grid(row=1, column=1, sticky='w', padx=6)

    # 第2行：文件列表
    ttk.Label(lf1, text='发现的文件：', font=FONT_N).grid(
        row=2, column=0, sticky='nw', padx=6, pady=4)

    f_lb = ttk.Frame(lf1)
    f_lb.grid(row=2, column=1, columnspan=2, sticky='ew', padx=6, pady=4)

    _lb_ys = ttk.Scrollbar(f_lb, orient='vertical')
    _lb_xs = ttk.Scrollbar(f_lb, orient='horizontal')
    listbox = tk.Listbox(f_lb, selectmode='extended', height=5,
                          font=('Consolas', 9),
                          yscrollcommand=_lb_ys.set, xscrollcommand=_lb_xs.set)
    _lb_ys.config(command=listbox.yview)
    _lb_xs.config(command=listbox.xview)
    _lb_ys.pack(side='right', fill='y')
    _lb_xs.pack(side='bottom', fill='x')
    listbox.pack(fill='both', expand=True)

    # 第3行：多选快捷按钮
    f_sel = ttk.Frame(lf1)
    f_sel.grid(row=3, column=1, sticky='w', padx=6, pady=(0, 6))
    ttk.Button(f_sel, text='全 选', width=7,
               command=lambda: listbox.select_set(0, 'end')).pack(side='left', padx=(0, 3))
    ttk.Button(f_sel, text='取消全选', width=8,
               command=lambda: listbox.select_clear(0, 'end')).pack(side='left', padx=3)
    ttk.Button(f_sel, text='反 选', width=7,
               command=lambda: [
                   listbox.select_set(i) if i not in listbox.curselection()
                   else listbox.select_clear(i)
                   for i in range(listbox.size())
               ]).pack(side='left', padx=3)

    # ════════════════════════════════════════════════════════
    # ② 输出与导出设置
    # ════════════════════════════════════════════════════════
    lf2 = ttk.LabelFrame(parent, text='2. 输出与导出设置')
    lf2.pack(fill='x', padx=10, pady=4)
    lf2.columnconfigure(1, weight=1)

    # 第0行：输出文件夹
    ttk.Label(lf2, text='输出文件夹：', font=FONT_N).grid(
        row=0, column=0, sticky='w', **P)
    ttk.Entry(lf2, textvariable=var_dst).grid(
        row=0, column=1, sticky='ew', **P)
    btn_browse_dst = ttk.Button(lf2, text='浏 览', width=7)
    btn_browse_dst.grid(row=0, column=2, **P)

    # 第1行：子文件夹 + 命名规则
    f_r1 = ttk.Frame(lf2)
    f_r1.grid(row=1, column=0, columnspan=3, sticky='w', padx=6, pady=(0, 2))
    ttk.Checkbutton(f_r1, text='按 Origin 文件名建子文件夹',
                    variable=var_subfolder).pack(side='left', padx=(0, 20))
    ttk.Label(f_r1, text='命名规则：', font=FONT_N).pack(side='left')
    ttk.Combobox(f_r1, textvariable=var_naming, width=24, state='readonly',
                 values=['图表短名称', '图表长名称',
                         'Origin文件名_图表短名称', 'Origin文件名_图表长名称',
                         '三位序号_图表短名称']
                 ).pack(side='left', padx=2)

    # 第2行：图片格式 + DPI + 颜色 + 透明背景
    f_r2 = ttk.Frame(lf2)
    f_r2.grid(row=2, column=0, columnspan=3, sticky='w', padx=6, pady=2)
    ttk.Label(f_r2, text='格式：',     font=FONT_N).pack(side='left')
    ttk.Combobox(f_r2, textvariable=var_fmt, width=7, state='readonly',
                 values=['PNG', 'JPEG', 'TIFF', 'BMP', 'PDF', 'SVG', 'EMF', 'EPS', 'WMF']
                 ).pack(side='left', padx=(2, 14))
    ttk.Label(f_r2, text='分辨率 DPI：', font=FONT_N).pack(side='left')
    ttk.Combobox(f_r2, textvariable=var_dpi, width=6,
                 values=['72', '96', '150', '200', '300', '600', '1200']
                 ).pack(side='left', padx=(2, 14))
    ttk.Label(f_r2, text='颜色：',     font=FONT_N).pack(side='left')
    ttk.Combobox(f_r2, textvariable=var_color, width=10, state='readonly',
                 values=['彩色 RGB', '灰度', '黑白']
                 ).pack(side='left', padx=(2, 14))
    ttk.Checkbutton(f_r2, text='透明背景（PNG）',
                    variable=var_transparent).pack(side='left')

    # 第3行：导出尺寸 + JPEG质量
    f_r3 = ttk.Frame(lf2)
    f_r3.grid(row=3, column=0, columnspan=3, sticky='w', padx=6, pady=(2, 6))
    ttk.Label(f_r3, text='尺寸：',   font=FONT_N).pack(side='left')
    ttk.Radiobutton(f_r3, text='保持原始', variable=var_size_mode, value='origin'
                    ).pack(side='left', padx=(2, 6))
    ttk.Radiobutton(f_r3, text='自定义：', variable=var_size_mode, value='custom'
                    ).pack(side='left')
    ttk.Entry(f_r3, textvariable=var_width,  width=6).pack(side='left', padx=2)
    ttk.Label(f_r3, text='×').pack(side='left')
    ttk.Entry(f_r3, textvariable=var_height, width=6).pack(side='left', padx=2)
    ttk.Combobox(f_r3, textvariable=var_unit, width=5, state='readonly',
                 values=['像素', '厘米', '英寸']).pack(side='left', padx=(2, 22))
    ttk.Label(f_r3, text='JPEG 质量：', font=FONT_N).pack(side='left')
    ttk.Combobox(f_r3, textvariable=var_quality, width=5,
                 values=['60', '70', '80', '85', '90', '95', '100']
                 ).pack(side='left', padx=2)
    ttk.Label(f_r3, text='（矢量格式忽略 DPI/尺寸）',
              font=FONT_SM, foreground='#888888').pack(side='left', padx=(12, 0))

    # ════════════════════════════════════════════════════════
    # 执行区：进度条 + 状态 + 按钮（参照磁光克尔配色方案）
    # ════════════════════════════════════════════════════════
    f_exec = ttk.Frame(parent)
    f_exec.pack(fill='x', padx=10, pady=(4, 6))

    ttk.Progressbar(f_exec, variable=var_progress, maximum=100).pack(
        fill='x', pady=(0, 5))

    f_exec_btns = ttk.Frame(f_exec)
    f_exec_btns.pack(fill='x')

    lbl_status = ttk.Label(f_exec_btns, text='就绪', font=FONT_N)
    lbl_status.pack(side='left', padx=(2, 20))

    # 主操作按钮：黄色高亮（同磁光克尔"功能3"风格）
    btn_run = tk.Button(
        f_exec_btns,
        text='⚡  开始批量导出',
        font=('Microsoft YaHei', 10, 'bold'),
        bg='#FFF176', activebackground='#FFEE58',
        relief='raised', padx=14, pady=4
    )
    btn_run.pack(side='left', padx=(0, 8))

    # 辅助按钮：浅蓝色
    btn_open = tk.Button(
        f_exec_btns,
        text='📂  打开输出文件夹',
        font=FONT_N,
        bg='#B3E5FC', activebackground='#81D4FA',
        padx=10, pady=4
    )
    btn_open.pack(side='left')

    # ════════════════════════════════════════════════════════
    # 运行日志输出（撑满剩余空间，与磁光克尔完全一致）
    # ════════════════════════════════════════════════════════
    lf_log = ttk.LabelFrame(parent, text='运行日志输出')
    lf_log.pack(fill='both', expand=True, padx=10, pady=(0, 8))

    _log_ys = ttk.Scrollbar(lf_log)
    _log_ys.pack(side='right', fill='y')
    log_box = tk.Text(lf_log, state='disabled', font=FONT_LOG,
                       wrap='word', yscrollcommand=_log_ys.set)
    log_box.pack(fill='both', expand=True, padx=4, pady=4)
    _log_ys.config(command=log_box.yview)

    # 接管 sys.stdout → 日志框
    sys.stdout = TextRedirector(log_box)

    # ════════════════════════════════════════════════════════
    # 内部函数（闭包，捕获上方所有 widget 变量）
    # ════════════════════════════════════════════════════════

    def _browse_src():
        d = filedialog.askdirectory(title='选择包含 Origin 文件的文件夹')
        if d:
            var_src.set(clean_path(d))

    def _browse_dst():
        d = filedialog.askdirectory(title='选择图片输出文件夹')
        if d:
            var_dst.set(clean_path(d))

    def _open_output_folder():
        d = clean_path(var_dst.get())
        if d and os.path.isdir(d):
            os.startfile(d)
        else:
            messagebox.showwarning('提示', '输出文件夹不存在，请先执行导出！')

    def _scan():
        src = clean_path(var_src.get())
        if not src or not os.path.isdir(src):
            messagebox.showwarning('提示', '请先填写有效的 Origin 文件夹路径！')
            return
        _file_paths.clear()
        listbox.delete(0, 'end')
        exts = ('.opju', '.opj')
        if var_recursive.get():
            for root_, _, files in os.walk(src):
                for fn in sorted(files):
                    if fn.lower().endswith(exts):
                        _file_paths.append(os.path.join(root_, fn))
        else:
            for fn in sorted(os.listdir(src)):
                if fn.lower().endswith(exts):
                    _file_paths.append(os.path.join(src, fn))
        for fp in _file_paths:
            listbox.insert('end', os.path.relpath(fp, src))
        listbox.select_set(0, 'end')
        print(f'[扫描] 路径：{src}')
        print(f'  → 共发现 {len(_file_paths)} 个 Origin 文件\n')

    # ── 格式对照表 ─────────────────────────────────────────
    _FMT = {
        'PNG':  ('PNG',  'png'),  'JPEG': ('JPEG', 'jpg'),
        'TIFF': ('TIFF', 'tif'),  'BMP':  ('BMP',  'bmp'),
        'PDF':  ('PDF',  'pdf'),  'SVG':  ('SVG',  'svg'),
        'EMF':  ('EMF',  'emf'),  'EPS':  ('EPS',  'eps'),
        'WMF':  ('WMF',  'wmf'),
    }
    _COLOR       = {'彩色 RGB': '0', '灰度': '1', '黑白': '2'}
    _UNIT        = {'像素': '0', '厘米': '1', '英寸': '2'}
    _VECTOR_FMTS = {'PDF', 'SVG', 'EMF', 'EPS', 'WMF'}

    def _sanitize(name: str) -> str:
        """移除 Windows 文件名非法字符"""
        return ''.join(c for c in name if c not in r'\/:*?"<>|').strip()

    def _get_graphs() -> list:
        """
        用 LabTalk doc -e W 循环枚举当前项目所有图形页（page.type==3）
        返回 [{'name': 短名, 'lname': 长名}, ...]
        """
        graphs = []
        try:
            op.lt_exec('string _gdata$; _gdata$ = "";')
            op.lt_exec(
                'doc -e W {'
                '  if (page.type == 3) {'
                '    _gdata$ = _gdata$ + page.name$ + ":::" + page.longname$ + "|";'
                '  }'
                '}'
            )
            # 【这里精确修复】：更正为标准的 get_lt_str
            raw = op.get_lt_str('_gdata$')
            if raw:
                for entry in raw.split('|'):
                    entry = entry.strip()
                    if not entry:
                        continue
                    parts = entry.split(':::')
                    sname = parts[0].strip()
                    lname = (parts[1].strip() if len(parts) > 1 and parts[1].strip()
                             else sname)
                    if sname:
                        graphs.append({'name': sname, 'lname': lname})
        except Exception as e:
            print(f'  [警告] 枚举图形页出错: {e}')
        return graphs

    def _export_one_file(fp: str, dst: str, idx: int, total: int) -> int:
        """打开单个 Origin 文件并导出全部图形页，返回成功数量"""
        fp       = clean_path(fp)
        basename = os.path.splitext(os.path.basename(fp))[0]

        print(f'[{idx}/{total}] ▶  {os.path.basename(fp)}')
        parent.after(0, lbl_status.configure,
                     {'text': f'({idx}/{total}) 处理中：{basename}'})

        # 输出子目录
        out_dir = clean_path(
            os.path.join(dst, basename) if var_subfolder.get() else dst)
        os.makedirs(out_dir, exist_ok=True)

        # 打开 Origin 文件（替换当前项目；不调用 save，不落地）
        try:
            op.open(fp)
            print('  ✔ 文件已打开')
        except Exception as e:
            print(f'  ✘ 打开失败: {e}\n')
            return 0

        graphs = _get_graphs()
        if not graphs:
            print('  ⚠ 未找到任何图形页，跳过。\n')
            return 0
        print(f'  → 发现 {len(graphs)} 个图形页')

        # 读取当前导出参数
        fmt_key = var_fmt.get()
        lt_type, ext = _FMT.get(fmt_key, ('PNG', 'png'))
        dpi     = var_dpi.get().strip()     or '300'
        color   = _COLOR.get(var_color.get(), '0')
        quality = var_quality.get().strip() or '90'
        trans   = '1' if (var_transparent.get() and fmt_key == 'PNG') else '0'
        naming  = var_naming.get()
        is_vec  = fmt_key in _VECTOR_FMTS
        custom  = (var_size_mode.get() == 'custom')

        success   = 0
        name_seen = {}   # 去重计数器

        for seq, gp in enumerate(graphs, start=1):
            sname = gp['name']
            lname = gp['lname']

            # 按命名规则生成文件名（不含扩展名）
            if   naming == '图表短名称':              base = sname
            elif naming == '图表长名称':              base = lname
            elif naming == 'Origin文件名_图表短名称': base = f'{basename}_{sname}'
            elif naming == 'Origin文件名_图表长名称': base = f'{basename}_{lname}'
            else:                                     base = f'{seq:03d}_{sname}'

            base = _sanitize(base) or f'graph_{seq:03d}'

            # 同名去重：后缀追加 _2、_3…
            key = base.lower()
            if key in name_seen:
                name_seen[key] += 1
                base = f'{base}_{name_seen[key]}'
            else:
                name_seen[key] = 1

            # ⚠ 路径必须全反斜杠（Origin 路径拼接 Bug 防护）
            out_no_ext = clean_path(os.path.join(out_dir, base))
            
            # 【这里精准处理】：转换为正斜杠传给 LabTalk，斩断反斜杠导致的转义乱码灾难，彻底解决保存失败
            lt_out_path = out_no_ext.replace('\\', '/')

            try:
                # 构造 expGraph LabTalk 命令，增加指定 page 参数
                cmd_parts = [
                    'expGraph',
                    f'page:="{sname}"',
                    f'type:={lt_type}',
                    f'filename:="{lt_out_path}"',
                ]
                if not is_vec:
                    cmd_parts += [f'dpi:={dpi}', f'color:={color}']
                    if custom:
                        w = var_width.get().strip()  or '1600'
                        h = var_height.get().strip() or '1200'
                        u = _UNIT.get(var_unit.get(), '0')
                        cmd_parts += [f'width:={w}', f'height:={h}',
                                       f'unitsize:={u}']
                if fmt_key == 'JPEG':
                    cmd_parts.append(f'quality:={quality}')
                if fmt_key == 'PNG':
                    cmd_parts.append(f'tr:={trans}')

                op.lt_exec(' '.join(cmd_parts) + ';')

                # 验证文件是否实际落盘
                out_final = f'{out_no_ext}.{ext}'
                if os.path.isfile(out_final):
                    print(f'    ✔ [{sname}]  →  {base}.{ext}')
                    success += 1
                else:
                    print(f'    ⚠ [{sname}]  命令已执行但文件未找到（{base}.{ext}）')

            except Exception as e:
                print(f'    ✘ [{sname}]  导出异常: {e}')

        print(f'  → 本文件导出完成：成功 {success} / {len(graphs)} 张\n')
        return success

    def _run_export():
        """批量导出主流程（后台线程）"""
        parent.after(0, btn_run.configure, {'state': 'disabled'})
        parent.after(0, var_progress.set, 0)

        src      = clean_path(var_src.get())
        dst      = clean_path(var_dst.get())
        selected = listbox.curselection()

        # 参数校验
        if not src or not os.path.isdir(src):
            messagebox.showwarning('参数错误', '请选择有效的 Origin 文件所在文件夹！')
            parent.after(0, btn_run.configure, {'state': 'normal'})
            return
        if not dst:
            messagebox.showwarning('参数错误', '请设置输出文件夹！')
            parent.after(0, btn_run.configure, {'state': 'normal'})
            return
        if not selected:
            messagebox.showwarning('提示', '请在文件列表中至少选择一个 Origin 文件！')
            parent.after(0, btn_run.configure, {'state': 'normal'})
            return

        sel_files = [_file_paths[i] for i in selected]
        os.makedirs(dst, exist_ok=True)
        total    = len(sel_files)
        total_ok = 0

        print(f'{"═" * 54}')
        print(f'  批量导出启动 | 共 {total} 个文件')
        print(f'  格式: {var_fmt.get()}  |  DPI: {var_dpi.get()}  |  命名: {var_naming.get()}')
        print(f'  输出根目录: {dst}')
        print(f'{"═" * 54}\n')

        # 先强行清空可能存在的死连接残留，重置 Python 模块对已关闭 PID 的错误记忆
        try:
            op.exit()
        except:
            pass

        # 使用刚性 try...finally 包裹，不论提取结果成败，最后必须解除控制并强行关闭
        try:
            op.set_show(False)
            for i, fp in enumerate(sel_files, start=1):
                try:
                    total_ok += _export_one_file(fp, dst, i, total)
                except Exception as e:
                    print(f'  ✘ 文件处理异常: {e}\n')
                parent.after(0, var_progress.set, i / total * 100)
        finally:
            try:
                op.exit()
            except:
                pass

            print(f'{"═" * 54}')
            print(f'  🎉 全部完成！共导出 {total_ok} 张图片')
            print(f'  保存位置: {dst}')
            print(f'{"═" * 54}\n')

            parent.after(0, lbl_status.configure,
                         {'text': f'✅ 完成！共导出 {total_ok} 张图片'})
            parent.after(0, btn_run.configure, {'state': 'normal'})

            if messagebox.askyesno('导出完成',
                                   f'共成功导出 {total_ok} 张图片！\n是否立即打开输出文件夹？'):
                os.startfile(dst)

    def _start():
        threading.Thread(target=_run_export, daemon=True).start()

    # ── 绑定按钮命令（函数定义完成后再绑定，避免前向引用问题）──
    btn_browse_src.configure(command=_browse_src)
    btn_scan.configure(command=_scan)
    btn_browse_dst.configure(command=_browse_dst)
    btn_open.configure(command=_open_output_folder)
    btn_run.configure(command=_start)

    # ── 启动提示 ───────────────────────────────────────────
    print('[系统] 图片批量导出模块已加载。')
    print('[步骤]  ① 填写 Origin 文件夹路径并点击"扫描文件夹"')
    print('         ② 在列表中选择要处理的文件（支持 Ctrl/Shift 多选）')
    print('         ③ 设置输出路径与导出格式')
    print('         ④ 点击"⚡ 开始批量导出"\n')