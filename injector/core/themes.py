"""19 themes — 10 dark + 9 light, each with unique palette & atmosphere"""
THEMES = {}

# ==================== DEFAULT ====================

THEMES["slate_gray"] = {
    "name": "Slate Gray",
    "qss": """
        QMainWindow,QDialog,QWidget{background-color:#2b2b2b;color:#cccccc;font-size:13px;}
        QLabel{color:#cccccc;}
        QPushButton{background-color:#333333;color:#cccccc;border:1px solid #555555;border-radius:4px;padding:6px 16px;font-size:12px;}
        QPushButton:hover{background-color:#3d3d3d;border-color:#666666;}
        QPushButton:pressed{background-color:#4a4a4a;}
        QScrollArea{border:none;background-color:transparent;}
        QFrame#pluginCard{background-color:#333333;border:1px solid #444444;border-radius:6px;padding:8px;margin:4px 0px;}
        QFrame#pluginCard:hover{border-color:#777777;}
        QFrame#brokenCard{background-color:#3a2020;border-color:#cc5555;}
        QCheckBox{spacing:8px;}
        QCheckBox::indicator{width:40px;height:22px;border-radius:11px;border:2px solid #555555;background-color:#555555;}
        QCheckBox::indicator:checked{background-color:#4caf50;border-color:#4caf50;}
        QTextEdit{background-color:#1e1e1e;color:#d4d4d4;font-family:'Consolas','Courier New',monospace;font-size:11px;border:1px solid #444444;border-radius:4px;}
        QLineEdit{background-color:#333333;color:#cccccc;border:1px solid #555555;border-radius:4px;padding:4px 8px;}
        QTabWidget::pane{border:1px solid #444444;background-color:#2b2b2b;}
        QTabBar::tab{background-color:#333333;color:#999999;padding:8px 16px;border:1px solid #444444;border-bottom:none;border-top-left-radius:4px;border-top-right-radius:4px;}
        QTabBar::tab:selected{background-color:#2b2b2b;color:#cccccc;border-bottom:2px solid #4caf50;}
        QComboBox{background-color:#333333;color:#cccccc;border:1px solid #555555;border-radius:4px;padding:4px 8px;}
        QComboBox:hover{border-color:#666666;}
        QComboBox QAbstractItemView{background-color:#333333;color:#cccccc;border:1px solid #555555;selection-background-color:#4a4a4a;}
""",
}

# ==================== DARK (9) ====================

THEMES["catppuccin_mocha"] = {
    "name": "Catppuccin Mocha",
    "qss": """QMainWindow,QDialog,QWidget{background:#1e1e2e;color:#cdd6f4;font-size:13px;}QLabel{color:#cdd6f4;}QPushButton{background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:8px;padding:6px 16px;}QPushButton:hover{background:#45475a;}QFrame#pluginCard{background:#313244;border:1px solid #45475a;border-radius:10px;padding:8px;}QFrame#pluginCard:hover{border-color:#89b4fa;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:6px;padding:4px 8px;}QTextEdit{background:#11111b;color:#a6e3a1;font-family:Consolas;}QTabWidget::pane{border:1px solid #45475a;background:#1e1e2e;}QTabBar::tab{background:#313244;color:#cdd6f4;padding:8px 16px;border:1px solid #45475a;}QTabBar::tab:selected{background:#1e1e2e;border-bottom:2px solid #89b4fa;}""",
}

THEMES["tokyo_night"] = {
    "name": "Tokyo Night",
    "qss": """QMainWindow,QDialog,QWidget{background:#1a1b26;color:#c0caf5;font-size:13px;}QLabel{color:#c0caf5;}QPushButton{background:#24283b;color:#7aa2f7;border:1px solid #3b4261;border-radius:3px;padding:5px 14px;}QPushButton:hover{background:#364a82;color:#c0caf5;}QFrame#pluginCard{background:#24283b;border:1px solid #3b4261;border-radius:4px;padding:8px;}QFrame#pluginCard:hover{border-color:#7aa2f7;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#1f2335;color:#c0caf5;border:1px solid #3b4261;border-radius:3px;}QTextEdit{background:#1a1b26;color:#9ece6a;font-family:Consolas;}QTabWidget::pane{border:1px solid #3b4261;background:#1a1b26;}QTabBar::tab{background:#24283b;color:#565f89;padding:6px 14px;}QTabBar::tab:selected{color:#7aa2f7;background:#1a1b26;}""",
}

THEMES["dracula"] = {
    "name": "Dracula",
    "qss": """QMainWindow,QDialog,QWidget{background:#282a36;color:#f8f8f2;font-size:13px;}QLabel{color:#f8f8f2;}QPushButton{background:#44475a;color:#bd93f9;border:1px solid #6272a4;border-radius:6px;padding:6px 16px;}QPushButton:hover{background:#6272a4;color:#f8f8f2;}QFrame#pluginCard{background:#44475a;border:1px solid #6272a4;border-radius:8px;padding:8px;}QFrame#pluginCard:hover{border-color:#ff79c6;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#44475a;color:#f8f8f2;border:1px solid #6272a4;border-radius:6px;}QTextEdit{background:#282a36;color:#50fa7b;font-family:Consolas;}QTabWidget::pane{border:1px solid #6272a4;background:#282a36;}QTabBar::tab{background:#44475a;color:#bd93f9;padding:6px 14px;}QTabBar::tab:selected{color:#f8f8f2;background:#282a36;}""",
}

THEMES["gruvbox_dark"] = {
    "name": "Gruvbox Dark",
    "qss": """QMainWindow,QDialog,QWidget{background:#282828;color:#ebdbb2;font-size:13px;}QLabel{color:#ebdbb2;}QPushButton{background:#3c3836;color:#fabd2f;border:1px solid #504945;border-radius:3px;padding:5px 14px;}QPushButton:hover{background:#504945;color:#ebdbb2;}QFrame#pluginCard{background:#3c3836;border:1px solid #504945;border-radius:4px;padding:8px;}QFrame#pluginCard:hover{border-color:#b8bb26;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#3c3836;color:#ebdbb2;border:1px solid #504945;border-radius:3px;}QTextEdit{background:#1d2021;color:#b8bb26;font-family:Consolas;}QTabWidget::pane{border:1px solid #504945;background:#282828;}QTabBar::tab{background:#3c3836;color:#928374;padding:6px 14px;}QTabBar::tab:selected{color:#ebdbb2;background:#282828;}""",
}

THEMES["monokai"] = {
    "name": "Monokai",
    "qss": """QMainWindow,QDialog,QWidget{background:#272822;color:#f8f8f2;font-size:13px;}QLabel{color:#f8f8f2;}QPushButton{background:#3e3d32;color:#a6e22e;border:1px solid #75715e;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#49483e;color:#f8f8f2;}QFrame#pluginCard{background:#3e3d32;border:1px solid #75715e;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#f92672;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#3e3d32;color:#f8f8f2;border:1px solid #75715e;border-radius:4px;}QTextEdit{background:#272822;color:#a6e22e;font-family:Consolas;}QTabWidget::pane{border:1px solid #75715e;background:#272822;}QTabBar::tab{background:#3e3d32;color:#75715e;padding:6px 14px;}QTabBar::tab:selected{color:#f8f8f2;background:#272822;}""",
}

THEMES["nord"] = {
    "name": "Nord",
    "qss": """QMainWindow,QDialog,QWidget{background:#2e3440;color:#d8dee9;font-size:13px;}QLabel{color:#d8dee9;}QPushButton{background:#3b4252;color:#88c0d0;border:1px solid #4c566a;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#434c5e;color:#d8dee9;}QFrame#pluginCard{background:#3b4252;border:1px solid #4c566a;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#88c0d0;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#3b4252;color:#d8dee9;border:1px solid #4c566a;border-radius:4px;}QTextEdit{background:#2e3440;color:#a3be8c;font-family:Consolas;}QTabWidget::pane{border:1px solid #4c566a;background:#2e3440;}QTabBar::tab{background:#3b4252;color:#81a1c1;padding:6px 14px;}QTabBar::tab:selected{color:#d8dee9;background:#2e3440;}""",
}

THEMES["one_dark"] = {
    "name": "One Dark",
    "qss": """QMainWindow,QDialog,QWidget{background:#282c34;color:#abb2bf;font-size:13px;}QLabel{color:#abb2bf;}QPushButton{background:#3e4451;color:#61afef;border:1px solid #5c6370;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#4b5362;color:#abb2bf;}QFrame#pluginCard{background:#3e4451;border:1px solid #5c6370;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#e5c07b;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#3e4451;color:#abb2bf;border:1px solid #5c6370;border-radius:4px;}QTextEdit{background:#21252b;color:#98c379;font-family:Consolas;}QTabWidget::pane{border:1px solid #5c6370;background:#282c34;}QTabBar::tab{background:#3e4451;color:#5c6370;padding:6px 14px;}QTabBar::tab:selected{color:#abb2bf;background:#282c34;}""",
}

THEMES["oled_black"] = {
    "name": "OLED Black",
    "qss": """QMainWindow,QDialog,QWidget{background:#000000;color:#ffffff;font-size:13px;}QLabel{color:#ffffff;}QPushButton{background:#111111;color:#4da6ff;border:1px solid #333333;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#222222;color:#ffffff;}QFrame#pluginCard{background:#111111;border:1px solid #333333;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#4da6ff;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#111111;color:#ffffff;border:1px solid #333333;border-radius:4px;}QTextEdit{background:#000000;color:#33cc33;font-family:Consolas;}QTabWidget::pane{border:1px solid #333333;background:#000000;}QTabBar::tab{background:#111111;color:#666666;padding:6px 14px;}QTabBar::tab:selected{color:#ffffff;background:#000000;}""",
}

THEMES["cyberpunk"] = {
    "name": "Cyberpunk Neon",
    "qss": """QMainWindow,QDialog,QWidget{background:#000b1e;color:#00ffff;font-size:13px;}QLabel{color:#00ffff;}QPushButton{background:#0a1628;color:#ff00ff;border:1px solid #00ffff;border-radius:2px;padding:5px 14px;}QPushButton:hover{background:#1a2840;color:#00ffff;}QFrame#pluginCard{background:#0a1628;border:1px solid #00ffff;border-radius:3px;padding:8px;}QFrame#pluginCard:hover{border-color:#ff00ff;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#0a1628;color:#00ffff;border:1px solid #00ffff;border-radius:2px;}QTextEdit{background:#000b1e;color:#00ff00;font-family:Consolas;}QTabWidget::pane{border:1px solid #00ffff;background:#000b1e;}QTabBar::tab{background:#0a1628;color:#008888;padding:6px 14px;}QTabBar::tab:selected{color:#00ffff;background:#000b1e;}""",
}

# ==================== LIGHT (9) ====================

THEMES["catppuccin_latte"] = {
    "name": "Catppuccin Latte",
    "qss": """QMainWindow,QDialog,QWidget{background:#eff1f5;color:#4c4f69;font-size:13px;}QLabel{color:#4c4f69;}QPushButton{background:#ccd0da;color:#4c4f69;border:1px solid #bcc0cc;border-radius:8px;padding:6px 16px;}QPushButton:hover{background:#bcc0cc;}QFrame#pluginCard{background:#e6e9ef;border:1px solid #ccd0da;border-radius:10px;padding:8px;}QFrame#pluginCard:hover{border-color:#1e66f5;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#e6e9ef;color:#4c4f69;border:1px solid #ccd0da;border-radius:6px;padding:4px 8px;}QTextEdit{background:#eff1f5;color:#40a02b;font-family:Consolas;}QTabWidget::pane{border:1px solid #ccd0da;background:#eff1f5;}QTabBar::tab{background:#ccd0da;color:#5c5f77;padding:8px 16px;border:1px solid #ccd0da;}QTabBar::tab:selected{background:#eff1f5;color:#4c4f69;border-bottom:2px solid #1e66f5;}""",
}

THEMES["solarized_light"] = {
    "name": "Solarized Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#fdf6e3;color:#657b83;font-size:13px;}QLabel{color:#657b83;}QPushButton{background:#eee8d5;color:#2aa198;border:1px solid #d3cbb7;border-radius:3px;padding:5px 14px;}QPushButton:hover{background:#e6dfc5;color:#586e75;}QFrame#pluginCard{background:#eee8d5;border:1px solid #d3cbb7;border-radius:4px;padding:8px;}QFrame#pluginCard:hover{border-color:#2aa198;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#eee8d5;color:#657b83;border:1px solid #d3cbb7;border-radius:3px;}QTextEdit{background:#fdf6e3;color:#859900;font-family:Consolas;}QTabWidget::pane{border:1px solid #d3cbb7;background:#fdf6e3;}QTabBar::tab{background:#eee8d5;color:#93a1a1;padding:6px 14px;}QTabBar::tab:selected{color:#657b83;background:#fdf6e3;}""",
}

THEMES["gruvbox_light"] = {
    "name": "Gruvbox Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#fbf1c7;color:#3c3836;font-size:13px;}QLabel{color:#3c3836;}QPushButton{background:#ebdbb2;color:#b57614;border:1px solid #d5c4a1;border-radius:3px;padding:5px 14px;}QPushButton:hover{background:#d5c4a1;color:#3c3836;}QFrame#pluginCard{background:#ebdbb2;border:1px solid #d5c4a1;border-radius:4px;padding:8px;}QFrame#pluginCard:hover{border-color:#79740e;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#ebdbb2;color:#3c3836;border:1px solid #d5c4a1;border-radius:3px;}QTextEdit{background:#fbf1c7;color:#79740e;font-family:Consolas;}QTabWidget::pane{border:1px solid #d5c4a1;background:#fbf1c7;}QTabBar::tab{background:#ebdbb2;color:#a89984;padding:6px 14px;}QTabBar::tab:selected{color:#3c3836;background:#fbf1c7;}""",
}

THEMES["github_light"] = {
    "name": "GitHub Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#ffffff;color:#24292f;font-size:13px;}QLabel{color:#24292f;}QPushButton{background:#f6f8fa;color:#0969da;border:1px solid #d0d7de;border-radius:6px;padding:5px 16px;}QPushButton:hover{background:#eaeef2;color:#24292f;}QFrame#pluginCard{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#0969da;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#f6f8fa;color:#24292f;border:1px solid #d0d7de;border-radius:6px;}QTextEdit{background:#ffffff;color:#1a7f37;font-family:Consolas;}QTabWidget::pane{border:1px solid #d0d7de;background:#ffffff;}QTabBar::tab{background:#f6f8fa;color:#656d76;padding:6px 14px;}QTabBar::tab:selected{color:#24292f;background:#ffffff;}""",
}

THEMES["nord_light"] = {
    "name": "Nord Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#eceff4;color:#2e3440;font-size:13px;}QLabel{color:#2e3440;}QPushButton{background:#d8dee9;color:#5e81ac;border:1px solid #c8d0e0;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#c8d0e0;color:#2e3440;}QFrame#pluginCard{background:#d8dee9;border:1px solid #c8d0e0;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#5e81ac;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#d8dee9;color:#2e3440;border:1px solid #c8d0e0;border-radius:4px;}QTextEdit{background:#eceff4;color:#4c566a;font-family:Consolas;}QTabWidget::pane{border:1px solid #c8d0e0;background:#eceff4;}QTabBar::tab{background:#d8dee9;color:#81a1c1;padding:6px 14px;}QTabBar::tab:selected{color:#2e3440;background:#eceff4;}""",
}

THEMES["everforest_light"] = {
    "name": "Everforest Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#fdf6e3;color:#5c6a72;font-size:13px;}QLabel{color:#5c6a72;}QPushButton{background:#f3ead3;color:#8da101;border:1px solid #e0dcc7;border-radius:5px;padding:5px 14px;}QPushButton:hover{background:#e0dcc7;color:#5c6a72;}QFrame#pluginCard{background:#f3ead3;border:1px solid #e0dcc7;border-radius:7px;padding:8px;}QFrame#pluginCard:hover{border-color:#8da101;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#f3ead3;color:#5c6a72;border:1px solid #e0dcc7;border-radius:5px;}QTextEdit{background:#fdf6e3;color:#8da101;font-family:Consolas;}QTabWidget::pane{border:1px solid #e0dcc7;background:#fdf6e3;}QTabBar::tab{background:#f3ead3;color:#b3aa8e;padding:6px 14px;}QTabBar::tab:selected{color:#5c6a72;background:#fdf6e3;}""",
}

THEMES["rose_pine_dawn"] = {
    "name": "Rosé Pine Dawn",
    "qss": """QMainWindow,QDialog,QWidget{background:#faf4ed;color:#575279;font-size:13px;}QLabel{color:#575279;}QPushButton{background:#f2e9e1;color:#b4637a;border:1px solid #dfdad9;border-radius:8px;padding:6px 16px;}QPushButton:hover{background:#dfdad9;color:#575279;}QFrame#pluginCard{background:#f2e9e1;border:1px solid #dfdad9;border-radius:10px;padding:8px;}QFrame#pluginCard:hover{border-color:#907aa9;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#f2e9e1;color:#575279;border:1px solid #dfdad9;border-radius:8px;}QTextEdit{background:#faf4ed;color:#286983;font-family:Consolas;}QTabWidget::pane{border:1px solid #dfdad9;background:#faf4ed;}QTabBar::tab{background:#f2e9e1;color:#9893a5;padding:8px 16px;}QTabBar::tab:selected{color:#575279;background:#faf4ed;}""",
}

THEMES["ayu_light"] = {
    "name": "Ayu Light",
    "qss": """QMainWindow,QDialog,QWidget{background:#fafafa;color:#6c7680;font-size:13px;}QLabel{color:#6c7680;}QPushButton{background:#ffffff;color:#f29718;border:1px solid #d9d9d9;border-radius:4px;padding:5px 14px;}QPushButton:hover{background:#f0f0f0;color:#5c6166;}QFrame#pluginCard{background:#ffffff;border:1px solid #d9d9d9;border-radius:6px;padding:8px;}QFrame#pluginCard:hover{border-color:#f29718;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#ffffff;color:#6c7680;border:1px solid #d9d9d9;border-radius:4px;}QTextEdit{background:#fafafa;color:#86b300;font-family:Consolas;}QTabWidget::pane{border:1px solid #d9d9d9;background:#fafafa;}QTabBar::tab{background:#ffffff;color:#b3b3b3;padding:6px 14px;}QTabBar::tab:selected{color:#6c7680;background:#fafafa;}""",
}

THEMES["light_plus"] = {
    "name": "Light+ (VS Code)",
    "qss": """QMainWindow,QDialog,QWidget{background:#ffffff;color:#3b3b3b;font-size:13px;}QLabel{color:#3b3b3b;}QPushButton{background:#e8e8e8;color:#007acc;border:1px solid #d0d0d0;border-radius:3px;padding:5px 14px;}QPushButton:hover{background:#d0d0d0;color:#3b3b3b;}QFrame#pluginCard{background:#f3f3f3;border:1px solid #e0e0e0;border-radius:4px;padding:8px;}QFrame#pluginCard:hover{border-color:#007acc;}QLineEdit,QTextEdit,QComboBox,QSpinBox{background:#ffffff;color:#3b3b3b;border:1px solid #cecece;border-radius:3px;}QTextEdit{background:#fafafa;color:#098658;font-family:Consolas;}QTabWidget::pane{border:1px solid #d0d0d0;background:#ffffff;}QTabBar::tab{background:#ececec;color:#666;padding:6px 14px;}QTabBar::tab:selected{color:#3b3b3b;background:#ffffff;}""",
}
