# main.py
import sys
from PyQt6.QtWidgets import QApplication, QStyleFactory
from gui import RPGAdventureGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    window = RPGAdventureGUI()
    window.show()
    
    sys.exit(app.exec())
