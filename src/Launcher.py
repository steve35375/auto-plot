import os
import sys
import importlib.util
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import ctypes

# ================== ⚡ 终极环境刚性注入（让 .exe 成为全能环境舱） ==================
try:
    import pandas as pd
    import originpro as op
    from tkinter import filedialog   
    from tkinter import messagebox   
    from tkinter import scrolledtext 
except ImportError:
    pass
# ===============================================================================

# 开启 Windows 高清物理像素感知模式，防止界面发虚模糊
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass

# ------------------ 🌓 全局日间/夜间双色主题矩阵 ------------------
THEMES = {
    "day": {
        "root_bg": "#F5F5F5",
        "bg": "#F5F5F5",
        "fg": "#000000",
        "entry_bg": "#FFFFFF",
        "btn_bg": "#EFEFEF",
        "log_bg": "#FFFFFF",
        "text_fg": "#000000",
        "accent_btn": "#FFF9C4",
        "tab_btn_bg": "#EFEFEF",
        "tab_border": "#D0D0D0"
    },
    "night": {
        "root_bg": "#1E1E1E",
        "bg": "#2D2D2D",
        "fg": "#E0E0E0",
        "entry_bg": "#3D3D3D",
        "btn_bg": "#4A4A4A",
        "log_bg": "#121212",
        "text_fg": "#E0E0E0",
        "accent_btn": "#5C542E",
        "tab_btn_bg": "#333333",
        "tab_border": "#444444"
    }
}

current_mode = "day" 

def apply_theme_to_all(root_window, mode):
    """跨平台高级调色引擎：彻底消灭夜间模式下的左上角白块与白边"""
    t = THEMES[mode]
    
    style = ttk.Style()
    if style.theme_use() != 'clam':
        style.theme_use('clam')
        
    style.configure("TFrame", background=t["bg"])
    style.configure("TLabelframe", background=t["bg"], foreground=t["fg"], bordercolor=t["tab_border"])
    style.configure("TLabelframe.Label", background=t["bg"], foreground=t["fg"])
    style.configure("TLabel", background=t["bg"], foreground=t["fg"])
    
    style.configure("TNotebook", background=t["root_bg"], borderwidth=0, lightcolor=t["root_bg"], darkcolor=t["root_bg"])
    style.configure("TNotebook.Tab", font=("Microsoft YaHei", 11, "bold"), background=t["tab_btn_bg"], foreground=t["fg"], lightcolor=t["tab_border"], darkcolor=t["tab_border"], borderwidth=1, padding=[18, 6])
    style.map("TNotebook.Tab", 
              background=[("selected", t["bg"]), ("active", t["tab_btn_bg"])], 
              foreground=[("selected", t["fg"])])

    def _recurse(widget):
        w_class = widget.winfo_class()
        if w_class in ("Tk", "Frame"):
            widget.configure(background=t["root_bg"] if w_class == "Tk" else t["bg"])
            
        # 【核心修复点】：给文字标签增加安全检查，防止因为读取现代父级背景而闪退
        elif w_class == "Label":
            try:
                p_bg = widget.master.cget("background")
            except:
                p_bg = t["bg"]
            widget.configure(background=p_bg, foreground=t["fg"])
            
        elif w_class == "Labelframe":
            widget.configure(background=t["bg"], foreground=t["fg"])
        elif w_class == "Entry":
            widget.configure(background=t["entry_bg"], foreground=t["fg"], insertbackground=t["fg"])
        elif w_class == "Button":
            try:
                txt = widget.cget("text")
                if "一键" in txt or "⚡" in txt:
                    widget.configure(background=t["accent_btn"], foreground=t["fg"])
                elif "提取" in txt:
                    widget.configure(background=t["btn_bg"] if mode=="night" else "#E1F5FE", foreground=t["fg"])
                elif "绘图" in txt:
                    widget.configure(background=t["btn_bg"] if mode=="night" else "#E8F5E9", foreground=t["fg"])
                else:
                    widget.configure(background=t["btn_bg"], foreground=t["fg"])
            except:
                widget.configure(background=t["btn_bg"], foreground=t["fg"])
        elif w_class == "Text":
            widget.configure(background=t["log_bg"], foreground=t["text_fg"], insertbackground=t["fg"])
            
        for child in widget.winfo_children():
            _recurse(child)
            
    _recurse(root_window)

# ------------------ 主程序构建 ------------------

def main_launcher():
    global current_mode
    root = tk.Tk()
    root.title("高通量数据处理平台")
    
    root.geometry("820x800")
    root.resizable(True, True)

    try:
        for font_name in ["TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"]:
            tkfont.nametofont(font_name).configure(family="Microsoft YaHei", size=10)
    except:
        pass

    # ------------------ 🌓 顶层控制栏 ------------------
    top_bar = ttk.Frame(root)
    top_bar.pack(fill="x", padx=15, pady=(8, 2))
    
    lbl_brand = ttk.Label(top_bar, text="材料高通量数据自动化处理中心", font=("Microsoft YaHei", 10, "italic"))
    lbl_brand.pack(side="left")
    
    def switch_theme_trigger():
        global current_mode
        if current_mode == "day":
            current_mode = "night"
            btn_theme.config(text="☀️ 切换为日间模式")
        else:
            current_mode = "day"
            btn_theme.config(text="🌙 切换为夜间模式")
        apply_theme_to_all(root, current_mode)

    btn_theme = tk.Button(top_bar, text="🌙 切换为夜间模式", font=("Microsoft YaHei", 9), relief="groove", bd=1, padx=10, command=switch_theme_trigger)
    btn_theme.pack(side="right")

    # ------------------ 标签页控制中心 ------------------
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=(5, 12))

    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    features_dir = os.path.join(exe_dir, "Features").replace('\\', '/')
    if not os.path.exists(features_dir):
        os.makedirs(features_dir)

    has_features = False
    if os.path.exists(features_dir):
        for item in os.listdir(features_dir):
            item_path = os.path.join(features_dir, item)
            if os.path.isdir(item_path) and not item.startswith("__"):
                script_name = f"{item}.py"
                file_path = os.path.join(item_path, script_name).replace('\\', '/')
                
                if os.path.exists(file_path):
                    has_features = True
                    feature_title = item
                    
                    tab_outer = ttk.Frame(notebook)
                    notebook.add(tab_outer, text=f" {feature_title} ")
                    
                    tab_outer.grid_rowconfigure(0, weight=1)
                    tab_outer.grid_columnconfigure(0, weight=1)
                    
                    tab_frame = ttk.Frame(tab_outer)
                    tab_frame.grid(row=0, column=0, sticky="")
                    
                    try:
                        spec = importlib.util.spec_from_file_location(feature_title, file_path)
                        module = importlib.util.module_from_spec(spec)
                        
                        if item_path not in sys.path:
                            sys.path.insert(0, item_path)
                            
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, "build_sub_interface"):
                            module.build_sub_interface(tab_frame)
                        else:
                            err_label = tk.Label(tab_frame, text=f"❌ 脚本加载失败：\n{script_name} 中缺少 build_sub_interface 入口", fg="red")
                            err_label.pack(pady=50)
                    except Exception as e:
                        err_label = tk.Label(tab_frame, text=f"❌ 运行脚本出错：\n{e}", fg="red")
                        err_label.pack(pady=50)

    if not has_features:
        empty_frame = ttk.Frame(notebook)
        notebook.add(empty_frame, text=" 欢迎使用 ")
        tip_text = (
            "欢迎使用高通量数据处理平台！\n\n"
            "目前平台内还没有任何功能模块。\n\n"
            "请在软件身边的 Features 文件夹内为新功能建立独立文件夹（例如：磁光克尔），\n"
            "并将核心脚本（例如：磁光克尔.py）放进该独立文件夹内：\n"
            f"{features_dir}\n\n"
            "然后重新打开软件，系统即可自动为您生成对应的功能标签页！"
        )
        tip_label = tk.Label(empty_frame, text=tip_text, justify="left", font=("Microsoft YaHei", 11), padx=25, pady=45)
        tip_label.pack(fill="both")

    apply_theme_to_all(root, current_mode)
    root.mainloop()

if __name__ == '__main__':
    main_launcher()
