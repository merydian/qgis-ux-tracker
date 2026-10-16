import csv
import os
import uuid
import json
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QObject, QSettings
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolBar


class UXTracker(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self._connected_toolbars: dict = {}
        self.click_list: list[list[str]] = []
        self.max_clicks: int = 10
        self.user_id: str = self._get_or_create_user_id()

    @staticmethod
    def _get_or_create_user_id() -> str:
        settings = QSettings()
        user_id = settings.value("ux_tracker/uuid")
        if not user_id:
            user_id = str(uuid.uuid2())
            settings.setValue("ux_tracker/uuid", user_id)
        return str(user_id)

    def initGui(self):
        self.iface.initializationCompleted.connect(self._connect_all)
        self.iface.mainWindow().installEventFilter(self)

    def unload(self):
        self.iface.initializationCompleted.disconnect(self._connect_all)
        self.iface.mainWindow().removeEventFilter(self)
        self._disconnect_all()

    def _export_log(self):
        base_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(base_dir, exist_ok=True)
        self.log_path = os.path.join(base_dir, "ux_tracker.json")

        try:
            with open(self.log_path, 'w') as f:
                json.dump({self.user_id: self.click_list}, f)
        except OSError as error:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "UX Tracker",
                f"Could not export log:\n{error}",
            )
            return

    def _log(self, toolbar_name: str, label: str):
        self.click_list.append(
            [
                datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                toolbar_name,
                label,
            ]
        )
        if len(self.click_list) >= self.max_clicks:
            self._export_log()
            self.click_list.clear()

    def _connect_all(self):
        for toolbar in self.iface.mainWindow().findChildren(QToolBar):
            self._connect_toolbar(toolbar)

    def _connect_toolbar(self, toolbar: QToolBar):
        if toolbar in self._connected_toolbars:
            return
        toolbar_name = toolbar.objectName()

        def slot(action: QAction, t=toolbar_name):
            self._on_action_triggered(action, t)

        # actionTriggered covers actions added to the toolbar later as well.
        toolbar.actionTriggered.connect(slot)
        self._connected_toolbars[toolbar] = slot

    def _on_action_triggered(self, action: QAction, toolbar_name: str):
        label_name = action.objectName()
        label_name = label_name.replace("&", "")
        self._log(toolbar_name=toolbar_name, label=label_name)

    def _disconnect_all(self):
        for toolbar, slot in self._connected_toolbars.items():
            try:
                toolbar.actionTriggered.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connected_toolbars.clear()
