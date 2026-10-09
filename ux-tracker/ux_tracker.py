import csv
import os
from collections import deque
from datetime import datetime

from qgis.PyQt.QtCore import QEvent, QObject, QTimer
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolBar

from .settings_dialog import SettingsDialog, load_settings, save_settings


class UXTracker(QObject):
    """QGIS plugin that queues toolbar-action triggers for CSV export."""

    def __init__(self, iface):
        super().__init__()
        self.iface = iface

        plugin_dir = os.path.dirname(__file__)
        base_dir = os.path.join(plugin_dir, "data")
        self.log_path = os.path.join(base_dir, "ux_tracker.csv")
        self.settings_path = os.path.join(base_dir, "ux_tracker_settings.json")
        os.makedirs(base_dir, exist_ok=True)

        self._settings = load_settings(self.settings_path)
        self._tracked_actions: set = set()
        self._recording = True
        self._settings_action: QAction = None
        self._export_action: QAction = None
        self.click_deque: deque = deque()

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def initGui(self):
        self._settings_action = QAction("UX Tracker Settings", self.iface.mainWindow())
        self._settings_action.setToolTip("UX Tracker – open settings")
        self._settings_action.triggered.connect(self._open_settings_dialog)
        self.iface.addToolBarIcon(self._settings_action)

        # Connect to widgets that already exist; defer so all plugins
        # have had a chance to add their own toolbars and panels.
        QTimer.singleShot(500, self._connect_all)

        # Watch for toolbars / panels added after our initGui completes.
        self.iface.mainWindow().installEventFilter(self)

        if self._recording:
            self.iface.messageBar().pushInfo(
                "UX Tracker", ":Recording" if self._recording else ":Not Recording"
            )

    def unload(self):
        self.iface.mainWindow().removeEventFilter(self)
        self._export_log()
        if self._settings_action:
            self.iface.removeToolBarIcon(self._settings_action)
            del self._settings_action
        if self._export_action:
            self.iface.removeToolBarIcon(self._export_action)
            del self._export_action
        self._recording = False

    def _export_log(self):

        try:
            with open(self.log_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["timestamp", "toolbar", "action_label"])
                writer.writerows(self.click_deque)
        except OSError as error:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "UX Tracker",
                f"Could not export log:\n{error}",
            )
            return

    def _log(self, toolbar_name: str, label: str):
        if not self._recording:
            return
        
        self.click_deque.append(
            [
                datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
                toolbar_name,
                label,
            ]
        )

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self._settings, parent=self.iface.mainWindow())
        if dlg.exec():
            self._settings["experience"] = dlg.selected_experience()
            self._settings["task"] = dlg.selected_task()
            save_settings(self.settings_path, self._settings)

    def _connect_all(self):
        mw = self.iface.mainWindow()
        for toolbar in mw.findChildren(QToolBar):
            self._connect_toolbar(toolbar)

    def _connect_toolbar(self, toolbar: QToolBar):
        toolbar_name = toolbar.objectName() or toolbar.windowTitle()
        for action in toolbar.actions():
            uid = id(action)
            if uid in self._tracked_actions:
                continue
            self._tracked_actions.add(uid)
            action.triggered.connect(
                lambda checked, a=action, t=toolbar_name: self._on_action_triggered(a, t, checked)
            )

    def _on_action_triggered(self, action: QAction, toolbar_name: str, checked: bool):
        label = action.text() or action.toolTip() or action.iconText() or ""
        # Strip any Qt accelerator markers (e.g. "&Open" -> "Open")
        label = label.replace("&", "")
        self._log(toolbar_name=toolbar_name, label=label)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            # Defer so the widget is fully initialised before we inspect it.
            QTimer.singleShot(0, lambda c=child: self._on_child_added(c))
        return False  # never consume the event

    def _on_child_added(self, child: QObject):
        if isinstance(child, QToolBar):
            self._connect_toolbar(child)
