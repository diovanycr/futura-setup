# =============================================================================
# FUTURA SETUP — UI: Widgets Facade (Backward Compatibility)
# =============================================================================

from ui.components.base import (
    hex_to_rgb, card_style, label, HLine, h_line, spacer
)
from ui.components.buttons import (
    make_primary_btn, make_secondary_btn, make_folder_btn, make_danger_btn, btn_row,
    _apply_primary_style, _apply_secondary_style
)
from ui.components.feedback import (
    SectionHeader, PageHeader, AlertBox, ProgressBlock, StepIndicator, LoadingSpinner,
    ResultBox
)
from ui.components.containers import (
    LogConsole, FadeStackedWidget, BusyOverlay
)
from ui.components.cards import (
    ServerItem, RadioRow, MiniFileItem, DestPanel, ProcessCard, CustomPathCard
)
from ui.components.dialogs import (
    ConfirmDialog, WorkerGuardDialog
)

# Alias para compatibilidade legado se necessário
PageTitle = PageHeader
make_btn = make_secondary_btn