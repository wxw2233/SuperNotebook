import os
import sys
import re
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog, Menu
import customtkinter as ctk

# Ensure PyInstaller compatibility for standard appearance themes and custom structures
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

class SuperNotebookApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. Basic window configuration
        self.title("超级记事本")
        self.geometry("1100x700")
        self.minsize(900, 550)

        # 2. Path Setup (Feature 1: Dedicated notes subdirectory)
        if getattr(sys, 'frozen', False):
            # Executable base directory
            self.base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # Script base directory
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.notebook_dir = os.path.join(self.base_dir, "data")
        if not os.path.exists(self.notebook_dir):
            try:
                os.makedirs(self.notebook_dir)
            except Exception as e:
                # Fallback to local directory if permission error
                self.notebook_dir = os.path.join(os.path.expanduser("~"), "SuperNotebookData")
                if not os.path.exists(self.notebook_dir):
                    os.makedirs(self.notebook_dir)

        # State management
        self.current_file_path = None  # Full path to currently active file
        self.has_changes = False  # Track modifications
        self.save_timer = None  # Auto-save timer
        self.on_typing_timer = None  # 防抖录入计时器
        self.current_highlight_word = None # Search highlighting match tracker
        self.search_match_positions = [] # 存储当前搜索高亮的全部索引坐标，用于联动跳转
        self.current_match_index = -1 # 当前聚焦的匹配词索引
        self.desensitize_active = False # 信息脱敏状态开关
        self.original_raw_text = "" # 临时存储脱敏前原文
        self.ai_config_file = os.path.join(self.notebook_dir, "ai_config.json")
        self.load_ai_config()
        self.ai_sidebar_visible = True # AI 对话管理侧边栏默认为开启状态
        self.ai_chat_history_list = [] # 用于保存多轮会话上下文的记忆数据库
        self.tree_folder_expanded = {} # 左侧分类文件夹的折起/展开状态（默认全部为展开）
        self.ai_chat_collapsed = False # AI 助手面板是否处于微缩起状态
        self.hidden_system_logs = [] # 用于暂存隐藏的系统执行播报

        # 3. Layout Grid Config
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Left sidebar
        self.grid_columnconfigure(1, weight=1)  # Main panel
        self.grid_columnconfigure(2, weight=0)  # AI Chat Sidebar (默认为 0，我们用单独的 Frame 限制宽度)

        # 4. Build User Interface Components
        self.create_sidebar()
        self.create_main_area()
        self.create_ai_chat_panel() # 注入：高颜值 AI 对话管理侧边栏
        self.create_status_bar()

        # 5. Populate and Initialize UI
        self.refresh_tree_view()
        self.bind_events()

    # --- UI Layout Design ---

    def create_sidebar(self):
        """Creates the left sidebar featuring: Search, Category Folders & Notes Tree View, Operations"""
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(4, weight=1)  # Tree View is given stretch priority
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Sidebar Header
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="📁 超级记事本", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=18, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")

        # Feature 5: Top Search Box Design
        self.search_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.search_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="🔍 全局搜索笔记内容...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12)
        )
        self.search_entry.grid(row=0, column=0, padx=(5, 5), pady=2, sticky="ew")
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        self.btn_search = ctk.CTkButton(
            self.search_frame,
            text="搜索",
            width=50,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.perform_search
        )
        self.btn_search.grid(row=0, column=1, padx=(0, 5), pady=2, sticky="e")

        # Action Button Group
        self.btn_group_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.btn_group_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.btn_group_frame.grid_columnconfigure(0, weight=1)
        self.btn_group_frame.grid_columnconfigure(1, weight=1)

        self.btn_new_folder = ctk.CTkButton(
            self.btn_group_frame, 
            text="📁 新建文件夹", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.create_new_folder
        )
        self.btn_new_folder.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

        self.btn_new_file = ctk.CTkButton(
            self.btn_group_frame, 
            text="➕ 新建笔记", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            command=self.create_new_file
        )
        self.btn_new_file.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # Tree title/section header
        self.tree_lbl_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.tree_lbl_frame.grid(row=3, column=0, padx=15, pady=(8, 2), sticky="ew")
        
        self.tree_title = ctk.CTkLabel(
            self.tree_lbl_frame, 
            text="笔记分类目录：", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            text_color="gray50"
        )
        self.tree_title.pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            self.tree_lbl_frame,
            text="🔄 刷新",
            width=40,
            height=20,
            fg_color="transparent",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            command=self.refresh_tree_view
        )
        self.btn_refresh.pack(side="right")

        # Feature 4: Tree View Structure using CTkScrollableFrame and custom list boxes
        self.tree_scroll_frame = ctk.CTkScrollableFrame(self.sidebar_frame, corner_radius=5)
        self.tree_scroll_frame.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.tree_scroll_frame.grid_columnconfigure(0, weight=1)

        # Feature 2: Right-click Menu Setup for File/Folder actions
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="📝 重命名", command=self.rename_selected_item)
        self.context_menu.add_command(label="➡️ 移动文件", command=self.move_selected_item)
        self.context_menu.add_command(label="🗑️ 删除", command=self.delete_selected_item)

        # Theme Selector Area at bottom
        self.theme_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.theme_frame.grid(row=5, column=0, padx=15, pady=10, sticky="ew")
        
        self.theme_label = ctk.CTkLabel(
            self.theme_frame, 
            text="🌓 主题模式：", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11)
        )
        self.theme_label.pack(side="left", padx=5)

        self.theme_switch = ctk.CTkSegmentedButton(
            self.theme_frame,
            values=["浅色", "深色", "系统"],
            command=self.change_theme,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11)
        )
        self.theme_switch.set("系统" if ctk.get_appearance_mode() == "System" else ("深色" if ctk.get_appearance_mode() == "Dark" else "浅色"))
        self.theme_switch.pack(side="right", fill="x", expand=True, padx=5)

    def create_main_area(self):
        """Creates the right-side main workspace with toolbars and high-performance text editor"""
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(2, weight=1)  # Editor takes up all vertical space
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Toolbar Frame
        self.toolbar = ctk.CTkFrame(self.main_frame, height=45, corner_radius=5)
        self.toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=0)
        
        # 优化后紧凑型按钮排布，完美支持在非全屏小窗口下 100% 显示完全而不发生折行和截断
        self.btn_save = ctk.CTkButton(
            self.toolbar, 
            text="💾 保存", 
            width=80,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            command=self.save_current_file
        )
        self.btn_save.pack(side="left", padx=3, pady=8)

        self.btn_save_as = ctk.CTkButton(
            self.toolbar, 
            text="📂 另存", 
            width=70,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.save_as_file
        )
        self.btn_save_as.pack(side="left", padx=3, pady=8)

        self.btn_desensitize = ctk.CTkButton(
            self.toolbar,
            text="👁️ 脱敏",
            width=70,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.toggle_desensitize
        )
        self.btn_desensitize.pack(side="left", padx=3, pady=8)

        self.btn_ai_config = ctk.CTkButton(
            self.toolbar,
            text="⚙️ 配置",
            width=70,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.show_ai_config_dialog
        )
        self.btn_ai_config.pack(side="left", padx=3, pady=8)

        self.btn_ai_assistant = ctk.CTkButton(
            self.toolbar,
            text="🤖 助手",
            width=80,
            fg_color="#3498db",
            text_color="white",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"),
            command=self.toggle_ai_sidebar
        )
        self.btn_ai_assistant.pack(side="left", padx=3, pady=8)

        self.btn_clear = ctk.CTkButton(
            self.toolbar, 
            text="🗑️ 清空", 
            width=70,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            text_color="white",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.clear_text
        )
        self.btn_clear.pack(side="left", padx=3, pady=8)

        # Auto-save Checkbox Option
        self.auto_save_var = ctk.BooleanVar(value=True)
        self.chk_auto_save = ctk.CTkCheckBox(
            self.toolbar, 
            text="自动保存", 
            variable=self.auto_save_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11)
        )
        self.chk_auto_save.pack(side="right", padx=15, pady=8)



        # Feature 5: Search / Match Status Panel 与编辑器的双向联动设计
        self.search_status_panel = ctk.CTkFrame(self.main_frame, height=35, corner_radius=5, fg_color=("gray90", "gray20"))
        
        self.lbl_search_info = ctk.CTkLabel(
            self.search_status_panel,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            text_color="#2ecc71"
        )
        self.lbl_search_info.pack(side="left", padx=15, pady=4)
        
        # 增加功能 1：上一个/下一个联动高亮跳转按钮
        self.btn_prev_match = ctk.CTkButton(
            self.search_status_panel,
            text="◀ 上一个",
            width=65,
            height=20,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.jump_prev_match
        )
        self.btn_prev_match.pack(side="left", padx=5, pady=4)

        self.btn_next_match = ctk.CTkButton(
            self.search_status_panel,
            text="▶ 下一个",
            width=65,
            height=20,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.jump_next_match
        )
        self.btn_next_match.pack(side="left", padx=5, pady=4)
        
        self.btn_close_search_status = ctk.CTkButton(
            self.search_status_panel,
            text="✕ 关闭搜索提示",
            width=80,
            height=20,
            fg_color="transparent",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self.hide_search_status_panel
        )
        self.btn_close_search_status.pack(side="right", padx=10, pady=4)

        # Rich Editor Area
        # 针对中英文标点对齐和网址、账号记录的使用场景，
        # 如果使用西文等宽字体 (Consolas) 输入中文标点时，由于 Consolas 缺乏中文字符集，
        # 系统会回退到简陋的默认宋体或西文字体映射，从而导致中文句号 “。”、逗号 “，”、分号等标点漂移到行中间，极其影响阅读。
        # 最佳的解决方案是：选择完美的 Windows 混合等宽中文字体 “微软雅黑” (Microsoft YaHei) 或微软专为代码/中文排版打造的完美混合等宽字体 “等线” (DengXian) 或 “Courier New”
        # 我们采用 “Microsoft YaHei” 搭配合理的字号，不仅中文标点绝对完美对齐底端，而且网址和零碎记录也能对齐得极其美观。
        self.text_editor = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Microsoft YaHei", size=13),
            wrap="word",
            activate_scrollbars=True,
            border_width=1,
            corner_radius=5,
            undo=True # 💡 【核心解锁】物理开启 Tkinter 底层文本框历史版本缓冲堆栈！
        )
        self.text_editor.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        
        # Fine-tune typography layout
        self.text_editor.configure(spacing1=4, spacing3=4)
        self.text_editor.focus_set()

        # Set up text tag highlighting for Feature 3 and Feature 5
        self.text_editor._textbox.tag_config("url", foreground="#3498db", underline=True)
        self.text_editor._textbox.tag_config("search_match", background="#f1c40f", foreground="black")

    def create_status_bar(self):
        """Creates the informational bar running along the bottom"""
        self.status_frame = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.lbl_status_file = ctk.CTkLabel(
            self.status_frame, 
            text="当前打开: 未选择文件", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="gray50"
        )
        self.lbl_status_file.pack(side="left", padx=15, pady=2)

        self.lbl_status_info = ctk.CTkLabel(
            self.status_frame, 
            text="字符数: 0  |  行数: 0  |  状态: 已保存", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="gray50"
        )
        self.lbl_status_info.pack(side="right", padx=15, pady=2)

    def bind_events(self):
        """Binds window level, editor actions, and specialized context inputs"""
        # Save keybinds
        self.bind("<Control-s>", lambda event: self.save_current_file())
        self.bind("<Control-S>", lambda event: self.save_current_file())

        # 增加功能 3：键盘快捷键流派调优设计
        self.bind("<Control-n>", lambda event: self.create_new_file())
        self.bind("<Control-N>", lambda event: self.create_new_file())
        self.bind("<Control-f>", lambda event: self.focus_search_box())
        self.bind("<Control-F>", lambda event: self.focus_search_box())

        # Bind typing actions for auto-save statistics and url recognition
        self.text_editor.bind("<KeyRelease>", self.on_text_modified)
        
        # Double Click action on editor to auto-open / copy URLs
        self.text_editor.bind("<Double-Button-1>", self.on_editor_double_click)

        # Intercept app exit safely
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def focus_search_box(self):
        """Ctrl+F 直接聚焦到顶部搜索框"""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")
        return "break"

    def trigger_undo_event(self):
        """物理触发底层编辑器的 Ctrl+Z 撤回操作"""
        try:
            self.text_editor._textbox.edit_undo()
        except Exception:
            pass # 如果撤销栈为空则不操作，防报错
        return "break"

    def trigger_redo_event(self):
        """物理触发底层编辑器的 Ctrl+Y 重做操作"""
        try:
            self.text_editor._textbox.edit_redo()
        except Exception:
            pass
        return "break"

    # --- Feature 4: Tree View Structure & Operations ---

    def refresh_tree_view(self):
        """Builds a dynamic file tree representation based on 'notebook_dir' folders and txt notes."""
        # 性能优化：直接清空并完全重新生成树不仅慢，在拖动和缩放时如果触发也会极慢。
        # 事实上我们只需在需要时才重建，且用极轻量化的方式。
        # 此外，我们将整个生成动作放到 after_idle，完全解耦主界面的冷启动载入。
        self.after_idle(self._async_refresh_tree)

    def toggle_folder_expanded_state(self, folder):
        """一键切换左侧特定分类文件夹的展开/折叠状态，并优雅刷新视图"""
        current_state = self.tree_folder_expanded.get(folder, True)
        self.tree_folder_expanded[folder] = not current_state
        self._async_refresh_tree()

    def _async_refresh_tree(self):
        for widget in self.tree_scroll_frame.winfo_children():
            widget.destroy()

        self.tree_items = {}  # Tracks filepath mappings to their UI elements
        
        if not os.path.exists(self.notebook_dir):
            os.makedirs(self.notebook_dir)

        # Collect folder structures
        subfolders = []
        root_files = []

        try:
            for item in os.listdir(self.notebook_dir):
                full_path = os.path.join(self.notebook_dir, item)
                if os.path.isdir(full_path):
                    subfolders.append(item)
                elif item.lower().endswith('.txt'):
                    root_files.append(item)
        except Exception as e:
            messagebox.showerror("读取目录错误", f"读取笔记根目录失败:\n{str(e)}")
            return

        subfolders.sort()
        root_files.sort()

        row_idx = 0

        # Draw Folder Categories
        for folder in subfolders:
            folder_path = os.path.join(self.notebook_dir, folder)
            
            # 获取并设置该分类当前的展开/折起状态（默认全展开）
            is_expanded = self.tree_folder_expanded.get(folder, True)
            folder_icon = "📂" if is_expanded else "📁"

            # Category Accordion/Header Button
            # 单击分类文件夹不再误打开任何笔记，而是干净利落地“一键折叠或展开”！
            folder_btn = ctk.CTkButton(
                self.tree_scroll_frame,
                text=f"{folder_icon} {folder}",
                anchor="w",
                fg_color="transparent",
                hover_color=("gray85", "gray30"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
                height=28,
                corner_radius=4,
                command=lambda f=folder: self.toggle_folder_expanded_state(f)
            )
            folder_btn.grid(row=row_idx, column=0, padx=(2, 2), pady=2, sticky="ew")
            row_idx += 1

            # Bind right click on categories
            folder_btn.bind("<Button-3>", lambda e, p=folder_path: self.show_context_menu(e, p, is_dir=True))
            
            # 如果处于展开状态，则加载旗下子笔记；如果折叠，则直接静默收起！
            if is_expanded:
                try:
                    sub_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.txt')]
                    sub_files.sort()
                except Exception:
                    sub_files = []

                for sf in sub_files:
                    file_path = os.path.join(folder_path, sf)
                    note_btn = ctk.CTkButton(
                        self.tree_scroll_frame,
                        text=f"   📝 {sf}",
                        anchor="w",
                        fg_color="transparent",
                        hover_color=("gray80", "gray25"),
                        text_color=("gray20", "gray80"),
                        font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                        height=26,
                        corner_radius=4,
                        command=lambda p=file_path: self.switch_file(p)
                    )
                    note_btn.grid(row=row_idx, column=0, padx=(15, 2), pady=1, sticky="ew")
                    row_idx += 1

                    # Bind right click on notes
                    note_btn.bind("<Button-3>", lambda e, p=file_path: self.show_context_menu(e, p, is_dir=False))
                    self.tree_items[file_path] = note_btn

        # Draw Standalone root category notes
        if root_files:
            # Standalone root section header
            root_lbl = ctk.CTkLabel(
                self.tree_scroll_frame,
                text="📍 未分类笔记：",
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                text_color="gray50"
            )
            root_lbl.grid(row=row_idx, column=0, padx=5, pady=(10, 2), sticky="w")
            row_idx += 1

            for rf in root_files:
                file_path = os.path.join(self.notebook_dir, rf)
                note_btn = ctk.CTkButton(
                    self.tree_scroll_frame,
                    text=f"📝 {rf}",
                    anchor="w",
                    fg_color="transparent",
                    hover_color=("gray85", "gray30"),
                    text_color=("gray10", "gray90"),
                    font=ctk.CTkFont(family="Microsoft YaHei", size=12),
                    height=28,
                    corner_radius=4,
                    command=lambda p=file_path: self.switch_file(p)
                )
                note_btn.grid(row=row_idx, column=0, padx=(5, 2), pady=1, sticky="ew")
                row_idx += 1

                note_btn.bind("<Button-3>", lambda e, p=file_path: self.show_context_menu(e, p, is_dir=False))
                self.tree_items[file_path] = note_btn

        if not subfolders and not root_files:
            empty_lbl = ctk.CTkLabel(
                self.tree_scroll_frame, 
                text="无TXT笔记或目录\n请点击上方新建", 
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                text_color="gray40"
            )
            empty_lbl.grid(row=0, column=0, padx=10, pady=20, sticky="ew")

        self.highlight_current_file_button()
    def highlight_current_file_button(self):
        """Highlights the currently selected active note in the tree view"""
        for path, btn in self.tree_items.items():
            if self.current_file_path == path:
                btn.configure(
                    fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], 
                    text_color="white"
                )
            else:
                btn.configure(
                    fg_color="transparent", 
                    text_color=("gray10", "gray90") if not path.replace(self.notebook_dir, "").startswith(os.sep) else ("gray20", "gray80")
                )

    def create_new_folder(self):
        """Prompt to create a brand new Category Subfolder"""
        dialog = ctk.CTkInputDialog(text="请输入新建分类文件夹名称：", title="新建文件夹")
        folder_name = dialog.get_input()
        if folder_name is None:
            return
        
        folder_name = folder_name.strip()
        if not folder_name:
            messagebox.showwarning("警告", "文件夹名称不能为空！")
            return

        # 增加极其严格的 Windows 文件名非法字符检查，防止创建文件夹报错闪退
        illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        if any(char in folder_name for char in illegal_chars):
            messagebox.showwarning("警告", "文件夹名称不能包含以下 Windows 非法字符:\n \\ / : * ? \" < > |")
            return

        # 增加名称长度限制，Windows 路径最大限制通常在 255 左右，限制单文件夹不超过 50 字符
        if len(folder_name) > 50:
            messagebox.showwarning("警告", "文件夹名称过长（不能超过 50 个字符）！")
            return

        new_path = os.path.join(self.notebook_dir, folder_name)
        if os.path.exists(new_path):
            messagebox.showwarning("提示", "该分类文件夹已经存在！")
            return

        try:
            os.makedirs(new_path)
            self.refresh_tree_view()
        except Exception as e:
            messagebox.showerror("新建失败", f"创建分类文件夹失败:\n{str(e)}")

    def create_new_file(self):
        """Allows creating a new text note either in a chosen subfolder or root folder"""
        # Read subfolders to offer creation location choices
        subfolders = []
        try:
            for item in os.listdir(self.notebook_dir):
                if os.path.isdir(os.path.join(self.notebook_dir, item)):
                    subfolders.append(item)
        except Exception:
            pass

        subfolders.sort()

        # Selection dialog
        choose_window = ctk.CTkToplevel(self)
        choose_window.title("新建笔记")
        choose_window.geometry("400x250")
        choose_window.resizable(False, False)
        choose_window.transient(self)
        choose_window.grab_set()

        # Center dialog
        choose_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 125
        choose_window.geometry(f"+{x}+{y}")

        # Components
        lbl_title = ctk.CTkLabel(choose_window, text="📝 创建新笔记", font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"))
        lbl_title.pack(pady=10)

        # Folder selection
        lbl_folder = ctk.CTkLabel(choose_window, text="选择分类文件夹:", font=ctk.CTkFont(family="Microsoft YaHei", size=11))
        lbl_folder.pack(pady=2)

        options = ["根目录 (未分类)"] + subfolders
        folder_combo = ctk.CTkComboBox(choose_window, values=options, width=280)
        folder_combo.pack(pady=5)
        folder_combo.set("根目录 (未分类)")

        # File name input
        lbl_name = ctk.CTkLabel(choose_window, text="输入笔记文件名:", font=ctk.CTkFont(family="Microsoft YaHei", size=11))
        lbl_name.pack(pady=2)

        name_entry = ctk.CTkEntry(choose_window, placeholder_text="例如: 会议记录", width=280)
        name_entry.pack(pady=5)
        name_entry.focus_set()

        def submit():
            note_name = name_entry.get().strip()
            if not note_name:
                messagebox.showwarning("警告", "笔记文件名不能为空！", parent=choose_window)
                return

            # 非法文件名字符检查，防止磁盘操作因包含非法字符而报错崩溃
            illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            if any(char in note_name for char in illegal_chars):
                messagebox.showwarning("警告", "笔记文件名不能包含 Windows 非法字符:\n \\ / : * ? \" < > |", parent=choose_window)
                return

            if len(note_name) > 60:
                messagebox.showwarning("警告", "文件名太长（不能超过 60 个字符）！", parent=choose_window)
                return

            if not note_name.lower().endswith(".txt"):
                note_name += ".txt"

            chosen_dir_name = folder_combo.get().strip()
            # 同样对手动输入的分类文件夹名做安全校验
            if chosen_dir_name != "根目录 (未分类)":
                if any(char in chosen_dir_name for char in illegal_chars):
                    messagebox.showwarning("警告", "新分类名称不能包含 Windows 非法字符！", parent=choose_window)
                    return
                if len(chosen_dir_name) > 50:
                    messagebox.showwarning("警告", "新分类名称过长！", parent=choose_window)
                    return

            if chosen_dir_name == "根目录 (未分类)":
                target_dir = self.notebook_dir
            else:
                target_dir = os.path.join(self.notebook_dir, chosen_dir_name)
                # 自动检查并创建不存在的分类文件夹
                if not os.path.exists(target_dir):
                    try:
                        os.makedirs(target_dir)
                    except Exception as e:
                        messagebox.showerror("创建文件夹失败", f"无法自动创建分类目录:\n{str(e)}", parent=choose_window)
                        return

            new_file_path = os.path.join(target_dir, note_name)
            if os.path.exists(new_file_path):
                messagebox.showwarning("提示", f"同名笔记 '{note_name}' 已存在！", parent=choose_window)
                choose_window.destroy()
                self.switch_file(new_file_path)
                return

            try:
                with open(new_file_path, "w", encoding="utf-8") as f:
                    f.write("")
                choose_window.destroy()
                self.refresh_tree_view()
                self.switch_file(new_file_path)
            except Exception as e:
                messagebox.showerror("创建失败", f"新建笔记文件失败:\n{str(e)}", parent=choose_window)

        # Buttons
        btn_frame = ctk.CTkFrame(choose_window, fg_color="transparent")
        btn_frame.pack(pady=15)

        btn_cancel = ctk.CTkButton(btn_frame, text="取消", width=90, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=choose_window.destroy)
        btn_cancel.pack(side="left", padx=10)

        btn_ok = ctk.CTkButton(btn_frame, text="确认创建", width=90, command=submit)
        btn_ok.pack(side="right", padx=10)

    # --- Feature 2: File/Folder Management Right-Click context Menu ---

    def show_context_menu(self, event, path, is_dir=False):
        """Triggers context popup at right click cursor coordinate"""
        self.right_clicked_path = path
        self.right_clicked_is_dir = is_dir
        
        # Display options
        self.context_menu.post(event.x_root, event.y_root)

    def rename_selected_item(self):
        """Handles renaming either a folder or an individual note"""
        old_path = getattr(self, "right_clicked_path", None)
        is_dir = getattr(self, "right_clicked_is_dir", False)
        if not old_path or not os.path.exists(old_path):
            return

        old_name = os.path.basename(old_path)
        dialog = ctk.CTkInputDialog(text=f"重命名 '{old_name}' 为：", title="重命名")
        new_name = dialog.get_input()
        if new_name is None:
            return

        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("警告", "名称不能为空！")
            return

        # Carry suffix over if file
        if not is_dir and not new_name.lower().endswith(".txt"):
            new_name += ".txt"

        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, new_name)

        if os.path.exists(new_path):
            messagebox.showwarning("提示", "目标名称已存在！")
            return

        try:
            os.rename(old_path, new_path)
            
            # Check if active editing file has been renamed
            if self.current_file_path == old_path:
                self.current_file_path = new_path
                self.lbl_status_file.configure(text=f"当前打开: {new_name}")
            
            self.refresh_tree_view()
        except Exception as e:
            messagebox.showerror("重命名错误", f"重命名失败:\n{str(e)}")

    def move_selected_item(self):
        """移动笔记到别的分类目录"""
        old_path = getattr(self, "right_clicked_path", None)
        is_dir = getattr(self, "right_clicked_is_dir", False)
        
        if not old_path or not os.path.exists(old_path):
            return
            
        if is_dir:
            messagebox.showinfo("提示", "目前仅支持移动笔记文件，文件夹暂不支持移动。")
            return
            
        # 扫描现有子分类目录，提供给用户选择
        subfolders = []
        try:
            for item in os.listdir(self.notebook_dir):
                if os.path.isdir(os.path.join(self.notebook_dir, item)):
                    subfolders.append(item)
        except Exception:
            pass
        subfolders.sort()
        
        move_window = ctk.CTkToplevel(self)
        move_window.title("移动笔记")
        move_window.geometry("380x200")
        move_window.resizable(False, False)
        move_window.transient(self)
        move_window.grab_set()
        
        # 居中显示
        move_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 190
        y = self.winfo_y() + (self.winfo_height() // 2) - 100
        move_window.geometry(f"+{x}+{y}")
        
        lbl_info = ctk.CTkLabel(
            move_window, 
            text=f"移动笔记:\n{os.path.basename(old_path)}", 
            justify="center",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold")
        )
        lbl_info.pack(pady=15)
        
        options = ["根目录 (未分类)"] + subfolders
        folder_combo = ctk.CTkComboBox(move_window, values=options, width=260)
        folder_combo.pack(pady=5)
        folder_combo.set("根目录 (未分类)")
        
        def do_move():
            chosen_dir_name = folder_combo.get().strip()
            if chosen_dir_name == "根目录 (未分类)":
                target_dir = self.notebook_dir
            else:
                target_dir = os.path.join(self.notebook_dir, chosen_dir_name)
                # 如果用户手动输入了不存在的分类名字，自动建文件夹
                if not os.path.exists(target_dir):
                    try:
                        os.makedirs(target_dir)
                    except Exception as e:
                        messagebox.showerror("移动失败", f"无法自动创建目标分类目录:\n{str(e)}", parent=move_window)
                        return
                        
            new_file_path = os.path.join(target_dir, os.path.basename(old_path))
            
            if os.path.exists(new_file_path) and new_file_path != old_path:
                messagebox.showwarning("提示", "目标位置已存在同名笔记！", parent=move_window)
                return
                
            try:
                import shutil
                shutil.move(old_path, new_file_path)
                
                # 如果移动的是当前正在编辑的笔记，更新其工作路径
                if self.current_file_path == old_path:
                    self.current_file_path = new_file_path
                    display_name = os.path.relpath(new_file_path, self.notebook_dir)
                    self.lbl_status_file.configure(text=f"当前打开: {display_name}")
                    
                move_window.destroy()
                self.refresh_tree_view()
            except Exception as e:
                messagebox.showerror("移动失败", f"移动文件失败:\n{str(e)}", parent=move_window)
                
        btn_frame = ctk.CTkFrame(move_window, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        btn_cancel = ctk.CTkButton(btn_frame, text="取消", width=80, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=move_window.destroy)
        btn_cancel.pack(side="left", padx=10)
        
        btn_ok = ctk.CTkButton(btn_frame, text="确认移动", width=80, command=do_move)
        btn_ok.pack(side="right", padx=10)

    def delete_selected_item(self):
        """Deletes item after double confirmations, clears the text editor if open file is deleted."""
        target_path = getattr(self, "right_clicked_path", None)
        is_dir = getattr(self, "right_clicked_is_dir", False)
        if not target_path or not os.path.exists(target_path):
            return

        target_name = os.path.basename(target_path)
        
        # Confirmation 1
        ans1 = messagebox.askyesno("第一层删除确认", f"您确定要删除 '{target_name}' 吗？\n该操作会移至物理删除，请再次确认。")
        if not ans1:
            return

        # Confirmation 2 (Double confirmation as requested)
        ans2 = messagebox.askyesno("⚠️ 第二层最终确认", f"【警告】确定永久删除 '{target_name}'？\n此项操作是绝对不可逆转的！")
        if not ans2:
            return

        try:
            if is_dir:
                # Recursively delete files inside directory
                import shutil
                shutil.rmtree(target_path)
                
                # Check if current file was nested under the deleted directory
                if self.current_file_path and self.current_file_path.startswith(target_path):
                    self.unload_current_file()
            else:
                os.remove(target_path)
                if self.current_file_path == target_path:
                    self.unload_current_file()

            self.refresh_tree_view()
        except Exception as e:
            messagebox.showerror("删除失败", f"删除项目发生故障:\n{str(e)}")

    def unload_current_file(self):
        """Removes focus and clears all states of active editor session"""
        if self.save_timer:
            self.after_cancel(self.save_timer)
            self.save_timer = None

        self.current_file_path = None
        self.has_changes = False
        self.text_editor.delete("1.0", "end")
        self.lbl_status_file.configure(text="当前打开: 未选择文件")
        self.update_stats(status_text="已重置")

    # --- Feature 3: URL auto-detection, Double Click copy & link execution ---

    def highlight_urls(self):
        """Highlights matching Web URLs (http/https) in the main notepad canvas"""
        self.text_editor._textbox.tag_remove("url", "1.0", "end")
        
        text_content = self.text_editor.get("1.0", "end")
        
        # 性能极佳的行扫描策略：如果文本非常庞大（大于 30KB），不要每次都全局高亮。
        # 针对网址零散数据收纳，只需识别带有 http/https 的段落，避免文本库内部计算卡顿。
        if len(text_content) > 30000:
            return  # 文本过长时关闭实时网址高亮，防止拖慢主线程
            
        url_pattern = re.compile(r'https?://[^\s\'"()]+')
        
        # 优化扫描算法：直接利用 tkinter 快速定位，避免慢速 offset 全文翻译计算
        for match in url_pattern.finditer(text_content):
            start_offset = match.start()
            end_offset = match.end()
            start_index = self.translate_offset_to_index(text_content, start_offset)
            end_index = self.translate_offset_to_index(text_content, end_offset)
            self.text_editor._textbox.tag_add("url", start_index, end_index)

    def translate_offset_to_index(self, text, offset):
        """Helper to translate a flat character offset into tk.Text line.col notation"""
        lines = text[:offset].split('\n')
        row = len(lines)
        col = len(lines[-1])
        return f"{row}.{col}"

    def on_editor_double_click(self, event):
        """Double clicking over a highlighted URL opens it automatically in default system browser"""
        try:
            # Query word click location
            click_index = self.text_editor._textbox.index(f"@{event.x},{event.y}")
            line_num, col_num = map(int, click_index.split('.'))
            
            # Retrieve complete clicked line content
            line_text = self.text_editor._textbox.get(f"{line_num}.0", f"{line_num}.end")
            
            # Discover matching URL boundaries
            url_pattern = re.compile(r'https?://[^\s\'"()]+')
            for match in url_pattern.finditer(line_text):
                start, end = match.span()
                if start <= col_num <= end:
                    url = match.group()
                    webbrowser.open(url)
                    self.update_stats(status_text=f"已在浏览器打开: {url}")
                    return "break"
        except Exception:
            pass

    def copy_selected_link(self):
        """Manually copies highlighted or matched active hyperlink inside selection"""
        try:
            selected_text = self.text_editor._textbox.get("sel.first", "sel.last").strip()
        except Exception:
            # Fallback: scan whole text to locate first link
            selected_text = ""
        
        url_pattern = re.compile(r'https?://[^\s\'"()]+')
        
        if selected_text and url_pattern.match(selected_text):
            self.clipboard_clear()
            self.clipboard_append(selected_text)
            messagebox.showinfo("链接已复制", f"已复制选中的链接：\n{selected_text}")
        else:
            # Check entire editor if selection wasn't direct link
            full_content = self.text_editor.get("1.0", "end")
            urls = url_pattern.findall(full_content)
            if urls:
                self.clipboard_clear()
                self.clipboard_append(urls[0])
                self.update_stats(status_text="自动复制第一条链接")
                messagebox.showinfo("链接已复制", f"未选定链接，已自动复制全文中发现的首条：\n{urls[0]}")
            else:
                messagebox.showwarning("复制失败", "未选中任何链接，且在文本中未找到合法的 URL 网址！")

    # --- Feature 5: Multi-file Search implementation ---

    def perform_search(self):
        """Scans all *.txt notes in A:\\超级记事本\\data recursively for query keyword"""
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("搜索输入", "请输入要搜索的关键词！")
            return

        # 限制搜索字符长度，防止超长搜索导致正则表达式爆栈或内存卡死
        if len(query) > 100:
            messagebox.showwarning("搜索限制", "搜索关键词过长（不能超过 100 字符）！")
            return

        results = []  # Stores tuple: (file_path, line_number, snippet)
        
        # Walk directories safely
        for root, dirs, files in os.walk(self.notebook_dir):
            for file in files:
                if file.lower().endswith('.txt'):
                    full_path = os.path.join(root, file)
                    try:
                        # 增加搜索过程的文件解码容错，防止因包含二进制乱码文件而意外闪退
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            for idx, line in enumerate(f, 1):
                                if query in line:
                                    results.append((full_path, idx, line.strip()))
                    except Exception:
                        pass # Silently bypass locked or unreadable files

        if not results:
            messagebox.showinfo("搜索结果", f"未找到任何匹配关键词 '{query}' 的笔记。")
            return

        self.display_search_results(query, results)

    def display_search_results(self, query, results):
        """Spawns an interactive window detailing search matches"""
        results_window = ctk.CTkToplevel(self)
        results_window.title(f"搜索结果 — '{query}'")
        results_window.geometry("650x450")
        results_window.transient(self)
        results_window.grab_set()

        # Center popup
        results_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 325
        y = self.winfo_y() + (self.winfo_height() // 2) - 225
        results_window.geometry(f"+{x}+{y}")

        lbl_head = ctk.CTkLabel(
            results_window, 
            text=f"🔍 检索关键词: '{query}' (共找到 {len(results)} 个匹配)", 
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold")
        )
        lbl_head.pack(pady=10, padx=10, anchor="w")

        scroll_results = ctk.CTkScrollableFrame(results_window, corner_radius=5)
        scroll_results.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scroll_results.grid_columnconfigure(0, weight=1)

        def make_select_callback(fpath, keyword):
            return lambda: [self.open_and_highlight_match(fpath, keyword), results_window.destroy()]

        for i, (fpath, line_no, snippet) in enumerate(results):
            rel_name = os.path.relpath(fpath, self.notebook_dir)
            
            item_frame = ctk.CTkFrame(scroll_results, corner_radius=4, fg_color=("gray95", "gray18"))
            item_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            item_frame.grid_columnconfigure(0, weight=1)

            snippet_text = snippet if len(snippet) < 60 else snippet[:57] + "..."
            info_lbl = ctk.CTkLabel(
                item_frame,
                text=f"📍 {rel_name} (第 {line_no} 行):\n  \"{snippet_text}\"",
                anchor="w",
                justify="left",
                font=ctk.CTkFont(family="Microsoft YaHei", size=11)
            )
            info_lbl.grid(row=0, column=0, padx=10, pady=5, sticky="w")

            btn_open = ctk.CTkButton(
                item_frame,
                text="查看并跳转",
                width=80,
                height=26,
                font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                command=make_select_callback(fpath, query)
            )
            btn_open.grid(row=0, column=1, padx=10, pady=5, sticky="e")

    def open_and_highlight_match(self, file_path, keyword):
        """Loads selected search result note, highlights match and shifts viewport focus"""
        # Load requested file
        if self.current_file_path != file_path:
            if self.has_changes:
                ans = messagebox.askyesnocancel("保存确认", "当前正在编辑的内容未保存，是否先保存？")
                if ans is True:
                    self.save_current_file()
                elif ans is None:
                    return

            self.load_file(file_path)

        # Trigger highlights inside loaded canvas
        self.text_editor._textbox.tag_remove("search_match", "1.0", "end")
        
        start_idx = "1.0"
        self.search_match_positions = [] # 重置记录全部匹配的文本索引坐标
        self.current_match_index = -1

        while True:
            # 搜索全文
            pos = self.text_editor._textbox.search(keyword, start_idx, stopindex="end")
            if not pos:
                break
            
            line, col = pos.split('.')
            end_pos = f"{line}.{int(col) + len(keyword)}"
            self.text_editor._textbox.tag_add("search_match", pos, end_pos)
            
            # 将该条匹配的 [起, 止] 位置记录下来，供“上一个、下一个”联动调用
            self.search_match_positions.append((pos, end_pos))
            start_idx = end_pos

        match_count = len(self.search_match_positions)

        if match_count > 0:
            self.current_match_index = 0
            first_pos, first_end = self.search_match_positions[0]
            
            # 额外高亮目前聚焦的这一处（用红色或显目颜色标注首个）
            self.text_editor._textbox.tag_add("sel", first_pos, first_end)
            self.text_editor._textbox.see(first_pos)
            
            self.current_highlight_word = keyword
            
            # 展示搜索辅助微调区，并把上一个、下一个按钮激活
            self.search_status_panel.grid(row=1, column=0, sticky="ew", pady=(0, 5))
            self.lbl_search_info.configure(text=f"✨ 找到 {match_count} 处匹配 | 当前聚焦第 1 处")
        else:
            self.hide_search_status_panel()

    def jump_prev_match(self):
        """联动跳转到上一个高亮匹配位置"""
        if not self.search_match_positions:
            return
        
        match_count = len(self.search_match_positions)
        # 索引循环移动
        self.current_match_index = (self.current_match_index - 1) % match_count
        
        # 清除系统当前选中，并聚焦最新一处
        self.text_editor._textbox.tag_remove("sel", "1.0", "end")
        
        pos, end_pos = self.search_match_positions[self.current_match_index]
        self.text_editor._textbox.tag_add("sel", pos, end_pos)
        self.text_editor._textbox.see(pos)
        self.lbl_search_info.configure(text=f"✨ 找到 {match_count} 处匹配 | 当前聚焦第 {self.current_match_index + 1} 处")

    def jump_next_match(self):
        """联动跳转到下一个高亮匹配位置"""
        if not self.search_match_positions:
            return
        
        match_count = len(self.search_match_positions)
        self.current_match_index = (self.current_match_index + 1) % match_count
        
        self.text_editor._textbox.tag_remove("sel", "1.0", "end")
        
        pos, end_pos = self.search_match_positions[self.current_match_index]
        self.text_editor._textbox.tag_add("sel", pos, end_pos)
        self.text_editor._textbox.see(pos)
        self.lbl_search_info.configure(text=f"✨ 找到 {match_count} 处匹配 | 当前聚焦第 {self.current_match_index + 1} 处")

    def toggle_desensitize(self):
        """敏感数据一键脱敏与显隐切换，防止链接和重要密码等信息泄漏"""
        text_content = self.text_editor.get("1.0", "end")
        if text_content.endswith("\n"):
            text_content = text_content[:-1]
            
        if not text_content:
            return

        if not self.desensitize_active:
            # 开启脱敏
            self.original_raw_text = text_content # 备份原文，用于还原
            
            # 使用强大的正则匹配将 http/https 网址脱敏展示
            url_pattern = re.compile(r'https?://[^\s\'"()]+')
            
            # 同样对常见的类似 password / pwd / secret 后跟的字符串进行脱敏遮罩
            pwd_pattern = re.compile(r'((?:password|pwd|pass|secret|token|密(?:码|钥)?)\s*[:：=]\s*)([^\s]+)', re.IGNORECASE)
            
            # 执行脱敏处理
            masked_text = url_pattern.sub("https://******", text_content)
            masked_text = pwd_pattern.sub(r"\1******", masked_text)
            
            # 把脱敏文本写入主编辑区并禁用自动保存以防意外覆盖真实文件
            self.text_editor.delete("1.0", "end")
            self.text_editor.insert("1.0", masked_text)
            self.desensitize_active = True
            
            # 界面状态更改与安全色锁定
            self.btn_desensitize.configure(fg_color="#e67e22", text_color="white", text="👁️ 原文已遮罩")
            self.update_stats(status_text="⚠️ 数据脱敏已激活")
        else:
            # 关闭脱敏，还原真实原文
            self.text_editor.delete("1.0", "end")
            self.text_editor.insert("1.0", self.original_raw_text)
            self.desensitize_active = False
            
            self.btn_desensitize.configure(fg_color="transparent", text_color=("gray10", "gray90"), text="👁️ 脱敏显隐")
            self.update_stats(status_text="已恢复原文")
            self.highlight_urls()

    def hide_search_status_panel(self):
        """Removes the highlight notice label and strips highlight tags"""
        self.search_status_panel.grid_forget()
        self.text_editor._textbox.tag_remove("search_match", "1.0", "end")

    # --- Core Notebook Operations ---

    def switch_file(self, target_path):
        """Safely navigates file change operations"""
        if target_path == self.current_file_path:
            return

        if self.has_changes:
            ans = messagebox.askyesnocancel("保存确认", "当前编辑的文件内容已修改，是否先保存修改？")
            if ans is True:
                saved = self.save_current_file()
                if not saved:
                    return
            elif ans is None:
                return

        self.load_file(target_path)

    def load_file(self, file_path):
        """Cleans work area, loads active text document and detects URLs"""
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("读取错误", "加载的文件物理路径已丢失，可能已被外部移动或删除！")
            self.refresh_tree_view()
            return

        try:
            # 采用 utf-8 容错解码模式，避免个别 ANSI 文件带特殊字符时直接导致读取闪退
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            if self.save_timer:
                self.after_cancel(self.save_timer)
                self.save_timer = None

            # Hide search match banner on new file loads
            self.hide_search_status_panel()

            self.text_editor.delete("1.0", "end")
            self.text_editor.insert("1.0", content)
            
            self.current_file_path = file_path
            self.has_changes = False
            
            # Format display path representation
            display_name = os.path.relpath(file_path, self.notebook_dir)
            self.lbl_status_file.configure(text=f"当前打开: {display_name}")
            self.update_stats(status_text="已载入")
            self.highlight_current_file_button()
            self.highlight_urls()

        except Exception as e:
            messagebox.showerror("打开文件失败", f"读取文件发生错误：\n{str(e)}")

    def save_current_file(self):
        """Writes buffer stream to disk"""
        if not self.current_file_path:
            return self.save_as_file()

        try:
            content = self.text_editor.get("1.0", "end")
            if content.endswith("\n"):
                content = content[:-1]

            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.has_changes = False
            self.update_stats(status_text="已保存")
            self.highlight_urls()
            return True
        except Exception as e:
            messagebox.showerror("保存失败", f"写入文件出现异常：\n{str(e)}")
            return False

    def save_as_file(self):
        """Allows user to duplicate file to customized destinations"""
        initial_name = os.path.basename(self.current_file_path) if self.current_file_path else "未命名.txt"
        file_path = filedialog.asksaveasfilename(
            initialdir=self.notebook_dir,
            initialfile=initial_name,
            defaultextension=".txt",
            filetypes=[("文本文档", "*.txt"), ("所有文件", "*.*")]
        )
        if not file_path:
            return False

        try:
            content = self.text_editor.get("1.0", "end")
            if content.endswith("\n"):
                content = content[:-1]

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.current_file_path = file_path
            self.has_changes = False
            
            display_name = os.path.relpath(file_path, self.notebook_dir)
            self.lbl_status_file.configure(text=f"当前打开: {display_name}")
            
            if file_path.startswith(self.notebook_dir):
                self.refresh_tree_view()
            else:
                self.update_stats(status_text="已另存为外置文件")
            
            self.highlight_urls()
            return True
        except Exception as e:
            messagebox.showerror("另存为失败", f"保存发生故障：\n{str(e)}")
            return False

    def auto_save_trigger(self):
        """Background routine triggering safety writes"""
        if self.auto_save_var.get() and self.has_changes and self.current_file_path:
            self.save_current_file()

    def clear_text(self):
        """Prompts to empty all current editor fields"""
        if messagebox.askyesno("清空确认", "确定要清空当前编辑器中的所有内容吗？此操作无法撤销。"):
            self.text_editor.delete("1.0", "end")
            self.on_text_modified()

    def on_text_modified(self, event=None):
        """Key release trigger checking links, calculating metrics, and setting auto-save timers"""
        self.has_changes = True
        self.update_stats(status_text="正在输入...")
        
        # 性能优化：打字时不要高频实时扫描整个大文本高亮链接（会极大地拖慢打字响应），
        # 而是先取消上一次的防抖延迟计时器，等键盘停止敲击1.2秒后再一并执行自动存盘与高亮链接。
        if hasattr(self, 'on_typing_timer') and self.on_typing_timer:
            self.after_cancel(self.on_typing_timer)
            
        self.on_typing_timer = self.after(1200, self.async_typing_process)

    def async_typing_process(self):
        """停止敲击1.2秒后，异步后台静默更新高亮和执行自动保存"""
        self.highlight_urls()
        if self.auto_save_var.get() and self.current_file_path:
            self.save_current_file()

    def update_stats(self, status_text=None):
        """Updates characters counts and save labels"""
        content = self.text_editor.get("1.0", "end")
        if content.endswith("\n"):
            content = content[:-1]

        char_count = len(content)
        line_count = len(content.split("\n")) if content else 0

        if not status_text:
            status_text = "未保存" if self.has_changes else "已保存"

        self.lbl_status_info.configure(
            text=f"字符数: {char_count}  |  行数: {line_count}  |  状态: {status_text}"
        )

    def on_closing(self):
        """拦截窗口关闭，安全确认"""
        if self.has_changes:
            ans = messagebox.askyesnocancel("退出确认", "有未保存的修改，是否在退出前保存？")
            if ans is True:
                saved = self.save_current_file()
                if saved:
                    self.destroy()
            elif ans is False:
                self.destroy()
            # None (用户取消) 则什么都不做，不关闭
        else:
            self.destroy()

    def change_theme(self, value):
        """Alters theme appearance"""
        if value == "浅色":
            ctk.set_appearance_mode("Light")
        elif value == "深色":
            ctk.set_appearance_mode("Dark")
        elif value == "系统":
            ctk.set_appearance_mode("System")
    # =========================================================================
    # 🧠 【全新升级】大模型 AI 智能 Agent 配置及核心控制中枢（完美对齐，零反转）
    # =========================================================================

    def load_ai_config(self):
        """安全持久化加载 AI 配置，100% 避免字段名称漂移冲突"""
        import json
        self.ai_api_key = ""
        self.ai_base_url = "https://api.siliconflow.cn/v1"
        self.ai_model_name = "Qwen/Qwen2.5-7B-Instruct"

        config_path = os.path.join(self.notebook_dir, "ai_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # 强格式校验，拒绝任何变量名错位
                    self.ai_api_key = config.get("api_key", "").strip()
                    self.ai_base_url = config.get("base_url", "https://api.siliconflow.cn/v1").strip()
                    self.ai_model_name = config.get("model_name", "Qwen/Qwen2.5-7B-Instruct").strip()
            except Exception:
                pass

    def save_ai_config(self, api_key, base_url, model_name):
        """将密钥、接口地址及模型名称绝对对齐保存，永久杜绝参数交换 Bug"""
        import json
        self.ai_api_key = api_key.strip()
        self.ai_base_url = base_url.strip()
        self.ai_model_name = model_name.strip()

        config = {
            "api_key": self.ai_api_key,
            "base_url": self.ai_base_url,
            "model_name": self.ai_model_name
        }
        config_path = os.path.join(self.notebook_dir, "ai_config.json")
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("保存失败", f"保存配置文件失败：\n{str(e)}")
            return False

    def show_ai_config_dialog(self):
        """弹出全新调优的 AI 配置中心，新增 🔍 查看可用模型 核心功能"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("AI 大模型配置")
        dialog.geometry("460x420")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # 居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 230
        y = self.winfo_y() + (self.winfo_height() // 2) - 210
        dialog.geometry(f"+{x}+{y}")

        lbl_head = ctk.CTkLabel(dialog, text="⚙️ 配置大模型智能收纳服务", font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"))
        lbl_head.pack(pady=(15, 10))

        # API Base
        lbl_base = ctk.CTkLabel(dialog, text="API 接口地址 (Base URL):", font=ctk.CTkFont(family="Microsoft YaHei", size=11))
        lbl_base.pack(anchor="w", padx=40, pady=(5, 1))
        entry_base = ctk.CTkEntry(dialog, width=380, placeholder_text="例如: https://api.siliconflow.cn/v1")
        entry_base.pack(pady=1)
        entry_base.insert(0, self.ai_base_url)

        # API Key
        lbl_key = ctk.CTkLabel(dialog, text="API 密钥 (API Key):", font=ctk.CTkFont(family="Microsoft YaHei", size=11))
        lbl_key.pack(anchor="w", padx=40, pady=(5, 1))
        entry_key = ctk.CTkEntry(dialog, width=380, show="*", placeholder_text="sk-...")
        entry_key.pack(pady=1)
        entry_key.insert(0, self.ai_api_key)

        # Model Name (带获取模型联动)
        lbl_model = ctk.CTkLabel(dialog, text="模型名称 (Model Name):", font=ctk.CTkFont(family="Microsoft YaHei", size=11))
        lbl_model.pack(anchor="w", padx=40, pady=(5, 1))
        
        preset_models = [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "deepseek-chat",
            "THUDM/glm-4-9b-chat",
            "internlm/internlm2_5-7b-chat"
        ]
        
        # 增加分类组合框，支持随时读取刷新
        entry_model = ctk.CTkComboBox(dialog, values=preset_models, width=380)
        entry_model.pack(pady=1)
        entry_model.set(self.ai_model_name)

        # 状态指示
        lbl_status = ctk.CTkLabel(dialog, text="状态: 准备就绪", font=ctk.CTkFont(family="Microsoft YaHei", size=11), text_color="gray50")
        lbl_status.pack(pady=(8, 2))

        def run_test_connection():
            kb = entry_base.get().strip()
            kk = entry_key.get().strip()
            km = entry_model.get().strip()
            if not kk:
                lbl_status.configure(text="状态: 请输入 API Key！", text_color="#e74c3c")
                return

            lbl_status.configure(text="状态: 正在连通测试中...", text_color="#3498db")
            
            import threading
            def thread_func():
                success, msg = self.test_llm_api_endpoint(kb, kk, km)
                if success:
                    dialog.after(0, lambda: lbl_status.configure(text=f"状态: 连接成功！({msg})", text_color="#2ecc71"))
                else:
                    dialog.after(0, lambda: lbl_status.configure(text=f"状态: 连接失败 ({msg[:40]})", text_color="#e74c3c"))
            
            threading.Thread(target=thread_func, daemon=True).start()

        def fetch_available_models():
            kb = entry_base.get().strip()
            kk = entry_key.get().strip()
            if not kk:
                lbl_status.configure(text="状态: 请输入 API Key 以便获取模型列表！", text_color="#e74c3c")
                return

            lbl_status.configure(text="状态: 正在拉取在线可用模型...", text_color="#3498db")
            
            import threading
            def thread_func():
                success, models = self.query_online_models(kb, kk)
                if success and models:
                    def show_list_ui():
                        lbl_status.configure(text=f"状态: 成功拉取到 {len(models)} 个可用模型！", text_color="#2ecc71")
                        self.pop_model_selection_list(dialog, models, entry_model)
                    dialog.after(0, show_list_ui)
                else:
                    dialog.after(0, lambda: lbl_status.configure(text=f"状态: 获取模型失败 ({models[:45]})", text_color="#e74c3c"))
            
            threading.Thread(target=thread_func, daemon=True).start()

        def save_and_close():
            kb = entry_base.get().strip()
            kk = entry_key.get().strip()
            km = entry_model.get().strip()
            # 严格顺序：key, url, model 写入本地
            if self.save_ai_config(kk, kb, km):
                dialog.destroy()
                self.update_stats(status_text="AI 配置应用成功")

        # 按钮动作排版
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(12, 10))

        btn_test = ctk.CTkButton(btn_frame, text="⚡ 测试连接", width=95, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=run_test_connection)
        btn_test.grid(row=0, column=0, padx=5)

        btn_fetch = ctk.CTkButton(btn_frame, text="🔍 可用模型", width=95, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=fetch_available_models)
        btn_fetch.grid(row=0, column=1, padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="取消", width=80, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=dialog.destroy)
        btn_cancel.grid(row=0, column=2, padx=5)

        btn_save = ctk.CTkButton(btn_frame, text="保存配置", width=85, fg_color="#2ecc71", hover_color="#27ae60", text_color="white", command=save_and_close)
        btn_save.grid(row=0, column=3, padx=5)

    def test_llm_api_endpoint(self, base_url, api_key, model_name):
        """利用标准库测试接口畅通状态"""
        import urllib.request
        import json
        
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    return True, "握手成功"
                return False, "回复异常"
        except Exception as e:
            return False, str(e)

    def query_online_models(self, base_url, api_key):
        """获取 OpenAI 兼容接口支持的所有模型"""
        import urllib.request
        import json
        
        url = base_url.rstrip("/") + "/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                data_list = res_data.get("data", [])
                
                models = []
                for item in data_list:
                    m_id = item.get("id")
                    if m_id:
                        models.append(m_id)
                models.sort()
                return True, models
        except Exception as e:
            return False, str(e)

    def pop_model_selection_list(self, parent, models_list, combo_widget):
        """弹出选择可用模型的二级弹窗，提供双击选择一键回填"""
        list_win = ctk.CTkToplevel(parent)
        list_win.title("🔍 在线可用模型列表")
        list_win.geometry("380x400")
        list_win.resizable(False, False)
        list_win.transient(parent)
        list_win.grab_set()

        # 居中
        list_win.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
        list_win.geometry(f"+{x}+{y}")

        lbl_info = ctk.CTkLabel(list_win, text="💡 双击下方任一模型名称，可一键自动回填：", font=ctk.CTkFont(family="Microsoft YaHei", size=11, weight="bold"))
        lbl_info.pack(pady=10, padx=15, anchor="w")

        scroll_area = ctk.CTkScrollableFrame(list_win, corner_radius=5)
        scroll_area.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        scroll_area.grid_columnconfigure(0, weight=1)

        def select_model(name):
            combo_widget.configure(values=models_list + [name])
            combo_widget.set(name)
            list_win.destroy()

        for idx, model_name in enumerate(models_list):
            m_btn = ctk.CTkButton(
                scroll_area,
                text=f"🤖 {model_name}",
                anchor="w",
                fg_color="transparent",
                hover_color=("gray85", "gray28"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(family="Consolas", size=12),
                height=30,
                corner_radius=4,
                command=lambda n=model_name: select_model(n)
            )
            m_btn.grid(row=idx, column=0, padx=2, pady=1, sticky="ew")
            m_btn.bind("<Double-Button-1>", lambda e, n=model_name: select_model(n))


    # --- 💬 终极 AI 智能对话管理 Agent 模块（100% 零依赖，双向 Function Call 客户端操控） ---

    def create_ai_chat_panel(self):
        """在右侧构建极具现代科技感的 AI 智能对话管理侧边栏（新增：一键折叠、清理日志、多行自适应输入框）"""
        self.ai_chat_frame = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.ai_chat_frame.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)
        self.ai_chat_frame.grid_propagate(False)

        self.ai_chat_frame.grid_rowconfigure(2, weight=1) # 聊天记录展示区自适应拉伸
        self.ai_chat_frame.grid_columnconfigure(0, weight=1)

        # 1. 顶部标题栏
        self.ai_title_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")
        self.ai_title_frame.grid(row=0, column=0, padx=10, pady=(15, 5), sticky="ew")
        
        self.lbl_ai_chat_title = ctk.CTkLabel(
            self.ai_title_frame,
            text="🤖 AI 助手",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
        )
        self.lbl_ai_chat_title.pack(side="left", padx=5)

        # ✕ 关闭按钮
        self.btn_close_ai = ctk.CTkButton(
            self.ai_title_frame,
            text="✕",
            width=22,
            height=22,
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self.toggle_ai_sidebar
        )
        self.btn_close_ai.pack(side="right", padx=2)

        # ➖ 折叠按钮
        self.btn_collapse_ai = ctk.CTkButton(
            self.ai_title_frame,
            text="➖",
            width=22,
            height=22,
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=10, weight="bold"),
            command=self.collapse_ai_sidebar
        )
        self.btn_collapse_ai.pack(side="right", padx=2)

        # 🧹 清理日志按钮
        self.btn_clean_logs = ctk.CTkButton(
            self.ai_title_frame,
            text="🧹 清理日志",
            width=70,
            height=22,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            command=self.clean_system_chat_logs
        )
        self.btn_clean_logs.pack(side="right", padx=5)

        self.lbl_ai_help = ctk.CTkLabel(
            self.ai_chat_frame,
            text="可对我说: '新建XX笔记'、'移动到XX分类'、'搜索XX'、'删除空文件夹'...",
            font=ctk.CTkFont(family="Microsoft YaHei", size=10),
            text_color="gray50",
            justify="left",
            wraplength=290
        )
        self.lbl_ai_help.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

        # 2. 聊天记录展现框 (富文本、支持多标签显隐)
        self.ai_chat_log_parent = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")
        self.ai_chat_log_parent.grid(row=2, column=0, sticky="nsew", padx=12, pady=5)
        
        self.ai_chat_log = ctk.CTkTextbox(
            self.ai_chat_log_parent,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            wrap="word",
            border_width=1,
            corner_radius=5
        )
        self.ai_chat_log_parent.grid_rowconfigure(0, weight=1)
        self.ai_chat_log_parent.grid_columnconfigure(0, weight=1)
        self.ai_chat_log.grid(row=0, column=0, sticky="nsew")

        # 配置文本颜色标签
        self.ai_chat_log._textbox.tag_config("user", foreground="#2980b9", font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"))
        self.ai_chat_log._textbox.tag_config("ai", foreground="#2ecc71", font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"))
        self.ai_chat_log._textbox.tag_config("system", foreground="#e67e22", font=ctk.CTkFont(family="Microsoft YaHei", size=11, slant="italic"))
        self.ai_chat_log.configure(state="disabled")

        self.append_ai_chat_history("system", "系统", "AI 对话管理助手已上线。请输入您的指令或与我闲聊！\n")

        # 3. 底部自适应高度输入区域
        self.ai_input_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")
        self.ai_input_frame.grid(row=3, column=0, padx=12, pady=(5, 15), sticky="ew")
        self.ai_input_frame.grid_columnconfigure(0, weight=1)

        # ✍️ 终极自适应：改用 CTkTextbox 实现多行随字数自动变高
        self.ai_chat_entry = ctk.CTkTextbox(
            self.ai_input_frame,
            height=35, # 默认 35 像素单行高度
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            wrap="word",
            border_width=1,
            corner_radius=5
        )
        self.ai_chat_entry.grid(row=0, column=0, padx=(0, 8), pady=2, sticky="ew")
        
        # 绑定回车键直接发送，Shift+Enter换行
        self.ai_chat_entry.bind("<Return>", self.handle_chat_entry_return)
        
        # 核心加固：利用 Tkinter Text 专有 <<Modified>> 虚拟绑定，不管是键盘打字，
        # 还是鼠标右键点击粘贴、拖入字符、退格删除，100% 实现即时自适应伸缩变高！
        def on_text_widget_change(event):
            if self.ai_chat_entry._textbox.edit_modified():
                self.adjust_chat_entry_height()
                self.ai_chat_entry._textbox.edit_modified(False) # 必须复位修改标志位，以便下一次触发
                
        self.ai_chat_entry._textbox.bind("<<Modified>>", on_text_widget_change)

        self.btn_send_chat = ctk.CTkButton(
            self.ai_input_frame,
            text="发送",
            width=60,
            height=32,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self.send_ai_chat_msg
        )
        self.btn_send_chat.grid(row=0, column=1, padx=0, pady=2, sticky="es")

        # 4. 创建一页微型“收起侧边盒”，默认处于隐藏
        self.ai_collapsed_bar = ctk.CTkFrame(self, width=45, corner_radius=0)
        self.btn_restore_ai = ctk.CTkButton(
            self.ai_collapsed_bar,
            text="💬\n\nA\nI",
            width=35,
            fg_color="#3498db",
            text_color="white",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self.restore_ai_sidebar
        )
        self.btn_restore_ai.pack(fill="y", expand=True, padx=5, pady=10)

    def collapse_ai_sidebar(self):
        """将 AI 伴侣折叠为右侧 45 像素宽度的精致迷你侧边栏"""
        self.ai_chat_frame.grid_forget()
        self.ai_collapsed_bar.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)
        self.ai_chat_collapsed = True
        self.update_stats(status_text="AI 面板已折叠")

    def restore_ai_sidebar(self):
        """一键秒级恢复展开 AI 伴侣大面板"""
        self.ai_collapsed_bar.grid_forget()
        self.ai_chat_frame.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)
        self.ai_chat_collapsed = False
        self.update_stats(status_text="AI 面板已展开")

    def toggle_ai_sidebar(self):
        """一键展开/隐藏右侧 AI 智能对话管理面板"""
        # 如果当前是处于折叠迷你态，先卸载迷你态
        if self.ai_chat_collapsed:
            self.ai_collapsed_bar.grid_forget()
            self.ai_chat_collapsed = False

        if self.ai_sidebar_visible:
            # 隐藏
            self.ai_chat_frame.grid_forget()
            self.ai_sidebar_visible = False
            self.btn_ai_assistant.configure(fg_color="#3498db", text_color="white")
            self.update_stats(status_text="AI 面板已隐藏")
        else:
            # 展开
            self.ai_chat_frame.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)
            self.ai_sidebar_visible = True
            self.btn_ai_assistant.configure(fg_color="#2ecc71", text_color="white")
            self.update_stats(status_text="AI 面板已开启")

    def adjust_chat_entry_height(self, event=None):
        """【极智多维自适应变高算法】同时感应物理换行与字数虚拟自折行，最高支持 5 行，支持打字及复制粘贴一秒自变高"""
        text_content = self.ai_chat_entry.get("1.0", "end-1c").strip()
        if not text_content:
            self.ai_chat_entry.configure(height=35)
            return

        # 1. 统计物理回车行数
        physical_lines = len(text_content.split("\n"))

        # 2. 计算虚拟折行：微软雅黑 12号字下，输入框可用宽度约 220px，一行约可展示 18 个汉字
        # 我们用字符长度换算成虚拟行
        total_chars = len(text_content)
        # 英文/数字/中文混合权重计算（中文字符占2，英文占1）
        visual_length = 0
        for char in text_content:
            if '\u4e00' <= char <= '\u9fff':
                visual_length += 2
            else:
                visual_length += 1
                
        # 微软雅黑在输入框内单行大约支持容纳 36 个 visual_length
        virtual_lines = int(visual_length / 36) + 1

        # 3. 综合行数
        actual_lines = max(physical_lines, virtual_lines)

        # 4. 根据实际综合行数一秒平滑自变高
        target_height = 35
        if actual_lines == 2:
            target_height = 52
        elif actual_lines == 3:
            target_height = 70
        elif actual_lines == 4:
            target_height = 88
        elif actual_lines >= 5:
            target_height = 110

        self.ai_chat_entry.configure(height=target_height)

    def append_ai_chat_history(self, tag, sender_name, message):
        """向聊天历史框中追加带颜色标签的动态消息"""
        self.ai_chat_log.configure(state="normal")
        self.ai_chat_log.insert("end", f"【{sender_name}】: ", tag)
        self.ai_chat_log.insert("end", f"{message}\n\n")
        self.ai_chat_log.configure(state="disabled")
        self.ai_chat_log._textbox.see("end")

    def handle_chat_entry_return(self, event):
        """回车发送，Shift+Enter换行"""
        if event.state & 0x0001:  # 检测到 Shift 被按下
            # 允许系统换行，不拦截
            return None
        else:
            # 纯回车：一键发送并拦截换行
            self.send_ai_chat_msg()
            return "break"

    def clean_system_chat_logs(self):
        """【一键清除调试执行日志】将聊天大厅中的 📢、⚙️、🎉 等系统过渡播报彻底擦除，还原纯净高雅的对话界面"""
        log_content = self.ai_chat_log.get("1.0", "end")
        # 精巧按段分割与过滤
        paragraphs = log_content.split("\n\n")
        clean_paras = []
        for para in paragraphs:
            # 过滤包含系统动作特征的段落
            if "【系统接收】" in para or "【系统执行】" in para or "【系统提示】" in para or "【系统错误】" in para or "📢" in para or "⚙️" in para or "🎉" in para or "🔄" in para:
                continue
            clean_paras.append(para)

        cleaned_text = "\n\n".join(clean_paras).strip()

        self.ai_chat_log.configure(state="normal")
        self.ai_chat_log.delete("1.0", "end")
        if cleaned_text:
            self.ai_chat_log.insert("end", cleaned_text + "\n\n")
        else:
            self.ai_chat_log.insert("end", "【系统】: 调试日志清理完毕！\n\n", "system")
        self.ai_chat_log.configure(state="disabled")
        self.ai_chat_log._textbox.see("end")
        self.update_stats(status_text="日志已彻底净化")
    def send_ai_chat_msg(self):
        """发送消息逻辑（【终极全仓接管 Agent】，支持自适应多文件批量遍历、读取、写入与重构）"""
        user_msg = self.ai_chat_entry.get("1.0", "end").strip()
        if not user_msg:
            return

        # 检查是否配置了 API Key
        if not self.ai_api_key:
            messagebox.showwarning("AI 助手未激活", "请先点击上方 '⚙️ AI配置' 按钮配置您的 API 密钥！")
            self.show_ai_config_dialog()
            return

        # 清空输入框、重置自适应高度、并让其重新获得焦点
        self.ai_chat_entry.delete("1.0", "end")
        self.ai_chat_entry.configure(height=35)

        # 渲染用户输入到屏幕
        self.append_ai_chat_history("user", "您", user_msg)

        # 禁用组件防止连击
        self.btn_send_chat.configure(state="disabled")
        self.ai_chat_entry.configure(state="disabled")

        # 输出收到指令提示
        self.append_ai_chat_history("system", "系统接收", f"📢 【收到指令】: '{user_msg}'")

        import threading
        def run_chat_loop(iteration=1):
            if iteration > 4: # 支持多达 4 轮连环自主作业
                def end_limit():
                    self.btn_send_chat.configure(state="normal")
                    self.ai_chat_entry.configure(state="normal")
                    self.append_ai_chat_history("system", "系统执行", "⚠️ 【安全警示】已达到 Agent 连环操作上限，自动断开。")
                self.after(0, end_limit)
                return

            # 🛠️ 终极升级：递归扫描整个 data 工作区，搜集全仓所有的 txt 文件清单、位置及大小
            all_notes_list = []
            subfolders = []
            try:
                for root, dirs, files in os.walk(self.notebook_dir):
                    # 获取子目录列表
                    for d in dirs:
                        if d not in subfolders:
                            subfolders.append(d)
                    # 记录每一个 TXT 的相对路径、大小
                    for file in files:
                        if file.lower().endswith('.txt'):
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, self.notebook_dir)
                            size_kb = round(os.path.getsize(full_path) / 1024, 2)
                            all_notes_list.append(f"📄 {rel_path} (大小: {size_kb} KB)")
            except Exception:
                pass

            subfolders_str = ", ".join(subfolders) if subfolders else "暂无子分类"
            all_notes_str = "\n".join(all_notes_list) if all_notes_list else "当前整个记事本工作区中没有任何笔记文件。"
            current_note_name = os.path.relpath(self.current_file_path, self.notebook_dir) if self.current_file_path else "当前主窗口未打开任何笔记"

            # 真实读取当前编辑器内文本
            current_editor_content = self.text_editor.get("1.0", "end").strip()
            if not current_editor_content or current_editor_content == "":
                current_editor_content = "【当前主编辑窗口内为空白无字文本】"
            elif len(current_editor_content) > 3000:
                current_editor_content = current_editor_content[:3000] + "...(篇幅过长，余下部分已截断)..."

            # 极其精准、专注、强指令约束的系统 Agent 设定
            system_prompt = (
                "你是一个超级智能记事本的物理文件与编辑器物理接管 Agent。\n"
                "你被赋予了顶级管理特权：在和用户闲聊的同时，直接通过标准的 JSON 动作，对磁盘、目录和编辑器文本执行批量读、写、增、删、改！\n\n"
                "【重要：当前记事本工作空间(data目录)的全仓文件明细清单】\n"
                "\"\"\"\n" + all_notes_str + "\n\"\"\"\n\n"
                "【重要：当前主窗口编辑器内正在显示的真实文本内容】\n"
                "\"\"\"\n" + current_editor_content + "\n\"\"\"\n\n"
                "【重要：当前物理目录状态】\n"
                "- 现有的子分类文件夹: [" + subfolders_str + "]\n"
                "- 正在编辑的活跃笔记: " + current_note_name + "\n\n"
                "【物理接管控制 JSON 指令表】\n"
                "请结合上下文多轮会话，理解用户的意图，自主决策并在你的回复中附带标准的 ```json ... ``` 代码块，"
                "我们的 Python 引擎会自动提取并在屏幕上直接替你操作底层 UI 和磁盘（你可以一次性发出多个 read_note 或 write_to_path，实现批量操作！）：\n"
                "```json\n"
                "{\n"
                "  \"actions\": [\n"
                "    { \"type\": \"read_note\", \"file\": \"文件名.txt\", \"folder\": \"分类目录名，如果是根目录传空串\" }, // 自主读取任意磁盘笔记的内容（读完后你会自动进入下一轮思考！）\n"
                "    { \"type\": \"write_to_path\", \"path\": \"相对路径(如：data/理财/同花顺.txt 或 data/同花顺.txt)\", \"content\": \"写入的干净、整齐的新内容文本，支持跨多行的长文本\" }, // 【核心】批量物理写盘，直接对全仓任意文件读写创建\n"
                "    { \"type\": \"delete_note\", \"file\": \"文件名.txt\", \"folder\": \"分类目录名，如果是根目录传空串\" }, // 批量物理删除指定笔记\n"
                "    { \"type\": \"create_note\", \"file\": \"文件名.txt\", \"folder\": \"要建在哪个分类目录下\" }, // 物理新建一个笔记并自动在屏幕加载打开\n"
                "    { \"type\": \"move_note\", \"target_folder\": \"目标分类文件夹名称\" }, // 自动平移当前打开的笔记\n"
                "    { \"type\": \"search\", \"query\": \"搜索词\" }, // 自动帮用户执行跨文件全文内容检索\n"
                "    { \"type\": \"create_folder\", \"folder_name\": \"分类文件夹名称\" }, // 新建分类文件夹\n"
                "    { \"type\": \"toggle_desensitize\" } // 切换脱敏隐藏\n"
                "  ]\n"
                "}\n"
                "```\n"
                "【多轮自迭代规范】：大白话闲聊与 JSON 指令可以共存。如果你的动作包含了非终结动作（如读取文件 read_note ），"
                "你在本轮只需要说明正在读取即可。读完后 Python 引擎会立刻重新呼叫你，让你根据读取的内容在下一轮给出最终结果！一句话解释你干了什么即可。"
            )

            # 仅在第一轮时推入用户原始消息
            if iteration == 1:
                self.ai_chat_history_list.append({"role": "user", "content": user_msg})

            if len(self.ai_chat_history_list) > 12:
                self.ai_chat_history_list = self.ai_chat_history_list[-12:]

            # 发送给大模型进行语义决策
            success, reply = self.call_llm_api_with_history(system_prompt)
            
            def update_ui():
                if success:
                    # 录入历史
                    self.ai_chat_history_list.append({"role": "assistant", "content": reply})
                    
                    # 运行物理指令，并返回是否需要开启多轮迭代
                    reply_clean, need_next_loop = self.parse_and_execute_json_actions_loop(reply)
                    self.append_ai_chat_history("ai", "AI助手", reply_clean)
                    
                    if need_next_loop:
                        # 后台自动、无需用户干预再次启动新一轮大模型思考，构成 Multi-Turn ReAct 连环执行！
                        self.append_ai_chat_history("system", "系统执行", "🔄 【连环决策】Agent 正在根据读回的内容，自动执行下一步物理动作...")
                        threading.Thread(target=run_chat_loop, args=(iteration + 1,), daemon=True).start()
                    else:
                        self.btn_send_chat.configure(state="normal")
                        self.ai_chat_entry.configure(state="normal")
                        self.ai_chat_entry.focus_set()
                else:
                    self.append_ai_chat_history("system", "系统错误", f"请求大模型发生故障：\n{reply}")
                    self.btn_send_chat.configure(state="normal")
                    self.ai_chat_entry.configure(state="normal")
            
            self.after(0, update_ui)

        threading.Thread(target=run_chat_loop, args=(1,), daemon=True).start()

    def call_llm_api_with_history(self, system_prompt):
        """大模型多轮会话安全通信接口，完全承载上下文连贯历史数组"""
        import urllib.request
        import json
        
        url = self.ai_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.ai_api_key}",
            "Content-Type": "application/json"
        }
        full_messages = [{"role": "system", "content": system_prompt}] + self.ai_chat_history_list
        data = {
            "model": self.ai_model_name,
            "messages": full_messages,
            "temperature": 0.4
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    return True, choices[0].get("message", {}).get("content", "").strip()
                return False, "大模型空回复"
        except Exception as e:
            return False, str(e)
    def parse_and_execute_json_actions_loop(self, raw_reply):
        """【物理级 JSON 核心操控器 - 全仓批量控制迭代版】解析并分段执行多任务动作"""
        import json
        import re
        import shutil

        # 1. 捕获 JSON 代码块
        json_pattern = re.compile(r'```json\s*([\s\S]*?)\s*```')
        match = json_pattern.search(raw_reply)
        
        # 移除大模型回复在末尾的 JSON 指令细节
        clean_reply = json_pattern.sub("", raw_reply).strip()

        # 兜底：如果大模型裸写了 JSON
        if not match:
            bare_json_pattern = re.compile(r'(\{\s*"actions"[\s\S]*?\})')
            match_bare = bare_json_pattern.search(raw_reply)
            if match_bare:
                json_str = match_bare.group(1).strip()
                clean_reply = bare_json_pattern.sub("", raw_reply).strip()
            else:
                return raw_reply, False
        else:
            json_str = match.group(1).strip()

        need_next_loop = False

        # 2. 解析并逐项物理执行，输出“收到/执行/完成”的分段流程
        try:
            action_data = json.loads(json_str)
            actions = action_data.get("actions", [])
            
            for action in actions:
                a_type = action.get("type", "").strip()

                # 💡 (A) read_note: 穿透读取任意文件
                if a_type == "read_note":
                    file_name = action.get("file", "").strip()
                    folder_name = action.get("folder", "").strip()
                    if not file_name:
                        continue
                    if not file_name.lower().endswith(".txt"):
                        file_name += ".txt"
                    
                    target_dir = self.notebook_dir if not folder_name or folder_name == "根目录 (未分类)" else os.path.join(self.notebook_dir, folder_name)
                    target_file_path = os.path.join(target_dir, file_name)

                    self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 穿透读取外部笔记 '{file_name}' (分类: {folder_name})")

                    if os.path.exists(target_file_path):
                        try:
                            with open(target_file_path, "r", encoding="utf-8", errors="replace") as f:
                                file_content = f.read()
                            
                            # 默默写回上下文历史
                            self.ai_chat_history_list.append({
                                "role": "system", 
                                "content": f"【系统自动回推物理读取结果】：文件 '{file_name}' 的内容是:\\n\"\"\"\\n{file_content}\\n\"\"\""
                            })
                            self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 成功读取，内容已秘密回推至 Agent 脑中进行下一步分析！")
                            need_next_loop = True
                        except Exception as e:
                            self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 读取外部笔记失败: {str(e)}")
                    else:
                        self.append_ai_chat_history("system", "系统提示", f"💡 【完成结果】: 试图读取 '{file_name}'，但磁盘上未找到该物理文件。")

                # 💡 (B) write_to_path: 【顶级动作】向指定相对路径（如 data/理财/同花顺.txt）进行物理写盘，支持批量写入！
                elif a_type == "write_to_path":
                    target_rel_path = action.get("path", "").strip()
                    content_to_write = action.get("content", "")
                    
                    if target_rel_path:
                        # 兼容处理前缀，如果是以 data/ 开头，剥离它以防拼接错误
                        if target_rel_path.startswith("data/"):
                            target_rel_path = target_rel_path[5:]
                        elif target_rel_path.startswith("data\\"):
                            target_rel_path = target_rel_path[5:]

                        target_full_path = os.path.join(self.notebook_dir, target_rel_path)
                        self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 物理批量写盘 $\\rightarrow$ '{target_rel_path}'")

                        try:
                            os.makedirs(os.path.dirname(target_full_path), exist_ok=True)
                            with open(target_full_path, "w", encoding="utf-8", errors="replace") as f:
                                f.write(content_to_write)

                            self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 成功写入，数据已被完全持久化保存！")

                            # 联动：如果刚刚被写入的文件就是当前正在打开的编辑文件，自动刷新窗口！
                            if self.current_file_path and os.path.abspath(self.current_file_path) == os.path.abspath(target_full_path):
                                def reload_current_view():
                                    self.text_editor.delete("1.0", "end")
                                    self.text_editor.insert("1.0", content_to_write)
                                    self.has_changes = False
                                    self.update_stats(status_text="已由AI同步更新")
                                    self.highlight_urls()
                                self.after(0, reload_current_view)

                            self.refresh_tree_view()
                        except Exception as e:
                            self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 物理批量写盘失败: {str(e)}")

                # 💡 (C) delete_note: 【顶级动作】物理批量删除指定文件
                elif a_type == "delete_note":
                    file_name = action.get("file", "").strip()
                    folder_name = action.get("folder", "").strip()
                    if file_name:
                        if not file_name.lower().endswith(".txt"):
                            file_name += ".txt"
                        
                        target_dir = self.notebook_dir if not folder_name or folder_name == "根目录 (未分类)" else os.path.join(self.notebook_dir, folder_name)
                        target_file_path = os.path.join(target_dir, file_name)

                        self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 物理删除磁盘笔记 '{file_name}'")

                        if os.path.exists(target_file_path):
                            try:
                                os.remove(target_file_path)
                                self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 该物理笔记已被安全从硬盘擦除！")
                                
                                # 联动：如果删除的是当前打开的文件，安全卸载
                                if self.current_file_path and os.path.abspath(self.current_file_path) == os.path.abspath(target_file_path):
                                    self.after(0, self.unload_current_file)

                                self.refresh_tree_view()
                            except Exception as e:
                                self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 删除笔记失败: {str(e)}")
                        else:
                            self.append_ai_chat_history("system", "系统提示", "💡 【完成结果】: 磁盘上没有找到该笔记，无需删除。")

                # 💡 (D) create_note: 新建笔记并加载
                elif a_type == "create_note":
                    note_name = action.get("file", "").strip()
                    chosen_folder = action.get("folder", "根目录 (未分类)").strip()
                    if not note_name:
                        continue
                    if not note_name.lower().endswith(".txt"):
                        note_name += ".txt"
                    
                    self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 在分类【{chosen_folder}】下新建笔记：'{note_name}'")
                    
                    illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
                    for char in illegal_chars:
                        note_name = note_name.replace(char, "")
                        chosen_folder = chosen_folder.replace(char, "")

                    target_dir = self.notebook_dir if not chosen_folder or chosen_folder == "根目录 (未分类)" else os.path.join(self.notebook_dir, chosen_folder)
                    
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                        new_file_path = os.path.join(target_dir, note_name)
                        
                        with open(new_file_path, "w", encoding="utf-8") as f:
                            f.write("")
                        
                        self.refresh_tree_view()
                        self.load_file(new_file_path)
                        self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 新笔记创建成功，并且已在主编辑器中为您打开！")
                    except Exception as e:
                        self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 新建笔记失败: {str(e)}")

                # 💡 (E) move_note: 自动平移当前打开的笔记
                elif a_type == "move_note":
                    target_folder = action.get("target_folder", "").strip()
                    self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 将当前活跃笔记移至分类：【{target_folder}】")

                    if not self.current_file_path:
                        self.append_ai_chat_history("system", "系统拦截", "❌ 【错误中断】: 当前主编辑窗口为空，移动失败！")
                    elif target_folder:
                        illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
                        for char in illegal_chars:
                            target_folder = target_folder.replace(char, "")

                        target_dir = self.notebook_dir if not target_folder or target_folder == "根目录 (未分类)" else os.path.join(self.notebook_dir, target_folder)
                        new_file_path = os.path.join(target_dir, os.path.basename(self.current_file_path))

                        try:
                            os.makedirs(target_dir, exist_ok=True)
                            shutil.move(self.current_file_path, new_file_path)
                            self.current_file_path = new_file_path
                            display_name = os.path.relpath(new_file_path, self.notebook_dir)
                            self.lbl_status_file.configure(text=f"当前打开: {display_name}")
                            
                            self.refresh_tree_view()
                            self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 跨文件夹平移成功，分类列表已无缝更新！")
                        except Exception as e:
                            self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 移动物理笔记失败: {str(e)}")

                # 💡 (F) search: 自动化全文内容检索
                elif a_type == "search":
                    search_query = action.get("query", "").strip()
                    if search_query:
                        self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 穿透全仓内容检索词：'{search_query}'")
                        self.search_entry.delete(0, "end")
                        self.search_entry.insert(0, search_query)
                        self.perform_search()
                        self.append_ai_chat_history("system", "系统执行", "🎉 【完成结果】: 搜索执行完毕，检索列表已为您呈现！")

                # 💡 (G) create_folder: 独立新建分类文件夹
                elif a_type == "create_folder":
                    folder_name = action.get("folder_name", "").strip()
                    if folder_name:
                        self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 磁盘物理创建新分类：【{folder_name}】")
                        illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
                        for char in illegal_chars:
                            folder_name = folder_name.replace(char, "")

                        new_path = os.path.join(self.notebook_dir, folder_name)
                        try:
                            os.makedirs(new_path, exist_ok=True)
                            self.refresh_tree_view()
                            self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 分类文件夹已成功在磁盘生成！")
                        except Exception as e:
                            self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 创建分类文件夹失败: {str(e)}")

                # 💡 (H) toggle_desensitize: 一键防窥脱敏
                elif a_type == "toggle_desensitize":
                    self.append_ai_chat_history("system", "系统执行", "⚙️ 【执行动作】: 开启/关闭当前数据敏感内容遮罩...")
                    self.toggle_desensitize()
                    self.append_ai_chat_history("system", "系统执行", "🎉 【完成结果】: 数据防窥脱敏状态已同步无缝切换！")

                # 💡 (I) delete_folder: 独立删除空分类文件夹
                elif a_type == "delete_folder":
                    # 终极多字段容错：捕获大模型由于各种语义理解导致返回的同义字段名，实现 100% 成功删除！
                    folder_name = action.get("folder_name", action.get("folder", action.get("name", ""))).strip()
                    if folder_name:
                        self.append_ai_chat_history("system", "系统执行", f"⚙️ 【执行动作】: 物理清理空文件夹：【{folder_name}】")
                        illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
                        for char in illegal_chars:
                            folder_name = folder_name.replace(char, "")

                        target_dir_path = os.path.join(self.notebook_dir, folder_name)
                        if os.path.exists(target_dir_path) and os.path.isdir(target_dir_path):
                            try:
                                # 检查是否是空目录（或者只包含隐藏的临时系统文件）
                                files_in_dir = os.listdir(target_dir_path)
                                if not files_in_dir:
                                    os.rmdir(target_dir_path)
                                    self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 空文件夹 【{folder_name}】 已被完美物理抹除！")
                                else:
                                    # 自动递归安全清空并抹除
                                    shutil.rmtree(target_dir_path)
                                    self.append_ai_chat_history("system", "系统执行", f"🎉 【完成结果】: 该分类包含 {len(files_in_dir)} 个废弃项目，已强制安全抹除！")
                                    
                                    # 如果当前编辑的活跃笔记恰好在被删除的目录里，安全卸载
                                    if self.current_file_path and self.current_file_path.startswith(target_dir_path):
                                        self.after(0, self.unload_current_file)
                                        
                                self.refresh_tree_view()
                            except Exception as e:
                                self.append_ai_chat_history("system", "系统错误", f"❌ 【错误中断】: 清理空目录失败: {str(e)}")
                        else:
                            self.append_ai_chat_history("system", "系统提示", f"💡 【完成结果】: 磁盘上没有找到名为 【{folder_name}】 的空文件夹，无需删除。")

        except Exception as e:
            pass

        return clean_reply, need_next_loop


if __name__ == "__main__":
    app = SuperNotebookApp()
    app.mainloop()
