"""
vector_tracer_pro.app
~~~~~~~~~~~~~~~~~~~~~

Entrypoint module for launching the Vector Tracer Pro desktop application.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from vector_tracer_pro.core.path_manager import PathManager
from vector_tracer_pro.core.pipeline import Pipeline
from vector_tracer_pro.services.batch_runner import BatchRunner
from vector_tracer_pro.services.preset_manager import PresetManager
from vector_tracer_pro.ui.controllers.main_controller import MainController
from vector_tracer_pro.ui.main_window import MainWindow
from vector_tracer_pro.ui.styles.dark_theme import DARK_THEME_STYLE

# Setup basic logging to stdout/file
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("vector_tracer_pro")


def main() -> None:
    """Initialize core engines, services, styles, window, controller, and starts Qt event loop."""
    logger.info("Initializing Vector Tracer Pro...")

    # 1. Instantiate Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Tracer Pro")
    app.setApplicationDisplayName("Vector Tracer Pro")
    app.setOrganizationName("Vector Tracer Pro Team")

    # 2. Apply Custom Premium Dark QSS Style
    app.setStyleSheet(DARK_THEME_STYLE)

    # 3. Instantiate Core and Services
    try:
        path_manager = PathManager()
        path_manager.ensure_all_dirs()

        pipeline = Pipeline()
        batch_runner = BatchRunner()
        preset_manager = PresetManager(path_manager.get_user_presets_dir())
    except Exception as e:
        logger.critical("Failed to initialize backend services: %s", e)
        sys.exit(1)

    # 4. Instantiate UI views and Controllers
    window = MainWindow()
    controller = MainController(
        window=window,
        pipeline=pipeline,
        batch_runner=batch_runner,
        preset_manager=preset_manager,
    )

    # 5. Show window and execute event loop
    window.show()
    logger.info("Window visible, starting Qt event loop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
