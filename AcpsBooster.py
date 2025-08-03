from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import QThread, Qt, pyqtSignal, pyqtSlot, QMutex
from PyQt6.QtGui import QPixmap, QPainter, QFont, QIcon

from pynput.keyboard import Controller as KController, Listener as KeyboardListener
from pynput.mouse import Controller as MController, Listener as MouseListener
from pynput import keyboard, mouse
from pynput.mouse import Button

import time
import sys
import threading


class ClickBooster(QThread):
    update_clicks = pyqtSignal(int)
    update_info = pyqtSignal(str)
    stopped = pyqtSignal()
    target_reached = pyqtSignal()

    def __init__(self, key_to_click, hold_or_toggle, get_cps, stop_at, trigger_key):
        super().__init__()
        self.key_to_click = key_to_click
        self.hold_or_toggle = hold_or_toggle
        self.get_cps = get_cps
        self.stop_at = stop_at
        self.trigger_key = trigger_key

        self.total_clicks = 0
        self.keyboard_controller = KController()
        self.mouse_controller = MController()
        self.is_keydown = False
        self.is_toggled_on = False
        self.stop_booster = False
        self.mutex = QMutex()
        self.should_stop = False
        self.booster_thread = None
        self.listener = None

    def stop(self):
        self.mutex.lock()
        self.should_stop = True
        self.stop_极ooster = True
        self.is_keydown = False
        self.is_toggled_on = False
        self.mutex.unlock()

        self.update_info.emit("# Info: Boosting has been stopped.")

    def is_mouse_key(self, key):
        mouse_key = [Button.left, Button.middle, Button.right]
        return key in mouse_key

    def booster(self):
        click_delay = 1.0 / self.get_cps
        next_time = time.time()

        while True:
            self.mutex.lock()
            if self.stop_booster or not self.is_keydown or self.should_stop:
                self.stop_booster = False
                self.mutex.unlock()
                break
            self.mutex.unlock()

            self.mouse_controller.click(self.key_to_click, 1)
            self.total_clicks += 1
            self.update_clicks.emit(self.total_clicks)

            # Check if we've reached the stop-at count
            if self.stop_at is not None and self.total_clicks >= self.stop_at:
                self.mutex.lock()
                self.stop极ooster = True
                self.mutex.unlock()
                self.target_reached.emit()
                break

            next_time += click_delay
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

    def start_booster_thread(self):
        if self.booster_thread and self.booster_thread.is_alive():
            return

        self.booster_thread = threading.Thread(target=self.booster)
        self.booster_thread.daemon = True
        self.booster_thread.start()

    def on_mouse_click(self, x, y, button, pressed):
        if pressed and button == self.trigger_key:
            self.mutex.lock()
            self.is_keydown = True
            self.start_booster_thread()
            self.mutex.unlock()

    def on_keyboard_press(self, key):
        try:
            if hasattr(key, "char") and key.char == self.trigger_key:
                self.mutex.lock()
                self.is_keydown = True
                self.start_booster_thread()
                self.mutex.unlock()
        except Exception:
            pass

    def on_key_release(self, key):
        try:
            if hasattr(key, "char") and key.char == self.trigger_key:
                self.mutex.lock()
                self.is_keydown = False
                self.mutex.unlock()
        except Exception:
            pass

    def on_button_release(self, x, y, button, pressed):
        if not pressed and button == self.trigger_key:
            self.mutex.lock()
            self.is_keydown = False
            self.mutex.unlock()

    def on_mouse_key_toggled(self, x, y, button, pressed):
        if pressed and button == self.trigger_key:
            self.mutex.lock()
            self.is_toggled_on = not self.is_toggled_on
            self.is_keydown = self.is_toggled_on
            if self.is_toggled_on:
                self.start_booster_thread()
            else:
                self.stop_booster = True
            self.mutex.unlock()

    def on_keyboard_key_toggled(self, key):
        try:
            if hasattr(key, "char") and key.char == self.trigger_key:
                self.mutex.lock()
                self.is_toggled_on = not self.is_toggled_on
                self.is_keydown = self.is_toggled_on
                if self.is_toggled_on:
                    self.start_booster_thread()
                else:
                    self.stop_booster = True
                self.mutex.unlock()
        except Exception:
            pass

    def run(self):
        self.should_stop = False

        if self.is_mouse_key(key=self.trigger_key):
            if self.hold_or_toggle == "toggle":
                self.listener = MouseListener(on_click=self.on_mouse_key_toggled)
            elif self.hold_or_toggle == "hold":
                self.listener = MouseListener(
                    on_click=self.on_mouse_click, on_release=self.on_button_release
                )
        else:
            if self.hold_or_toggle == "toggle":
                self.listener = KeyboardListener(on_press=self.on_keyboard_key_toggled)
            elif self.hold_or_toggle == "hold":
                self.listener = KeyboardListener(
                    on_press=self.on_keyboard_press, on_release=self.on_key_release
                )

        if self.listener:
            self.listener.start()

        # Main thread loop
        while not self.should_stop:
            time.sleep(0.1)

        # Cleanup
        if self.listener and self.listener.is_alive():
            self.listener.stop()

        if self.booster_thread and self.booster_thread.is_alive():
            # Wait for booster thread to finish
            self.booster_thread.join(timeout=0.5)

        self.total_clicks = 0
        self.update_clicks.emit(0)
        self.stopped.emit()


class KeyCaptureButton(QPushButton):
    def __init__(self, parent, width=180, height=22):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setFont(QFont("Arial", 8))
        self.clicked.connect(self.start_capture)
        self.key = None
        self.setText("Click to Set Key")

    def start_capture(self):
        self.setEnabled(False)
        self.setText("Press a Key")
        self.key = None
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.keyboard_listener.start()
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()

    def on_key_press(self, key):
        self.key = key
        self.set_key_text()

    def on_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.key = button
            self.set_key_text()

    def set_key_text(self):
        key_text = self.get_key_text(self.key)
        self.setText(key_text)
        self.keyboard_listener.stop()
        self.mouse_listener.stop()

        self.setEnabled(False)
        time.sleep(0.4)
        self.setEnabled(True)

    def get_key_text(self, key):
        if isinstance(key, keyboard.KeyCode):
            return key.char
        elif isinstance(key, mouse.Button):
            return f"Mouse {key.name}"
        return "Unknown"


class QtAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.clicking_thread = None

        # Set window title and fixed size
        self.setWindowTitle("AcpsBooster")
        self.setWindowFlags(
            Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedSize(254, 448)

        # Set a mouse emoji as title bar icon
        app_icon_emoji = QPixmap(32, 32)
        app_icon_emoji.fill(Qt.GlobalColor.transparent)
        painter = QPainter(app_icon_emoji)
        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.drawText(
            app_icon_emoji.rect(), Qt.AlignmentFlag.AlignCenter, "\U0001f400"
        )
        painter.end()
        self.setWindowIcon(QIcon(app_icon_emoji))

        # Set up the first group of widgets
        self.first_group_widget = QWidget(self)
        self.first_group_widget.setGeometry(7, 5, 242, 115)
        self.first_group_box = QGroupBox(
            "Select Mouse Button to Click", self.first_group_widget
        )

        # Add a radio button and set it checked
        self.left_radio_button = QRadioButton("Left", self.first_group_box)
        # Set the 'left_radio_button' to default
        self.left_radio_button.setChecked(True)
        self.middle_radio_button = QRadioButton("Middle", self.first_group_box)
        self.right_radio_button = QRadioButton("Right", self.first_group_box)

        self.layout_1 = QVBoxLayout(self.first_group_box)
        self.layout_1.addWidget(self.left_radio_button)
        self.layout_1.addWidget(self.middle_radio_button)
        self.layout_1.addWidget(self.right_radio_button)
        self.layout_1.setSpacing(5)

        self.first_group_box.setLayout(self.layout_1)

        self.vbox_1 = QVBoxLayout(self.first_group_widget)
        self.vbox_1.addWidget(self.first_group_box)

        # Set up the second group
        self.second_group_widget = QWidget(self)
        self.second_group_widget.setGeometry(7, 105, 242, 95)
        self.second_group_box = QGroupBox("Hold/Toggle", self.second_group_widget)

        # Add a radio button and set it checked
        self.hold_radio_button = QRadioButton("Hold", self.second_group_box)
        self.hold_radio_button.setChecked(True)

        self.toggle_radio_button = QRadioButton("Toggle", self.second_group_box)

        self.layout_2 = QVBoxLayout(self.second_group_box)
        self.layout_2.addWidget(self.hold_radio_button)
        self.layout_2.addWidget(self.toggle_radio_button)
        self.layout_2.setSpacing(5)

        self.second_group_box.setLayout(self.layout_2)

        self.vbox_2 = QVBoxLayout(self.second_group_widget)
        self.vbox_2.addWidget(self.second_group_box)

        # Set up the third group of widgets
        self.third_group_widget = QWidget(self)
        self.third_group_widget.setGeometry(7, 185, 242, 160)
        self.third_group_box = QGroupBox("Options", self.third_group_widget)

        self.layout_3 = QVBoxLayout(self.third_group_box)
        self.third_group_box.setLayout(self.layout_3)

        self.cps_layout = QHBoxLayout()
        self.cps_label = QLabel("Get cps:", self.third_group_box)

        self.cps_entry = QLineEdit(self.third_group_box)
        self.cps_entry.setMaxLength(3)
        self.cps_entry.setText(str(10))

        self.cps_layout.addWidget(self.cps_label)
        self.cps_layout.addWidget(self.cps_entry)
        self.layout_3.addLayout(self.cps_layout)

        self.stop_at_layout = QHBoxLayout()
        self.stop_at_label = QLabel("Stop at:", self.third_group_box)
        self.stop_at_entry = QLineEdit(self.third_group_box)
        self.stop_at_layout.addWidget(self.stop_at_label)
        self.stop_at_layout.addWidget(self.stop_at_entry)
        self.layout_3.addLayout(self.stop_at_layout)

        self.trigger_layout = QHBoxLayout()
        self.trigger_label = QLabel("Trigger:", self.third_group_box)
        self.trigger_button = KeyCaptureButton(self.third_group_box, width=160)

        self.trigger_layout.addWidget(self.trigger_label)
        self.trigger_layout.addWidget(self.trigger_button)
        self.layout_3.addLayout(self.trigger_layout)

        self.button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start", self.third_group_box)
        self.start_button.clicked.connect(self.start_button_clicked)

        self.stop_button = QPushButton("Stop", self.third_group_box)
        self.stop_button.clicked.connect(self.stop_button_clicked)

        self.button_layout.addWidget(self.start_button)
        self.button_layout.addWidget(self.stop_button)
        self.layout_3.addLayout(self.button_layout)

        self.vbox_3 = QVBoxLayout(self.third_group_widget)
        self.vbox_3.addWidget(self.third_group_box)
        self.third_group_widget.setLayout(self.vbox_3)

        # Set up the fourth group of widgets
        self.fourth_group_widget = QWidget(self)
        self.fourth_group_widget.setGeometry(7, 330, 242, 112)

        self.fourth_group_box = QGroupBox("Information", self.fourth_group_widget)
        self.info_frame_layout = QVBoxLayout(self.fourth_group_box)
        self.fourth_group_box.setLayout(self.info_frame_layout)

        self.clicks_layout = QHBoxLayout()
        self.clicks_label = QLabel(f"# Clicks: {str(0)}", self.fourth_group_box)
        self.clicks_layout.addWidget(self.clicks_label)

        self.info_frame_layout.addLayout(self.clicks_layout)

        self.info_label = QLabel(
            "# Info: AcpsBooster is not boosting\n your cps currently, click start!!",
            self.fourth_group_box,
        )
        self.info_frame_layout.addWidget(self.info_label)

        self.vbox_4 = QVBoxLayout(self.fourth_group_widget)
        self.vbox_4.addWidget(self.fourth_group_box)
        self.fourth_group_widget.setLayout(self.vbox_4)

        self.setStyleSheet(
            """
            QLineEdit {
                border-radius: 5px;
                padding: 3px 8px;
                border: 1px solid palette(mid);
                max-width: 138px;
            }
        """
        )
        
        # Disable stop button initially
        self.stop_button.setEnabled(False)

    def is_mouse_key(self, key):
        mouse_keys = [Button.left, Button.middle, Button.right]
        return key in mouse_keys

    def is_valid_key(self, key):
        return isinstance(key, (keyboard.KeyCode, mouse.Button))

    @pyqtSlot()
    def start_button_clicked(self):
        # Get the selected mouse/keyboard key
        key_to_click = ""

        if self.left_radio_button.isChecked():
            key_to_click = Button.left
        elif self.middle_radio_button.isChecked():
            key_to_click = Button.middle
        elif self.right_radio_button.isChecked():
            key_to_click = Button.right

        # Check if hold or toggle is selected
        hold_or_toggle = ""

        if self.hold_radio_button.isChecked():
            hold_or_toggle = "hold"
        elif self.toggle_radio_button.isChecked():
            hold_or_toggle = "toggle"

        # Check if correct cps value is given
        get_cps = self.cps_entry.text()
        if not get_cps.isnumeric() or get_cps == "":
            QMessageBox.warning(
                self, "Invalid CPS Value", "Please select a valid number for CPS."
            )
            return

        cps = int(get_cps)

        # Check if correct stop at value is given
        stop_at = self.stop_at_entry.text()
        if not stop_at.isnumeric() and not stop_at == "":
            QMessageBox.warning(
                self,
                "Invalid Stop Value",
                "Please enter a valid number for stop value.",
            )
            return

        stop_value = int(stop_at) if stop_at else None

        # Get the selected mouse/keyboard key to trigger
        trigger_key = self.trigger_button.key
        if not self.is_valid_key(trigger_key) or trigger_key == "Unknown":
            QMessageBox.warning(
                self, "Invalid Key", "Please select a valid and known key to trigger."
            )
            return

        # Make sure not to start if key to click and key to trigger are same
        if str(key_to_click) == str(trigger_key):
            QMessageBox.warning(
                self,
                "What are you doing?",
                "You cannot select same key for 'Trigger' and 'Key to click'.",
            )
            return

        if self.is_mouse_key(trigger_key):
            self.info_label.setText(
                f"# Info: Now press '{trigger_key}' key to get\n {cps} clicks of '{key_to_click}' key."
            )
        else:
            self.info_label.setText(
                f"# Info: Now press {trigger_key} key to get\n {cps} clicks of '{key_to_click}' key."
            )

        # Check if mouse or keyboard key (Keyboard key needs to be stripped)
        if not self.is_mouse_key(trigger_key):
            trigger_key = str(trigger_key).strip("'")

        # Stop any existing thread properly
        if self.clicking_thread and self.clicking_thread.isRunning():
            self.clicking_thread.stop()
            self.clicking_thread.wait()
            self.clicking_thread = None

        # Create and start the ClickingThread
        self.clicking_thread = ClickBooster(
            key_to_click, hold_or_toggle, cps, stop_value, trigger_key
        )
        self.clicking_thread.update_clicks.connect(self.handle_updated_clicks)
        self.clicking_thread.update_info.connect(self.handle_updated_info)
        self.clicking_thread.stopped.connect(self.on_booster_stopped)
        self.clicking_thread.target_reached.connect(self.on_target_reached)
        self.clicking_thread.start()
        
        # Disable start button and enable stop button
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    @pyqtSlot()
    def on_target_reached(self):
        # Stop the thread when target is reached
        if self.clicking_thread:
            self.clicking_thread.stop()
            self.info_label.setText(
                f"# Info: Reached target of {self.clicking_thread.stop_at} clicks."
            )

    @pyqtSlot(int)
    def handle_updated_clicks(self, clicks):
        self.clicks_label.setText(f"# Clicks: {str(clicks)}")

    @pyqtSlot(str)
    def handle_updated_info(self, info):
        self.info_label.setText(info)

    @pyqtSlot()
    def on_booster_stopped(self):
        self.clicks_label.setText("# Clicks: 0")
        self.info_label.setText(
            "# Info: AcpsBooster is not boosting\n your cps currently, click start!!"
        )
        self.clicking_thread = None
        
        # Enable start button and disable stop button
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    @pyqtSlot()
    def stop_button_clicked(self):
        if self.clicking_thread and self.clicking_thread.isRunning():
            self.clicking_thread.stop()
        else:
            self.clicks_label.setText("# Clicks: 0")
            self.info_label.setText(
                "# Info: AcpsBooster is not boosting\n your cps currently, click start!!"
            )
            self.clicking_thread = None
            
        # Enable start button and disable stop button
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    AppWindow = QtAppWindow()
    AppWindow.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()