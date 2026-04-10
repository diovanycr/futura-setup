# =============================================================================
# FUTURA SETUP -- Theme v7 (Windows 11 Fluent Design)
# Light mode v2:
#   - Camadas de superfície mais distintas e limpas
#   - Accent azul mais rico e hierárquico
#   - accent_dim mais suave e agradável
#   - Bordas refinadas
#   - Texto com melhor hierarquia
# Dark mode v2:
#   - Camadas de superfície mais distintas
#   - accent_dim com azul visível mas sutil
#   - Warn/danger com dim backgrounds visíveis
#   - Texto com melhor hierarquia
# =============================================================================

FONT_MONO  = "Consolas"
FONT_SANS  = "Segoe UI"
FONT_SEMI  = "Segoe UI Semibold"

LIGHT_COLORS = {
    # -- Fundos — camadas distintas ------------------------------------------
    "bg":           "#EFEFEF",   # fundo geral — cinza bem suave
    "surface":      "#FFFFFF",   # cards / dialogs — branco limpo
    "surface2":     "#F7F7F7",   # sidebar — levemente off-white
    "panel":        "#FFFFFF",
    "panel_hover":  "#F0F0F0",   # hover mais perceptível
    "panel_press":  "#E6E6E6",   # press

    # -- Bordas --------------------------------------------------------------
    "border":       "#DCDCDC",   # borda padrão
    "border_light": "#ECECEC",   # borda mais suave

    # -- Accent azul ----------------------------------------------------------
    "accent":       "#0067C0",   # azul mais rico que o original
    "accent_hover": "#005BAA",
    "accent_press": "#004F94",
    "accent_dim":   "#E5F1FB",   # fundo de item ativo — azul muito suave

    # -- Verde -----------------------------------------------------------------
    "accent2":      "#0E7A0E",   # verde mais profundo
    "accent2_dim":  "#E8F5E8",

    # -- Amarelo / Warn --------------------------------------------------------
    "warn":         "#835A00",   # âmbar escuro legível
    "warn_dim":     "#FEF6DC",

    # -- Vermelho / Danger -----------------------------------------------------
    "danger":       "#B52419",   # vermelho mais profundo
    "danger_dim":   "#FCEAE8",

    # -- Texto -----------------------------------------------------------------
    "text":         "#1C1C1C",   # quase preto (mais suave que puro)
    "text_mid":     "#4A4A4A",   # texto secundário
    "text_dim":     "#8A8A8A",   # rótulos / placeholders
    "text_disabled":"#BBBBBB",

    # -- Log -------------------------------------------------------------------
    "log_ok":       "#0E7A0E",
    "log_info":     "#0067C0",
    "log_warn":     "#835A00",
    "log_err":      "#B52419",

    # -- Misc ------------------------------------------------------------------
    "white":        "#1C1C1C",
    "btn_border":   "#C2C2C2",   # borda de botão secundário

    # -- Gradients -----------------------------------------------------------
    "grad_accent":  "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0078D4, stop:1 #0067C0)",
    "grad_surface": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9F9)",
}

DARK_COLORS = {
    # -- Fundos — camadas distintas ------------------------------------------
    "bg":           "#141414",   # fundo geral — mais escuro
    "surface":      "#1E1E1E",   # cards / dialogs
    "surface2":     "#191919",   # sidebar
    "panel":        "#1E1E1E",
    "panel_hover":  "#2A2A2A",   # hover em itens
    "panel_press":  "#323232",   # press

    # -- Bordas --------------------------------------------------------------
    "border":       "#2E2E2E",   # borda padrão
    "border_light": "#383838",   # borda mais clara

    # -- Accent azul (Windows dark) ------------------------------------------
    "accent":       "#4CC2FF",   # azul mais saturado e legível
    "accent_hover": "#38B4F7",
    "accent_press": "#25A7EF",
    "accent_dim":   "#122030",   # fundo de item ativo — azul bem sutil

    # -- Verde ----------------------------------------------------------------
    "accent2":      "#57C754",   # verde legível no dark
    "accent2_dim":  "#0E2210",

    # -- Amarelo / Warn -------------------------------------------------------
    "warn":         "#F5C518",   # amarelo mais quente
    "warn_dim":     "#272010",

    # -- Vermelho / Danger ----------------------------------------------------
    "danger":       "#F47C7C",   # vermelho suave legível
    "danger_dim":   "#2A1010",

    # -- Texto ----------------------------------------------------------------
    "text":         "#F0F0F0",   # quase branco (não puro para reduzir fadiga)
    "text_mid":     "#A8A8A8",   # texto secundário
    "text_dim":     "#636363",   # texto desabilitado / rótulos
    "text_disabled":"#454545",

    # -- Log ------------------------------------------------------------------
    "log_ok":       "#57C754",
    "log_info":     "#4CC2FF",
    "log_warn":     "#F5C518",
    "log_err":      "#F47C7C",

    # -- Misc -----------------------------------------------------------------
    "white":        "#F0F0F0",
    "btn_border":   "#404040",   # borda de botão secundário bem visível

    # -- Gradients -----------------------------------------------------------
    "grad_accent":  "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #60CDFF, stop:1 #4CC2FF)",
    "grad_surface": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2C2C2C, stop:1 #1E1E1E)",
}

COLORS = dict(LIGHT_COLORS)


def set_theme(mode: str):
    COLORS.update(LIGHT_COLORS if mode == "light" else DARK_COLORS)


def get_stylesheet(mode: str = "light") -> str:
    C = LIGHT_COLORS if mode == "light" else DARK_COLORS
    console_bg    = "#FAFAFA"  if mode == "light" else "#111111"
    primary_text  = "#FFFFFF"  if mode == "light" else "#001828"
    success_text  = "#FFFFFF"  if mode == "light" else "#001800"

    return f"""
QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}
QMainWindow {{ background-color: {C['bg']}; }}

/* -- SCROLLBAR ------------------------------------------------ */
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

/* -- LABEL ---------------------------------------------------- */
QLabel {{ background: transparent; color: {C['text']}; }}

/* -- INPUT ---------------------------------------------------- */
QLineEdit {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    color: {C['text']};
    font-family: 'Consolas';
    padding: 4px 12px;
    font-size: 11px;
    border-radius: 4px;
}}
QLineEdit:hover {{ border-color: {C['text_dim']}; }}
QLineEdit:focus {{ border: 1.5px solid {C['accent']}; }}

/* -- BOTÃO BASE ----------------------------------------------- */
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

/* -- PRIMARY -------------------------------------------------- */
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

/* -- SECONDARY ------------------------------------------------ */
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

/* -- SUCCESS -------------------------------------------------- */
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

/* -- DANGER --------------------------------------------------- */
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

/* -- PROGRESS BAR --------------------------------------------- */
QProgressBar {{
    background: {C['border']}; border: none; height: 3px; border-radius: 2px;
}}
QProgressBar::chunk {{
    background: {C['accent']}; border-radius: 2px;
}}

/* -- CONSOLE / LOG -------------------------------------------- */
QTextEdit {{
    background: {console_bg};
    border: 1px solid {C['border']};
    color: {C['text_mid']};
    font-family: 'Consolas';
    font-size: 11px;
    padding: 10px 14px;
    border-radius: 4px;
}}

/* -- TOOLTIP -------------------------------------------------- */
QToolTip {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    color: {C['text']};
    padding: 5px 10px;
    border-radius: 4px;
}}

/* -- RADIO ---------------------------------------------------- */
QRadioButton {{ spacing: 8px; color: {C['text']}; background: transparent; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['text_dim']}; border-radius: 8px; background: transparent;
}}
QRadioButton::indicator:checked {{
    border: 5px solid {C['accent']}; background: {C['surface']};
}}
QRadioButton::indicator:hover {{ border-color: {C['accent']}; }}

/* -- CHECKBOX ------------------------------------------------- */
QCheckBox {{ spacing: 8px; color: {C['text']}; background: transparent; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['text_dim']}; border-radius: 3px; background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border-color: {C['accent']};
}}
"""