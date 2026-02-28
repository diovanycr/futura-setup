# =============================================================================
# FUTURA SETUP -- Theme v6 (Windows 11 Fluent Design)
# Melhorias v6:
#   - QPushButton primary: azul sólido com texto branco
#   - QPushButton secondary: borda visível, fundo transparente
#   - QPushButton success: verde sólido
#   - QPushButton danger: borda vermelha, hover vira sólido
# =============================================================================

FONT_MONO  = "Consolas"
FONT_SANS  = "Segoe UI"
FONT_SEMI  = "Segoe UI Semibold"

LIGHT_COLORS = {
    "bg":           "#f3f3f3",
    "surface":      "#ffffff",
    "surface2":     "#f9f9f9",
    "panel":        "#ffffff",
    "panel_hover":  "#f5f5f5",
    "panel_press":  "#ededed",
    "border":       "#e0e0e0",
    "border_light": "#ebebeb",
    "accent":       "#0078D4",
    "accent_hover": "#006CBE",
    "accent_press": "#005FAD",
    "accent_dim":   "#EFF6FC",
    "accent2":      "#107C10",
    "accent2_dim":  "#EEF7EE",
    "warn":         "#9D5D00",
    "warn_dim":     "#FFF4CE",
    "danger":       "#C42B1C",
    "danger_dim":   "#FDE7E9",
    "text":         "#1a1a1a",
    "text_mid":     "#5a5a5a",
    "text_dim":     "#9a9a9a",
    "text_disabled":"#bbbbbb",
    "log_ok":       "#107C10",
    "log_info":     "#0078D4",
    "log_warn":     "#9D5D00",
    "log_err":      "#C42B1C",
    "white":        "#1a1a1a",
    "btn_border":   "#c8c8c8",
}

DARK_COLORS = {
    "bg":           "#202020",
    "surface":      "#2c2c2c",
    "surface2":     "#272727",
    "panel":        "#2c2c2c",
    "panel_hover":  "#333333",
    "panel_press":  "#3c3c3c",
    "border":       "#3d3d3d",
    "border_light": "#454545",
    "accent":       "#60CDFF",
    "accent_hover": "#4ec9f7",
    "accent_press": "#3abded",
    "accent_dim":   "#0d2a38",
    "accent2":      "#6CCB5F",
    "accent2_dim":  "#0d2a0d",
    "warn":         "#FCE100",
    "warn_dim":     "#2a2500",
    "danger":       "#FF99A4",
    "danger_dim":   "#2a0f10",
    "text":         "#ffffff",
    "text_mid":     "#c0c0c0",
    "text_dim":     "#808080",
    "text_disabled":"#505050",
    "log_ok":       "#6CCB5F",
    "log_info":     "#60CDFF",
    "log_warn":     "#FCE100",
    "log_err":      "#FF99A4",
    "white":        "#ffffff",
    "btn_border":   "#555555",
}

COLORS = dict(LIGHT_COLORS)


def set_theme(mode: str):
    COLORS.update(LIGHT_COLORS if mode == "light" else DARK_COLORS)


def get_stylesheet(mode: str = "light") -> str:
    C = LIGHT_COLORS if mode == "light" else DARK_COLORS
    console_bg = "#fafafa" if mode == "light" else "#1c1c1c"

    # No dark mode o accent é azul claro — texto escuro fica legível
    primary_text = "#ffffff" if mode == "light" else "#001826"
    success_text = "#ffffff" if mode == "light" else "#001a00"

    return f"""
QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: 'Segoe UI';
    font-size: 13px;
    border: none;
    outline: none;
}}
QMainWindow {{ background-color: {C['bg']}; }}

QScrollBar:vertical {{
    background: transparent; width: 6px; border: none; margin: 2px 1px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none; height: 0;
}}
QScrollBar:horizontal {{ height: 0; background: none; }}

QLabel {{ background: transparent; color: {C['text']}; }}

QLineEdit {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    color: {C['text']};
    font-family: 'Consolas';
    padding: 7px 12px;
    border-radius: 4px;
}}
QLineEdit:hover {{ border-color: {C['text_dim']}; }}
QLineEdit:focus {{ border: 1.5px solid {C['accent']}; }}

/* ── BOTÃO BASE (secondary implícito) ───────────────────────── */
QPushButton {{
    font-family: 'Segoe UI';
    font-size: 13px;
    padding: 7px 18px;
    border-radius: 6px;
    border: 1.5px solid {C['btn_border']};
    background: {C['surface']};
    color: {C['text']};
    min-height: 34px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {C['panel_hover']};
    border-color: {C['text_dim']};
}}
QPushButton:pressed {{ background: {C['panel_press']}; }}
QPushButton:disabled {{
    color: {C['text_disabled']};
    border-color: {C['border']};
    background: {C['panel_hover']};
}}

/* ── PRIMARY ────────────────────────────────────────────────── */
QPushButton[class~="primary"] {{
    background-color: {C['accent']};
    border: 1.5px solid {C['accent']};
    color: {primary_text};
    font-weight: 700;
}}
QPushButton[class~="primary"]:hover {{
    background-color: {C['accent_hover']};
    border-color: {C['accent_hover']};
    color: {primary_text};
}}
QPushButton[class~="primary"]:pressed {{
    background-color: {C['accent_press']};
    border-color: {C['accent_press']};
    color: {primary_text};
}}
QPushButton[class~="primary"]:disabled {{
    background-color: {C['panel_hover']};
    color: {C['text_disabled']};
    border-color: {C['border']};
}}

/* ── SECONDARY ──────────────────────────────────────────────── */
QPushButton[class~="secondary"] {{
    background: transparent;
    border: 1.5px solid {C['btn_border']};
    color: {C['text']};
    font-weight: 500;
}}
QPushButton[class~="secondary"]:hover {{
    background: {C['panel_hover']};
    border-color: {C['text_dim']};
}}
QPushButton[class~="secondary"]:pressed {{
    background: {C['panel_press']};
}}

/* ── SUCCESS ────────────────────────────────────────────────── */
QPushButton[class~="success"] {{
    background-color: {C['accent2']};
    border: 1.5px solid {C['accent2']};
    color: {success_text};
    font-weight: 700;
}}
QPushButton[class~="success"]:hover {{
    background-color: {C['accent2']};
    border-color: {C['accent2']};
    color: {success_text};
}}

/* ── DANGER ─────────────────────────────────────────────────── */
QPushButton[class~="danger"] {{
    background: {C['danger_dim']};
    border: 1.5px solid {C['danger']};
    color: {C['danger']};
    font-weight: 500;
}}
QPushButton[class~="danger"]:hover {{
    background-color: {C['danger']};
    border-color: {C['danger']};
    color: #ffffff;
}}
QPushButton[class~="danger"]:pressed {{
    background-color: {C['danger']};
    color: #ffffff;
}}

QProgressBar {{
    background: {C['border']}; border: none; height: 2px; border-radius: 1px;
}}
QProgressBar::chunk {{
    background: {C['accent']}; border-radius: 1px;
}}

QTextEdit {{
    background: {console_bg};
    border: 1px solid {C['border']};
    color: {C['text_mid']};
    font-family: 'Consolas';
    font-size: 11px;
    padding: 10px 14px;
    border-radius: 4px;
}}

QToolTip {{
    background: {C['surface']}; border: 1px solid {C['border']};
    color: {C['text']}; padding: 5px 10px; border-radius: 4px;
}}

QRadioButton {{ spacing: 8px; color: {C['text']}; background: transparent; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['text_dim']}; border-radius: 8px; background: transparent;
}}
QRadioButton::indicator:checked {{ border: 5px solid {C['accent']}; background: {C['surface']}; }}
QRadioButton::indicator:hover {{ border-color: {C['accent']}; }}

QCheckBox {{ spacing: 8px; color: {C['text']}; background: transparent; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['text_dim']}; border-radius: 3px; background: transparent;
}}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
"""
