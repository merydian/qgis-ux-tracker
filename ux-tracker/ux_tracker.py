import csv
import os
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QEvent, QObject, QTimer
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolBar

class UXTracker(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self._connected_toolbars: dict = {}
        self.click_list: list = list()

    def initGui(self):
        self._connect_all()
        # At QGIS startup most toolbars don't exist yet; pick them up once
        # initialization finishes and whenever one is added later.
        self.iface.initializationCompleted.connect(self._connect_all)
        self.iface.mainWindow().installEventFilter(self)

    def unload(self):
        self.iface.initializationCompleted.disconnect(self._connect_all)
        self.iface.mainWindow().removeEventFilter(self)
        self._disconnect_all()
        self._export_log()

    def _export_log(self):
        base_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(base_dir, exist_ok=True)
        self.log_path = os.path.join(base_dir, "ux_tracker.csv")

        try:
            with open(self.log_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["timestamp", "toolbar", "action_label"])
                writer.writerows(self.click_list)
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

    def _disconnect_all(self):
        for toolbar, slot in self._connected_toolbars.items():
            try:
                toolbar.actionTriggered.disconnect(slot)
            except (RuntimeError, TypeError):
                pass  # toolbar already deleted or disconnected
        self._connected_toolbars.clear()

    def _on_action_triggered(self, action: QAction, toolbar_name: str):
        label_name = action.objectName()
        # Strip any Qt accelerator markers (e.g. "&Open" -> "Open")
        label_name = label_name.replace("&", "")
        self._log(toolbar_name=toolbar_name, label=label_name)

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            # Defer so the child is fully constructed before inspecting it.
            QTimer.singleShot(0, lambda c=event.child(): self._on_child_added(c))
        return False  # never consume the event

    def _on_child_added(self, child: QObject):
        if isinstance(child, QToolBar):
            self._connect_toolbar(child)
