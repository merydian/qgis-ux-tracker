import csv
import math
import os
import shutil
from datetime import datetime

from qgis.PyQt.QtCore import QEvent, QObject, QTimer
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QFileDialog, QMessageBox, QToolBar

from .settings_dialog import SettingsDialog, load_settings, save_settings


class UXTracker(QObject):
    """QGIS plugin that logs every toolbar-action trigger and panel
    visibility change to a CSV file in the plugin's data directory."""

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
        self._tracked_docks: set = set()
        self._csv_file = None
        self._csv_writer = None
        self._recording = False
        self._settings_action: QAction = None
        self._export_action: QAction = None
        self._last_event_time: datetime = None
        self._last_cursor_pos = None  # QPoint (global screen coords)

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def initGui(self):
        self._settings_action = QAction("UX Tracker Settings", self.iface.mainWindow())
        self._settings_action.setToolTip("UX Tracker – open settings")
        self._settings_action.triggered.connect(self._open_settings_dialog)
        self.iface.addToolBarIcon(self._settings_action)

        self._export_action = QAction("UX Tracker Export", self.iface.mainWindow())
        self._export_action.setToolTip("UX Tracker – export log CSV")
        self._export_action.triggered.connect(self._export_log)
        self.iface.addToolBarIcon(self._export_action)

        self._open_log()

        # Connect to widgets that already exist; defer so all plugins
        # have had a chance to add their own toolbars and panels.
        QTimer.singleShot(500, self._connect_all)

        # Watch for toolbars / panels added after our initGui completes.
        self.iface.mainWindow().installEventFilter(self)

        if self._recording:
            self.iface.messageBar().pushInfo(
                "UX Tracker", f"Recording to {self.log_path}"
            )

    def unload(self):
        self.iface.mainWindow().removeEventFilter(self)
        if self._settings_action:
            self.iface.removeToolBarIcon(self._settings_action)
            del self._settings_action
        if self._export_action:
            self.iface.removeToolBarIcon(self._export_action)
            del self._export_action
        self._close_log()

    # ------------------------------------------------------------------
    # Log file helpers
    # ------------------------------------------------------------------

    def _open_log(self):
        if self._csv_file:
            return
        try:
            needs_header = not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0
            self._csv_file = open(self.log_path, "a", newline="", encoding="utf-8")
            self._csv_writer = csv.writer(self._csv_file)
            if needs_header:
                self._csv_writer.writerow(
                    ["timestamp", "experience", "task", "event_type", "widget_type",
                     "object_name", "label", "detail", "delta_ms", "cursor_dist_px"]
                )
            self._csv_writer.writerow([
                datetime.now().isoformat(timespec="milliseconds"),
                self._settings.get("experience", ""),
                self._settings.get("task", ""),
                "session_start", "", "", "", "", "", "",
            ])
            self._csv_file.flush()
            self._recording = True
        except OSError as e:
            self._recording = False
            try:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"UX Tracker: could not open log file: {e}", "UX Tracker", Qgis.MessageLevel.Critical)
            except Exception:
                pass

    def _close_log(self):
        self._recording = False
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

    def _log(self, event_type: str, widget_type: str, object_name: str, label: str, detail: str = ""):
        if not self._recording or not self._csv_writer:
            return

        now = datetime.now()
        cursor_pos = QCursor.pos()

        delta_ms = ""
        if self._last_event_time is not None:
            delta_ms = round((now - self._last_event_time).total_seconds() * 1000)

        cursor_dist_px = ""
        if self._last_cursor_pos is not None:
            dx = cursor_pos.x() - self._last_cursor_pos.x()
            dy = cursor_pos.y() - self._last_cursor_pos.y()
            cursor_dist_px = round(math.sqrt(dx * dx + dy * dy))

        self._last_event_time = now
        self._last_cursor_pos = cursor_pos

        self._csv_writer.writerow(
            [
                now.isoformat(timespec="milliseconds"),
                self._settings.get("experience", ""),
                self._settings.get("task", ""),
                event_type,
                widget_type,
                object_name,
                label,
                detail,
                delta_ms,
                cursor_dist_px,
            ]
        )
        self._csv_file.flush()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_log(self):
        if not os.path.exists(self.log_path):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "UX Tracker",
                "No log file found yet. Interact with QGIS first to generate data.",
            )
            return

        dest, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Export UX Tracker log",
            os.path.expanduser("~/ux_tracker.csv"),
            "CSV files (*.csv)",
        )
        if not dest:
            return

        # Flush so the copy contains the latest rows.
        if self._csv_file:
            self._csv_file.flush()

        shutil.copy2(self.log_path, dest)
        QMessageBox.information(
            self.iface.mainWindow(),
            "UX Tracker",
            f"Log exported to:\n{dest}",
        )

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self._settings, parent=self.iface.mainWindow())
        if dlg.exec():
            self._settings["experience"] = dlg.selected_experience()
            self._settings["task"] = dlg.selected_task()
            save_settings(self.settings_path, self._settings)

    # ------------------------------------------------------------------
    # Connect to existing widgets
    # ------------------------------------------------------------------

    def _connect_all(self):
        mw = self.iface.mainWindow()
        for toolbar in mw.findChildren(QToolBar):
            self._connect_toolbar(toolbar)
        for dock in mw.findChildren(QDockWidget):
            self._connect_dock(dock)

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

    def _connect_dock(self, dock: QDockWidget):
        uid = id(dock)
        if uid in self._tracked_docks:
            return
        self._tracked_docks.add(uid)
        dock.visibilityChanged.connect(
            lambda visible, d=dock: self._on_dock_visibility(d, visible)
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_action_triggered(self, action: QAction, toolbar_name: str, checked: bool):
        label = action.text() or action.toolTip() or action.iconText() or ""
        # Strip any Qt accelerator markers (e.g. "&Open" -> "Open")
        label = label.replace("&", "")
        self._log(
            event_type="toolbar_action",
            widget_type="QAction",
            object_name=action.objectName() or "",
            label=label,
            detail=f"toolbar={toolbar_name} checked={checked}",
        )

    def _on_dock_visibility(self, dock: QDockWidget, visible: bool):
        self._log(
            event_type="panel_visibility",
            widget_type="QDockWidget",
            object_name=dock.objectName() or "",
            label=dock.windowTitle() or "",
            detail=f"visible={visible}",
        )

    # ------------------------------------------------------------------
    # Event filter – detect dynamically added toolbars / panels
    # ------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            # Defer so the widget is fully initialised before we inspect it.
            QTimer.singleShot(0, lambda c=child: self._on_child_added(c))
        return False  # never consume the event

    def _on_child_added(self, child: QObject):
        if isinstance(child, QToolBar):
            self._connect_toolbar(child)
        elif isinstance(child, QDockWidget):
            self._connect_dock(child)
