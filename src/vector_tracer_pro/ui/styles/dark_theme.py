"""
vector_tracer_pro.ui.styles.dark_theme
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A premium dark theme QSS stylesheet for Vector Tracer Pro.
"""

DARK_THEME_STYLE = """
/* Global Styling */
QWidget {
    background-color: #18181b;
    color: #e4e4e7;
    font-family: "Segoe UI", "Segoe UI Semibold", Roboto, Helvetica, sans-serif;
    font-size: 13px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background-color: #18181b;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #3f3f46;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #52525b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background-color: #18181b;
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #3f3f46;
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #52525b;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Menubar */
QMenuBar {
    background-color: #18181b;
    border-bottom: 1px solid #27272a;
}
QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
}
QMenuBar::item:selected {
    background-color: #27272a;
    border-radius: 4px;
}
QMenu {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

/* Splitter */
QSplitter::handle {
    background-color: #27272a;
    width: 4px;
    height: 4px;
}
QSplitter::handle:hover {
    background-color: #6366f1;
}

/* Headers / Panel Containers */
QFrame#PanelFrame, QFrame#ContainerFrame {
    background-color: #202024;
    border: 1px solid #2f2f36;
    border-radius: 8px;
}

QLabel#PanelTitle {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
    padding-bottom: 4px;
    border-bottom: 2px solid #6366f1;
}

/* Lists and Tables */
QListWidget, QTableWidget {
    background-color: #202024;
    border: 1px solid #2f2f36;
    border-radius: 6px;
    gridline-color: #27272a;
    outline: 0;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 4px;
    margin-bottom: 2px;
}
QListWidget::item:hover {
    background-color: #2a2a32;
    color: #ffffff;
}
QListWidget::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #27272a;
    color: #a1a1aa;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #3f3f46;
    font-weight: bold;
}
QTableWidget::item {
    padding: 6px;
}

/* Buttons */
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 16px;
    color: #e4e4e7;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}
QPushButton:pressed {
    background-color: #18181b;
}
QPushButton:disabled {
    background-color: #18181b;
    color: #71717a;
    border-color: #27272a;
}

QPushButton#PrimaryButton {
    background-color: #6366f1;
    border: 1px solid #4f46e5;
    color: #ffffff;
}
QPushButton#PrimaryButton:hover {
    background-color: #4f46e5;
}
QPushButton#PrimaryButton:pressed {
    background-color: #3730a3;
}
QPushButton#PrimaryButton:disabled {
    background-color: #312e81;
    color: #93c5fd;
    border-color: #1e1b4b;
}

QPushButton#DangerButton {
    background-color: #ef4444;
    border: 1px solid #dc2626;
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
    padding: 4px 10px;
    border-radius: 4px;
}
QPushButton#DangerButton:hover {
    background-color: #dc2626;
}
QPushButton#DangerButton:pressed {
    background-color: #991b1b;
}

/* Inputs & ComboBox */
QComboBox, QLineEdit {
    background-color: #202024;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e4e4e7;
}
QComboBox:hover, QLineEdit:hover {
    border-color: #52525b;
}
QComboBox:focus, QLineEdit:focus {
    border-color: #6366f1;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-left-width: 0px;
}
QComboBox QAbstractItemView {
    background-color: #202024;
    border: 1px solid #3f3f46;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

/* Progress Bar */
QProgressBar {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    text-align: center;
    font-weight: bold;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 5px;
}

/* Status Bar */
QStatusBar {
    background-color: #18181b;
    border-top: 1px solid #27272a;
    color: #a1a1aa;
}
QStatusBar::item {
    border: none;
}
"""
