import os
import uuid
import json
from datetime import datetime, timezone

from qgis.core import QgsSettings, Qgis, QgsApplication
from qgis.PyQt.QtCore import QObject, QEvent
from qgis.PyQt.QtWidgets import QToolBar


class UXTracker(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self._connected_toolbars: dict = {}
        self.click_list: list[list[str]] = []
        self.max_clicks: int = 10
        self.user_id: str = self._get_or_create_user_id()

    def _get_or_create_user_id(self) -> str:
        settings = QgsSettings()
        user_id = settings.value("ux_tracker/uuid")
        if not user_id:
            user_id = str(uuid.uuid1())
            settings.setValue("ux_tracker/uuid", user_id)
        return str(user_id)

    def initGui(self):
        QgsApplication.instance().installEventFilter(self)

    def unload(self):
        QgsApplication.instance().removeEventFilter(self)

    def _export_log(self):
        base_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(base_dir, exist_ok=True)
        self.log_path = os.path.join(base_dir, "ux_tracker.json")

        try:
            with open(self.log_path, "w") as f:
                json.dump({self.user_id: self.click_list}, f)
        except OSError:
            self.iface.messageBar().pushMessage(
                "UX Tracker", "Failed to write json file.", Qgis.MessageLevel.Critical
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

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            try:
                if isinstance(obj.parent(), QToolBar):
                    print((obj.parent().objectName(), obj.defaultAction().objectName()))
                    self._log(
                        obj.parent().objectName(), obj.defaultAction().objectName()
                    )
            except Exception:
                return False
        return False
