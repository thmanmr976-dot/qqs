"""A small supervised native-app example, not a complete desktop shell."""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLabel
app=QApplication(sys.argv)
window=QLabel('qqs custom launcher example\nThis window belongs to the selected shell process group.')
window.setWindowTitle('qqs custom launcher example');window.setMargin(24);window.show()
QTimer.singleShot(100,lambda:print('DEMO_READY',flush=True))
sys.exit(app.exec())
