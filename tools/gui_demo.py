import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog

class PluginLoader:
    def __init__(self):
        self.root = ttk.Window(themename="darkly")
        self.root.title("Elusha Plugin Loader")
        self.root.geometry("500x480")
        self._build()

    def _build(self):
        # 标题
        ttk.Label(self.root, text="世間知らずの猫エルーシャ",
                  font=("", 16, "bold")).pack(pady=(20, 0))
        ttk.Label(self.root, text="Plugin Loader v0.1",
                  font=("", 9), bootstyle=SECONDARY).pack(pady=(0, 20))

        ttk.Separator(self.root).pack(fill=X, padx=20)

        # 游戏路径
        path_frame = ttk.Frame(self.root)
        path_frame.pack(fill=X, padx=20, pady=(20, 10))
        ttk.Label(path_frame, text="游戏路径", font=("", 10, "bold")).pack(anchor=W)
        self.path_var = ttk.StringVar(value="D:\\...\\Game.exe")
        ttk.Entry(path_frame, textvariable=self.path_var).pack(side=LEFT, fill=X, expand=True, pady=(5, 0))
        ttk.Button(path_frame, text="...", width=3).pack(side=RIGHT, padx=(5, 0), pady=(5, 0))

        # 插件列表
        ttk.Label(self.root, text="插件列表", font=("", 10, "bold")).pack(anchor=W, padx=20, pady=(20, 5))

        list_frame = ttk.Frame(self.root)
        list_frame.pack(fill=BOTH, expand=True, padx=20)

        self.plugin_tree = ttk.Treeview(list_frame, columns=("name", "ver", "status"),
                                        show="headings", height=8)
        self.plugin_tree.heading("name", text="插件名")
        self.plugin_tree.heading("ver", text="版本")
        self.plugin_tree.heading("status", text="状态")
        self.plugin_tree.column("name", width=240)
        self.plugin_tree.column("ver", width=80)
        self.plugin_tree.column("status", width=80)
        self.plugin_tree.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.plugin_tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.plugin_tree.configure(yscrollcommand=scrollbar.set)

        # 模拟插件数据
        for data in [
            ("MOD-03-RuntimeMap ミニマップ", "0.6.2", "启用"),
            ("MOD-02-QuestLog 任务引导", "2.0.0", "启用"),
            ("MOD-01-Translate 翻译", "1.0.0", "禁用"),
            ("MOD-04-SkipIntro 跳过片头", "0.1.0", "启用"),
        ]:
            self.plugin_tree.insert("", END, values=data)

        # 按钮
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=X, padx=20, pady=20)
        ttk.Button(btn_frame, text="刷新列表", bootstyle=SECONDARY).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="启用 / 禁用", bootstyle=WARNING).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="▶ 启动游戏", bootstyle=SUCCESS).pack(side=RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="保存配置", bootstyle=INFO).pack(side=RIGHT, padx=5)

        # 状态栏
        self.status = ttk.Label(self.root, text="就绪", relief=SUNKEN, anchor=W, padding=(10, 2))
        self.status.pack(fill=X, side=BOTTOM)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    PluginLoader().run()
