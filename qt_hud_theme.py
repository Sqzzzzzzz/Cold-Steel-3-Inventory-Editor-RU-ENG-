"""Single Cold Steel III-inspired glass HUD theme for the native Qt editor."""
from catalog_core import resource_path

HUD_STYLESHEET = r'''
QWidget {color:#EBF4FC;font-family:'Segoe UI','DejaVu Sans';font-size:14px;font-weight:400;}
QWidget#canvas,QFrame,QLabel,QWidget#detailInner,QWidget#toolsInner {background:transparent;border:0;}
QWidget#titleBar {background:transparent;border-bottom:1px solid rgba(149,216,236,155);}
QLabel[role="title"] {font-family:'Cambria','DejaVu Serif';font-size:38px;font-weight:400;color:#FAFAF8;}
QLabel[role="subtitle"] {font-family:'Cambria','DejaVu Serif';font-size:17px;color:#99CCDF;}
QLabel[role="section"] {font-size:16px;font-weight:500;color:#EDF6FC;}
QLabel[role="muted"] {color:#B9D1E1;}
QLabel[role="itemName"] {font-size:20px;font-weight:600;color:#F6FAFC;}
QLabel[role="descriptionTitle"] {font-size:17px;color:#E8F4FA;}
QLabel#fieldCaption {font-size:13px;}
QLabel#heroIcon {background:transparent;border:0;}
QFrame#hudSeparator {background:rgba(132,191,213,143);border:0;}
QPushButton {background:transparent;border:0;padding:0;font-weight:400;font-size:14px;}
QPushButton[role="filter"] {font-size:12px;}
QLineEdit,QSpinBox,QComboBox {
  background:rgba(2,25,42,192);border:1px solid #6598B1;border-radius:3px;
  color:#E5F4FD;selection-background-color:#078ABC;padding:4px 8px;
  font-weight:400;font-size:14px;
}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus {border:1px solid #A6EAF7;}
QLineEdit {selection-color:white;}
QLineEdit:read-only {background:rgba(5,33,50,160);color:#E5F1FB;}
QComboBox {padding-right:22px;}
QComboBox::drop-down {border:0;width:20px;}
QComboBox::down-arrow {image:url(@DOWN@);width:8px;height:5px;}
QComboBox#languageSwitch {font-size:12px;background:rgba(5,38,58,150);border-color:rgba(110,167,188,130);}
QComboBox QAbstractItemView {background:#0A314B;border:1px solid #6EB7D3;color:#E2F5FF;selection-background-color:#147CAA;}
QSpinBox {padding-right:20px;}
QSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:17px;border:1px solid #6C9EB8;background:#17435D;border-top-right-radius:2px;}
QSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:17px;border:1px solid #6C9EB8;background:#17435D;border-bottom-right-radius:2px;}
QSpinBox::up-arrow {image:url(@UP@);width:8px;height:5px;}
QSpinBox::down-arrow {image:url(@DOWN@);width:8px;height:5px;}
QCheckBox {spacing:9px;color:#DDEAF3;font-size:13px;background:transparent;}
QCheckBox::indicator {width:15px;height:15px;border:1px solid #80A5BC;border-radius:1px;background:#173E56;}
QCheckBox::indicator:checked {background:#BEDAE9;image:url(@CHECK@);}
QTreeWidget {background:transparent;border:0;border-right:1px solid rgba(93,170,200,130);color:#E6F0FA;outline:0;}
QTreeWidget::item {padding:3px 3px;min-height:24px;border:1px solid transparent;}
QTreeWidget::item:selected {
  background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #0DB7E4,stop:.4 #087EAF,stop:1 #075A8F);
  border:1px solid #80E5F5;color:white;
}
QTreeWidget::item:hover:!selected {background:rgba(55,126,158,88);}
QTreeWidget::branch {background:transparent;}
QTableWidget {background:rgba(3,26,44,135);border:1px solid #608DA7;border-radius:3px;outline:0;gridline-color:transparent;font-size:14px;font-weight:400;}
QTableWidget::item {border:0;}
QHeaderView {background:transparent;}
QHeaderView::section {
  background:#1D4962;border:0;border-bottom:1px solid #35637C;border-right:1px solid #3A657D;
  padding:6px;color:#EAF4FA;font-size:14px;font-weight:400;
}
QHeaderView::up-arrow {image:url(@UP@);width:7px;height:5px;}
QHeaderView::down-arrow {image:url(@DOWN@);width:7px;height:5px;}
QTableCornerButton::section {background:#18445C;border:0;}
QScrollArea,QStackedWidget,QScrollArea QWidget#qt_scrollarea_viewport {background:transparent;border:0;}
QPlainTextEdit {background:rgba(3,29,47,190);border:1px solid #5C91AC;border-radius:3px;}
QPlainTextEdit#itemDescription {
  background:rgba(2,26,42,202);border:1px solid #679EB6;border-radius:3px;
  font-family:'Cambria','DejaVu Serif';font-size:16px;color:#EEF3F7;padding:9px;
}
QScrollBar:vertical {background:#092A42;width:12px;margin:14px 1px 14px 1px;border:1px solid #5385A0;}
QScrollBar::handle:vertical {
  background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #83B2CB,stop:.5 #C4DCE8,stop:1 #4F87A6);
  border:1px solid #46738B;min-height:28px;border-radius:1px;
}
QScrollBar::add-line:vertical {height:13px;subcontrol-position:bottom;subcontrol-origin:margin;background:#235371;border:1px solid #75A9C1;}
QScrollBar::sub-line:vertical {height:13px;subcontrol-position:top;subcontrol-origin:margin;background:#235371;border:1px solid #75A9C1;}
QScrollBar::up-arrow:vertical {image:url(@UP@);width:7px;height:5px;}
QScrollBar::down-arrow:vertical {image:url(@DOWN@);width:7px;height:5px;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
QScrollBar:horizontal {height:9px;background:#0A2D45;}
QScrollBar::handle:horizontal {background:#6E9DB5;min-width:25px;}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {width:0;}
QMenu {background:#0C324B;color:#EAF6FF;border:1px solid #689EBA;padding:5px;}
QMenu::item {padding:8px 22px 8px 16px;}
QMenu::item:selected {background:#0C7FAF;}
QMenu::separator {height:1px;background:#315D76;margin:5px;}
QLabel#saveStateChip {font-size:11px;color:#BFDAE7;padding:2px 7px;border:1px solid rgba(116,172,190,100);border-radius:3px;background:rgba(5,37,52,120);}
QLabel#saveStateChip[state="dirty"] {color:#FFE6B6;border-color:#BFA46D;background:rgba(86,58,23,180);}
QLabel#saveStateChip[state="clean"] {color:#BDDFDB;}
QWidget#footerRow {border-top:1px solid rgba(101,177,203,90);background:transparent;}
QToolTip {background:#0B314B;color:#EAF6FF;border:1px solid #7CB8CD;padding:5px;}
QMessageBox {background:#0B2B43;}
QMessageBox QPushButton {background:#145374;border:1px solid #7BAFC4;min-width:75px;padding:7px 14px;}
'''
HUD_STYLESHEET = HUD_STYLESHEET.replace('@UP@',resource_path('assets/hud_arrow_up.svg').as_posix()).replace('@DOWN@',resource_path('assets/hud_arrow_down.svg').as_posix())

HUD_STYLESHEET=HUD_STYLESHEET.replace('@CHECK@',resource_path('assets/hud_check.svg').as_posix())

# v7.9.1: edit feedback and review keep the same dark glass palette.
HUD_STYLESHEET += r'''
QLabel#itemCategoryBadge {font-size:12px;color:#A4CEDD;}
QLabel#quantityChange {font-size:13px;color:#99D9EA;padding:0 0 1px 0;}
QLabel#toastNotice {
  background:#113D54;border:1px solid #61B9CE;border-left:3px solid #74DCEB;
  color:#E7F8FF;border-radius:4px;padding:9px 13px;font-size:13px;
}
QDialog#changesDialog {
  background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #123E56,stop:1 #06273E);
  border:1px solid #7EB7CD;
}
QLabel#reviewHeading {font-size:21px;font-weight:600;color:#F4FAFF;}
QLabel#reviewNote {font-size:12px;color:#A6CBDD;}
QLabel#reviewDestination {font-size:13px;color:#ADD5E5;}
QTableWidget#reviewTable {background:#082C42;alternate-background-color:#123C52;selection-background-color:#136D97;}
QTableWidget#reviewTable::item {padding:4px 6px;border-bottom:1px solid #18445D;}
'''

# v7.9.2: first-launch guidance uses the existing game-style chrome.
HUD_STYLESHEET += r'''
QScrollArea#firstLaunchScroller,QWidget#firstLaunchInner,QWidget#firstLaunchContent {background:transparent;border:0;}
QLabel#setupKicker {font-size:12px;letter-spacing:2px;color:#8EC9E0;}
QLabel#setupHeading {font-family:'Cambria','DejaVu Serif';font-size:33px;color:#F4FAFD;}
QLabel#setupIntro {font-size:15px;color:#BED7E5;}
QLabel#setupStep {font-size:14px;color:#B5EEFB;border:1px solid #578AA6;background:#103F59;border-radius:3px;}
QLabel#setupCardTitle {font-size:18px;font-weight:600;color:#F1F8FC;}
QLabel#setupCardText {font-size:14px;color:#B6D0DF;}
QLabel#setupStatus {font-size:13px;color:#A4C9DB;}
QLabel#setupStatus[state="ready"] {color:#8FE1D6;}
QLabel#setupStatus[state="busy"] {color:#A8E8F6;}
QLabel#setupStatus[state="error"],QLabel#setupStatus[state="warning"] {color:#F2C79C;}
QLabel#setupLater {font-size:12px;color:#9DBECE;}
QProgressBar#setupProgress {background:#06263C;border:1px solid #416C86;border-radius:2px;}
QProgressBar#setupProgress::chunk {background:#43BCDE;border:0;border-radius:1px;}
'''
