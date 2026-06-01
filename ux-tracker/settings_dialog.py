import json
import os

from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)


EXPERIENCE_LEVELS = ["Beginner", "Intermediate", "Advanced"]
TASKS = ["Digitize", "View data", "Analyse data"]


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UX Tracker – Settings")
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)

        # --- Experience level ---
        exp_group = QGroupBox("User experience")
        exp_layout = QVBoxLayout(exp_group)
        self._exp_buttons = QButtonGroup(self)
        for level in EXPERIENCE_LEVELS:
            rb = QRadioButton(level)
            if level == settings.get("experience", EXPERIENCE_LEVELS[0]):
                rb.setChecked(True)
            self._exp_buttons.addButton(rb)
            exp_layout.addWidget(rb)
        layout.addWidget(exp_group)

        # --- Current task ---
        task_group = QGroupBox("What I'm doing")
        task_layout = QVBoxLayout(task_group)
        self._task_buttons = QButtonGroup(self)
        for task in TASKS:
            rb = QRadioButton(task)
            if task == settings.get("task", TASKS[0]):
                rb.setChecked(True)
            self._task_buttons.addButton(rb)
            task_layout.addWidget(rb)
        layout.addWidget(task_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_experience(self) -> str:
        for btn in self._exp_buttons.buttons():
            if btn.isChecked():
                return btn.text()
        return EXPERIENCE_LEVELS[0]

    def selected_task(self) -> str:
        for btn in self._task_buttons.buttons():
            if btn.isChecked():
                return btn.text()
        return TASKS[0]


def load_settings(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"experience": EXPERIENCE_LEVELS[0], "task": TASKS[0]}


def save_settings(path: str, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
