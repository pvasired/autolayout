import sys
import argparse
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit, QFileDialog, QMessageBox, QComboBox, QGridLayout, QToolTip, QDialog, QSizePolicy, QProgressBar
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QEvent
from gdswriter import GDSDesign  # Import the GDSDesign class
from gdswriter import TEXT_SPACING_FACTOR as GDS_TEXT_SPACING_FACTOR
from copy import deepcopy
import math
import numpy as np
import random
import os
import uuid
import logging
from datetime import datetime
from shapely.geometry import Polygon, Point, box
from matplotlib.figure import Figure
from matplotlib.colors import rgb2hex
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.patches as patches
import matplotlib
matplotlib.use('Qt5Agg')

AXIS_BUFFER = 5
TEXT_SPACING_FACTOR = 0.55
TEXT_HEIGHT_FACTOR = 0.7
TEMP_CELL_NAME = "SIZE CHECK TEMP"
TILDE_KEY = 96
COLOR_SEQUENCE = [
    "#FFCCCC",  # Light red
    "#CCFFCC",  # Light green
    "#CCCCFF",  # Light blue
    "#FFFFCC",  # Light yellow
    "#FFCCFF",  # Light pink
    "#FFD1B3",  # Light orange
    "#E6CCFF",  # Light purple
    "#CCFFFF",  # Light cyan
    "#FFCCF2",  # Light magenta
    "#D9FFB3",  # Light lime
    "#CCFFFF",  # Light teal
    "#E6D8CC",  # Light brown
    "#FFDAB3",  # Light coral
    "#CCCCE6",  # Light navy
    "#E6E6CC",  # Light olive
    "#FFB3B3",  # Light maroon
    "#CCFFFF",  # Light aqua
    "#FFF5CC",  # Light gold
    "#FFD1CC",  # Light salmon
    "#E6CCFF"   # Light violet
]
BASE_COLORS = {
    "#FFCCCC": "#FF6666",  # Light red -> Red
    "#CCFFCC": "#66FF66",  # Light green -> Green
    "#CCCCFF": "#6666FF",  # Light blue -> Blue
    "#FFFFCC": "#FFFF66",  # Light yellow -> Yellow
    "#FFCCFF": "#FF66FF",  # Light pink -> Pink
    "#FFD1B3": "#FF9966",  # Light orange -> Orange
    "#E6CCFF": "#B266FF",  # Light purple -> Purple
    "#CCFFFF": "#66FFFF",  # Light cyan -> Cyan
    "#FFCCF2": "#FF66D9",  # Light magenta -> Magenta
    "#D9FFB3": "#99FF66",  # Light lime -> Lime
    "#CCFFFF": "#66FFFF",  # Light teal -> Teal
    "#E6D8CC": "#C9A57A",  # Light brown -> Brown
    "#FFDAB3": "#FF9966",  # Light coral -> Coral
    "#CCCCE6": "#6666B2",  # Light navy -> Navy
    "#E6E6CC": "#CCCC66",  # Light olive -> Olive
    "#FFB3B3": "#FF6666",  # Light maroon -> Maroon
    "#CCFFFF": "#66FFFF",  # Light aqua -> Aqua
    "#FFF5CC": "#FFEB99",  # Light gold -> Gold
    "#FFD1CC": "#FF9980",  # Light salmon -> Salmon
    "#E6CCFF": "#B266FF"   # Light violet -> Violet
}

def setup_logging():
    # Create a logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Generate a timestamp for the log file
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f'logs/log_{timestamp}.log'

    # Configure logging
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Optionally, also log to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(console_handler)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class CycleLineEdit(QLineEdit):
    def __init__(self, comboBox, addButton, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comboBox = comboBox
        self.addButton = addButton
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Tab:
            self.editingFinished.emit()
            
            currentIndex = self.comboBox.currentIndex()
            nextIndex = (currentIndex + 1) % self.comboBox.count()
            self.comboBox.setCurrentIndex(nextIndex)
            return True  # Event handled
        elif event.type() == QEvent.KeyPress and event.key() == TILDE_KEY:
            self.editingFinished.emit()
            
            currentIndex = self.comboBox.currentIndex()
            nextIndex = (currentIndex - 1) % self.comboBox.count()
            self.comboBox.setCurrentIndex(nextIndex)
            return True  # Event handled
        elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_A and event.modifiers() == (Qt.ShiftModifier | Qt.AltModifier):
            self.editingFinished.emit()
            self.addButton.clicked.emit()
            return True  
        return super().eventFilter(obj, event)
    
class EnterLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and (event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return):
            self.editingFinished.emit()
            
            return True  # Event handled
        return super().eventFilter(obj, event)
    
class PushButtonEdit(QLineEdit):
    def __init__(self, addButton, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addButton = addButton
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_A and event.modifiers() == (Qt.ShiftModifier | Qt.AltModifier):
            self.editingFinished.emit()
            self.addButton.clicked.emit()
            return True
        elif event.type() == QEvent.KeyPress and (event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return):
            self.editingFinished.emit()
            
            return True  # Event handled  
        return super().eventFilter(obj, event)

class TooltipComboBox(QComboBox):
    def __init__(self, tooltips=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tooltips = tooltips or {}
        self.tooltip_widget = QLabel("", self)
        self.tooltip_widget.setWindowFlags(Qt.ToolTip)
        self.tooltip_widget.setStyleSheet("background-color: yellow; border: 1px solid black;")
        self.view().viewport().installEventFilter(self)
        self.setMouseTracking(True)

    def setItemTooltips(self, tooltips):
        self.tooltips = tooltips

    def showCustomTooltip(self, text, pos):
        self.tooltip_widget.setText(text)
        self.tooltip_widget.adjustSize()
        self.tooltip_widget.move(pos)
        self.tooltip_widget.show()

    def hideCustomTooltip(self):
        self.tooltip_widget.hide()

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseMove and source is self.view().viewport():
            index = self.view().indexAt(event.pos()).row()
            if index >= 0 and index < len(self.tooltips):
                global_pos = self.mapToGlobal(event.pos())
                self.showCustomTooltip(self.tooltips[index], global_pos)
            else:
                self.hideCustomTooltip()
            return False
        elif event.type() == QEvent.Leave and source is self.view().viewport():
            self.hideCustomTooltip()
            return False
        return super().eventFilter(source, event)

class MyApp(QWidget):
    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose
        self.inputFileName = ""
        self.outputFileName = ""
        self.customTestCellName = ""
        self.logFileName = ""
        self.customFileName = ""
        self.substrateLayer = None
        self.excludedLayers = []
        self.availableSpace = None
        self.allOtherPolygons = None
        self.layerData = []  # To store layer numbers and names
        self.testStructureNames = [
            "MLA Alignment Mark", "Resistance Test", "Trace Test", 
            "Interlayer Via Test", "Electronics Via Test", "Short Test", 
            "Rectangle", "Circle", "Text", "Polygon", "Path", "Escape Routing", "Connect Rows", "Custom Test Structure"
        ]
        self.parameters = {
            "MLA Alignment Mark": ["Layer", "Center", "Outer Rect Width", "Outer Rect Height", "Interior Width", "Interior X Extent", "Interior Y Extent", "Automatic Placement"],
            "Resistance Test": ["Layer", "Center", "Probe Pad Width", "Probe Pad Height", "Probe Pad Spacing", "Plug Width", "Plug Height", "Trace Width", "Trace Spacing", "Switchbacks", "X Extent", "Text Height", "Text", "Add Interlayer Short", "Layer Name Short", "Short Text", "Automatic Placement"],
            "Trace Test": ["Layer", "Center", "Text", "Line Width", "Line Height", "Num Lines", "Line Spacing", "Text Height", "Automatic Placement"],
            "Interlayer Via Test": ["Layer Number 1", "Layer Number 2", "Via Layer", "Center", "Text", "Layer 1 Rectangle Spacing", "Layer 1 Rectangle Width", "Layer 1 Rectangle Height", "Layer 2 Rectangle Width", "Layer 2 Rectangle Height", "Via Width", "Via Height", "Text Height", "Automatic Placement"],
            "Electronics Via Test": ["Layer Number 1", "Layer Number 2", "Via Layer", "Center", "Text", "Layer 1 Rect Width", "Layer 1 Rect Height", "Layer 2 Rect Width", "Layer 2 Rect Height", "Layer 2 Rect Spacing", "Via Width", "Via Height", "Via Spacing", "Text Height", "Automatic Placement"],
            "Short Test": ["Layer", "Center", "Text", "Rect Width", "Trace Width", "Num Lines", "Group Spacing", "Num Groups", "Num Lines Vert", "Text Height", "Automatic Placement"],
            "Rectangle": ["Layer", "Center", "Width", "Height", "Lower Left", "Upper Right", "Rotation"],
            "Circle": ["Layer", "Center", "Diameter"],
            "Text": ["Layer", "Center", "Text", "Height", "Rotation"],
            "Polygon": ["Layer"],
            "Path": ["Layer", "Width"],
            "Escape Routing": ["Layer", "Center", "Copies X", "Copies Y", "Pitch X", "Pitch Y", "Trace Width", "Trace Space", "Pad Diameter", "Orientation", "Escape Extent", "Cable Tie Routing Angle", "Autorouting Angle"],
            "Connect Rows": ["Layer", "Row 1 Start", "Row 1 End", "Row 1 Spacing", "Row 1 Constant", "Row 2 Start", "Row 2 End", "Row 2 Spacing", "Row 2 Constant", "Orientation", "Trace Width", "Escape Extent"],
            "Custom Test Structure": ["Center", "Magnification", "Rotation", "X Reflection", "Array", "Copies X", "Copies Y", "Pitch X", "Pitch Y", "Automatic Placement"]
        }
        self.paramTooltips = {
            "MLA Alignment Mark": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the alignment mark.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the alignment mark in um.",
                "Outer Rect Width": "type:(number) Enter the width of the outer rectangle in um.",
                "Outer Rect Height": "type:(number) Enter the height of the outer rectangle in um.",
                "Interior Width": "type:(number) Enter the width of the interior lines in um.",
                "Interior X Extent": "type:(number) Enter the extent of the interior lines in the x direction in um.",
                "Interior Y Extent": "type:(number) Enter the extent of the interior lines in the y direction in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the alignment mark."
            },
            "Resistance Test": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the resistance test structure.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the resistance test structure in um.",
                "Probe Pad Width": "type:(number) Enter the width of the probe pad in um.",
                "Probe Pad Height": "type:(number) Enter the height of the probe pad in um.",
                "Probe Pad Spacing": "type:(number) Enter the spacing between probe pads in um.",
                "Plug Width": "type:(number) Enter the width of the plug in um.",
                "Plug Height": "type:(number) Enter the height of the plug in um.",
                "Trace Width": "type:(number) Enter the width of the traces in um.",
                "Trace Spacing": "type:(number) Enter the spacing between traces in um.",
                "Switchbacks": "type:(integer) Enter the number of switchbacks.",
                "X Extent": "type:(number) Enter the extent of the structure in the x direction in um.",
                "Text Height": "type:(number) Enter the height of the text in um.",
                "Text": "type:(string) Enter the text to display on the structure.",
                "Add Interlayer Short": "type:(case-ignored string 'True' or 'False') Check to add an interlayer short.",
                "Layer Name Short": "type:(layer number integer or layer name string) Enter the name of the short layer.",
                "Short Text": "type:(string) Enter the text to display for the short.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the resistance test structure."
            },
            "Trace Test": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the trace test structure.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the trace test structure in um.",
                "Text": "type:(string) Enter the text to display on the structure.",
                "Line Width": "type:(number) Enter the width of the lines in um.",
                "Line Height": "type:(number) Enter the height of the lines in um.",
                "Num Lines": "type:(integer) Enter the number of lines.",
                "Line Spacing": "type:(number) Enter the spacing between lines in um.",
                "Text Height": "type:(number) Enter the height of the text in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the trace test structure."
            },
            "Interlayer Via Test": {
                "Layer Number 1": "type:(layer number integer or layer name string) Enter the first layer for the interlayer via test structure.",
                "Layer Number 2": "type:(layer number integer or layer name string) Enter the second layer for the interlayer via test structure.",
                "Via Layer": "type:(layer number integer or layer name string) Enter the via layer for the interlayer via test structure.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the interlayer via test structure in um.",
                "Text": "type(string) Enter the text to display on the structure.",
                "Layer 1 Rectangle Spacing": "type:(number) Enter the spacing between rectangles on layer 1 in um.",
                "Layer 1 Rectangle Width": "type:(number) Enter the width of the rectangles on layer 1 in um.",
                "Layer 1 Rectangle Height": "type:(number) Enter the height of the rectangles on layer 1 in um.",
                "Layer 2 Rectangle Width": "type:(number) Enter the width of the rectangles on layer 2 in um.",
                "Layer 2 Rectangle Height": "type:(number) Enter the height of the rectangles on layer 2 in um.",
                "Via Width": "type:(number) Enter the width of the vias in um.",
                "Via Height": "type:(number) Enter the height of the vias in um.",
                "Text Height": "type:(number) Enter the height of the text in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the interlayer via test structure."
            },
            "Electronics Via Test": {
                "Layer Number 1": "type:(layer number integer or layer name string) Enter the first layer for the electronics via test structure.",
                "Layer Number 2": "type:(layer number integer or layer name string) Enter the second layer for the electronics via test structure.",
                "Via Layer": "type:(layer number integer or layer name string) Enter the via layer for the electronics via test structure.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the electronics via test structure in um.",
                "Text": "type:(string) Enter the text to display on the structure.",
                "Layer 1 Rect Width": "type:(number) Enter the width of the rectangles on layer 1 in um.",
                "Layer 1 Rect Height": "type:(number) Enter the height of the rectangles on layer 1 in um.",
                "Layer 2 Rect Width": "type:(number) Enter the width of the rectangles on layer 2 in um.",
                "Layer 2 Rect Height": "type:(number) Enter the height of the rectangles on layer 2 in um.",
                "Layer 2 Rect Spacing": "type:(number) Enter the spacing between rectangles on layer 2 in um.",
                "Via Width": "type:(number) Enter the width of the vias in um.",
                "Via Height": "type:(number) Enter the height of the vias in um.",
                "Via Spacing": "type:(number) Enter the spacing between vias and edge of rectangles in layer 2 in um.",
                "Text Height": "type:(number) Enter the height of the text in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the electronics via test structure."
            },
            "Short Test": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the short test structure.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the short test structure in um.",
                "Text": "type:(string) Enter the text to display on the structure.",
                "Rect Width": "type:(number) Enter the width of the rectangles in um.",
                "Trace Width": "type:(number) Enter the width of the traces in um.",
                "Num Lines": "type:(integer) Enter the number of lines.",
                "Group Spacing": "type:(number) Enter the spacing between groups in um.",
                "Num Groups": "type:(integer) Enter the number of groups.",
                "Num Lines Vert": "type:(integer) Enter the number of lines in the vertical direction.",
                "Text Height": "type:(number) Enter the height of the text in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the short test structure."
            },
            "Rectangle": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the rectangle.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the rectangle in um.",
                "Width": "type:(number) Enter the width of the rectangle in um.",
                "Height": "type:(number) Enter the height of the rectangle in um.",
                "Lower Left": "type:(comma-separated tuple x,y) Enter the lower left (x, y) coordinate of the rectangle in um.",
                "Upper Right": "type:(comma-separated tuple x,y) Enter the upper right (x, y) coordinate of the rectangle in um.",
                "Rotation": "type:(number) Enter the rotation angle of the rectangle in degrees."
            },
            "Circle": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the circle.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the circle in um.",
                "Diameter": "type:(number) Enter the diameter of the circle in um."
            },
            "Text": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the text.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the text in um.",
                "Text": "type:(string) Enter the text to display.",
                "Height": "type:(number) Enter the height of the text in um.",
                "Rotation": "type:(number) Enter the rotation angle of the text in degrees."
            },
            "Polygon": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the polygon."
            },
            "Path": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the path.",
                "Width": "type(number) Enter the width of the path in um."
            },
            "Escape Routing": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the escape routing.",
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the escape routing in um.",
                "Copies X": "type:(integer) Enter the number of copies in the x direction.",
                "Copies Y": "type:(integer) Enter the number of copies in the y direction.",
                "Pitch X": "type:(number) Enter the center-to-center pitch between copies in the x direction in um.",
                "Pitch Y": "type:(number) Enter the center-to-center pitch between copies in the y direction in um.",
                "Trace Width": "type:(number) Enter the width of the traces in um.",
                "Trace Space": "type:(number) Enter the spacing between traces in um.",
                "Pad Diameter": "type:(number) Enter the diameter of the pads in um.",
                "Orientation": "type:(comma-separated tuple #sides,direction. Examples of valid orientations include '1,-y', '2,x', '3,+x', and '4'.) Enter the orientation of the escape routing.",
                "Escape Extent": "type:(number) Enter the extent of the escape routing in um.",
                "Cable Tie Routing Angle": "type:(either 45 or 90) Enter the angle of the cable tie routing in degrees",
                "Autorouting Angle": "type:(either 45 or 90) Enter the angle for autorouting in degrees ."
            },
            "Connect Rows": {
                "Layer": "type:(layer number integer or layer name string) Enter the layer for the connect rows.",
                "Row 1 Start": "type:(number) Enter the start position of the first row in um.",
                "Row 1 End": "type:(number) Enter the end position of the first row in um.",
                "Row 1 Spacing": "type:(number) Enter the spacing between elements in the first row in um.",
                "Row 1 Constant": "type:(number) Enter the constant value for the first row in um.",
                "Row 2 Start": "type:(number) Enter the start position of the second row in um.",
                "Row 2 End": "type:(number) Enter the end position of the second row in um.",
                "Row 2 Spacing": "type:(number) Enter the spacing between elements in the second row in um.",
                "Row 2 Constant": "type:(number) Enter the constant value for the second row in um.",
                "Orientation": "type:(direction string '+x', '-x', '+y', or '-y') Enter the orientation of the connect rows.",
                "Trace Width": "type:(number) Enter the width of the traces in um.",
                "Escape Extent": "type:(number) Enter the extent of the escape segment in um.",
            },
            "Custom Test Structure": {
                "Center": "type:(comma-separated tuple x,y) Enter the center (x, y) coordinate of the custom test structure in um.",
                "Magnification": "type:(number) Enter the magnification factor of the custom test structure.",
                "Rotation": "type:(number) Enter the rotation angle of the custom test structure in degrees.",
                "X Reflection": "type:(case-ignored string 'True' or 'False') Check to reflect the structure in the x direction.",
                "Array": "type:(case-ignored string 'True' or 'False') Check to create an array of the structure.",
                "Copies X": "type:(integer) Enter the number of copies in the x direction.",
                "Copies Y": "type:(integer) Enter the number of copies in the y direction.",
                "Pitch X": "type:(number) Enter the center-to-center pitch between copies in the x direction in um.",
                "Pitch Y": "type:(number) Enter the center-to-center pitch between copies in the y direction in um.",
                "Automatic Placement": "type:(case-ignored string 'True' or 'False') Check to automatically place the custom test structure."
            }
        }
        self.defaultParams = {
            "MLA Alignment Mark": {
                "Layer": '',
                "Center": '',
                "Outer Rect Width": 500,
                "Outer Rect Height": 20,
                "Interior Width": 5,
                "Interior X Extent": 50,
                "Interior Y Extent": 50,
                "Automatic Placement": False
            },
            "Resistance Test": {
                "Layer": '',
                "Center": '',
                "Probe Pad Width": 1000,
                "Probe Pad Height": 1000,
                "Probe Pad Spacing": 3000,
                "Plug Width": 200,
                "Plug Height": 200,
                "Trace Width": 5,
                "Trace Spacing": 50,
                "Switchbacks": 18,
                "X Extent": 100,
                "Text Height": 100,
                "Text": '',
                "Add Interlayer Short": False,
                "Layer Name Short": '',
                "Short Text": '',
                "Automatic Placement": False
            },
            "Trace Test": {
                "Layer": '',
                "Center": '',
                "Text": '',
                "Line Width": 800,
                "Line Height": 80,
                "Num Lines": 4,
                "Line Spacing": 80,
                "Text Height": 100,
                "Automatic Placement": False
            },
            "Interlayer Via Test": {
                "Layer Number 1": '',
                "Layer Number 2": '',
                "Via Layer": '',
                "Center": '',
                "Text": '',
                "Layer 1 Rectangle Spacing": 150,
                "Layer 1 Rectangle Width": 700,
                "Layer 1 Rectangle Height": 250,
                "Layer 2 Rectangle Width": 600,
                "Layer 2 Rectangle Height": 550,
                "Via Width": 7,
                "Via Height": 7,
                "Text Height": 100,
                "Automatic Placement": False
            },
            "Electronics Via Test": {
                "Layer Number 1": '',
                "Layer Number 2": '',
                "Via Layer": '',
                "Center": '',
                "Text": '',
                "Layer 1 Rect Width": 1550,
                "Layer 1 Rect Height": 700,
                "Layer 2 Rect Width": 600,
                "Layer 2 Rect Height": 600,
                "Layer 2 Rect Spacing": 250,
                "Via Width": 7,
                "Via Height": 7,
                "Via Spacing": 10,
                "Text Height": 100,
                "Automatic Placement": False
            },
            "Short Test": {
                "Layer": '',
                "Center": '',
                "Text": '',
                "Rect Width": 1300,
                "Trace Width": 5,
                "Num Lines": 5,
                "Group Spacing": 130,
                "Num Groups": 6,
                "Num Lines Vert": 100,
                "Text Height": 100,
                "Automatic Placement": False
            },
            "Rectangle": {
                "Layer": '',
                "Center": '',
                "Width": '',
                "Height": '',
                "Lower Left": '',
                "Upper Right": '',
                "Rotation": 0
            },
            "Circle": {
                "Layer": '',
                "Center": '',
                "Diameter": ''
            },
            "Text": {
                "Layer": '',
                "Center": '',
                "Text": '',
                "Height": 100,
                "Rotation": 0
            },
            "Polygon": {
                "Layer": ''
            },
            "Path": {
                "Layer": '',
                "Width": ''
            },
            "Escape Routing": {
                "Layer": '',
                "Center": '',
                "Copies X": '',
                "Copies Y": '',
                "Pitch X": '',
                "Pitch Y": '',
                "Trace Width": '',
                "Trace Space": '',
                "Pad Diameter": '',
                "Orientation": '',
                "Escape Extent": 100,
                "Cable Tie Routing Angle": 45,
                "Autorouting Angle": 45
            },
            "Connect Rows": {
                "Layer": '',
                "Row 1 Start": '',
                "Row 1 End": '',
                "Row 1 Spacing": '',
                "Row 1 Constant": '',
                "Row 2 Start": '',
                "Row 2 End": '',
                "Row 2 Spacing": '',
                "Row 2 Constant": '',
                "Orientation": '',
                "Trace Width": '',
                "Escape Extent": 100,
            },
            "Custom Test Structure": {
                "Center": '',
                "Magnification": 1,
                "Rotation": 0,
                "X Reflection": False,
                "Array": False,
                "Copies X": 1,
                "Copies Y": 1,
                "Pitch X": 0,
                "Pitch Y": 0,
                "Automatic Placement": False
            }
        }
        self.testStructures = []  # Initialize testStructures here
        self.gds_design = None  # To store the GDSDesign instance
        self.custom_design = None  # To store the custom design instance
        self.polygon_points = []  # To store polygon points
        self.path_points = [] # To store path points
        self.undoStack = []  # Initialize undo stack
        self.redoStack = []  # Initialize redo stack
        self.escapeDicts = {}  # To store escape routing dictionaries
        self.routing = []
        self.routingMode = False
        self.flareMode = False
        self.pitch_x = None
        self.pitch_y = None
        self.copies_x = None
        self.copies_y = None
        self.center_escape = None
        self.initUI()

    def initUI(self):
        # Set a global stylesheet for the entire application
        font_size = 28  # Adjust the font size as needed
        self.setStyleSheet(f"""
            QToolTip {{
                background-color: yellow; 
                color: black; 
                border: 1px solid black; 
            }}
            QWidget {{
                font-size: {font_size}px;
            }}
            QLineEdit {{
                font-size: {font_size}px;
            }}
            QPushButton {{
                font-size: {font_size}px;
            }}
            QLabel {{
                font-size: {font_size}px;
            }}
            QComboBox {{
                font-size: {font_size}px;
            }}
            QCheckBox {{
                font-size: {font_size}px;
            }}
            QToolTip {{
                font-size: {font_size}px;
            }}
        """)
        # Main Layout
        mainLayout = QHBoxLayout()  # Changed to QHBoxLayout

        # Left Layout (contains all the menus)
        leftLayout = QVBoxLayout()

        # Write to GDS button
        self.writeButton = QPushButton('Write to GDS')
        self.writeButton.clicked.connect(self.writeToGDS)
        self.writeButton.setToolTip('Click to write the current design to a GDS file.')
        self.writeButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # File selection layout
        fileLayout = QHBoxLayout()
        fileMenuLabel = QLabel('File Menu')
        leftLayout.addWidget(fileMenuLabel)
        self.initFileButton = QPushButton('Select Input File')
        self.initFileButton.clicked.connect(self.selectInputFile)
        self.initFileButton.setToolTip('Click to select the input GDS file.')
        self.initFileButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.blankFileButton = QPushButton('Create Blank Design')
        self.blankFileButton.clicked.connect(self.createBlankDesign)
        self.blankFileButton.setToolTip('Click to create a blank design.')
        self.blankFileButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.outFileField = PushButtonEdit(self.writeButton)
        self.outFileField.setPlaceholderText('Output File')
        self.outFileField.editingFinished.connect(self.validateOutputFileName)
        self.outFileField.setToolTip("type:(filename or path ending with '.gds') Enter the name of the output GDS file.")
        self.outFileField.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        fileLayout.addWidget(self.initFileButton)
        fileLayout.addWidget(self.blankFileButton)
        fileLayout.addWidget(self.outFileField)
        leftLayout.addLayout(fileLayout)

        # Undo and Redo buttons
        undoRedoLayout = QHBoxLayout()
        self.undoButton = QPushButton('Undo')
        self.undoButton.clicked.connect(self.undo)
        self.undoButton.setToolTip('Undo the last action.')
        self.undoButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.redoButton = QPushButton('Redo')
        self.redoButton.clicked.connect(self.redo)
        self.redoButton.setToolTip('Redo the previously undone action.')
        self.redoButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        undoRedoLayout.addWidget(self.undoButton)
        undoRedoLayout.addWidget(self.redoButton)
        leftLayout.addLayout(undoRedoLayout)

        # Add cell dropdown and Matplotlib Button
        plotLayout = QHBoxLayout()
        plotMenuLabel = QLabel('Interactive Plotting Menu')
        leftLayout.addWidget(plotMenuLabel)
        self.cellComboBox = QComboBox()
        self.cellComboBox.setToolTip('Select a cell from the loaded GDS file.')
        self.cellComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        plotLayout.addWidget(self.cellComboBox)

        self.plotLayersComboBox = QComboBox()
        self.plotLayersComboBox.setToolTip('Select a layer from the list to plot for the cell.')
        self.plotLayersComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        plotLayout.addWidget(self.plotLayersComboBox)

        self.matplotlibButton = QPushButton('Routing Tool')
        self.matplotlibButton.clicked.connect(self.showMatplotlibWindow)
        self.matplotlibButton.setToolTip('Click to show an interactive plot of the selected cell for routing.')
        self.matplotlibButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        plotLayout.addWidget(self.matplotlibButton)

        leftLayout.addLayout(plotLayout)

        # Die Placement Utility Button
        self.diePlacementButton = QPushButton('Open Die Placement Menu')
        self.diePlacementButton.clicked.connect(self.showDiePlacementUtility)
        self.diePlacementButton.setToolTip('Click to open the Die Placement menu.')
        self.diePlacementButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        leftLayout.addWidget(self.diePlacementButton)

        # Test Structures layout
        testLayout = QVBoxLayout()
        testLabel = QLabel('Add Components (NOTE: all spatial units are in microns)')
        testLayout.addWidget(testLabel)

        gridLayout = QGridLayout()
        row = 0
        for name in self.testStructureNames:
            testCheckBox = QCheckBox(name)
            testCheckBox.stateChanged.connect(self.createCheckStateHandler)
            testCheckBox.setToolTip(f'Check to include {name} in the design.')
            testCheckBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cellBoxLabel = QLabel('Cell Name')
            cellBoxLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            testCellComboBox = QComboBox()
            testCellComboBox.setPlaceholderText(f'Select Cell to Place {name}')
            testCellComboBox.setToolTip(f'Select the cell on which to place {name}.')
            testCellComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            paramLabel = QLabel('Parameters')
            paramLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            paramComboBox = TooltipComboBox()
            paramComboBox.addItems(self.parameters[name])
            paramComboBox.setItemTooltips([self.paramTooltips[name].get(param, '') for param in self.parameters[name]])
            paramComboBox.currentTextChanged.connect(self.createParamChangeHandler)
            paramComboBox.setToolTip(f'Select parameters for {name}.') 
            paramComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            addButton = QPushButton("Add to Design")
            addButton.clicked.connect(self.createAddToDesignHandler)
            addButton.setToolTip(f'Click to add {name} to the design.')
            addButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            paramValueEdit = CycleLineEdit(paramComboBox, addButton)  # Use CycleLineEdit instead of QLineEdit
            paramName = paramComboBox.currentText()
            if paramName in self.defaultParams[name]:
                paramValueEdit.setText(str(self.defaultParams[name][paramName]))
            paramValueEdit.editingFinished.connect(self.createParamStoreHandler)
            paramValueEdit.setToolTip(f'Enter value for the selected parameter of {name}.')
            paramValueEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            gridLayout.addWidget(testCheckBox, row, 0)
            gridLayout.addWidget(cellBoxLabel, row, 1)
            gridLayout.addWidget(testCellComboBox, row, 2)
            gridLayout.addWidget(paramLabel, row, 3)
            gridLayout.addWidget(paramComboBox, row, 4)
            gridLayout.addWidget(paramValueEdit, row, 5)
            gridLayout.addWidget(addButton, row, 6)

            if name == "Polygon":
                self.polygonButton = QPushButton('Select Polygon Points File')
                self.polygonButton.clicked.connect(self.selectPolygonPointsFile)
                self.polygonButton.setToolTip('Click to select a file containing polygon points.')
                self.polygonButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.polygonButton, row, 7)
            
            if name == "Path":
                self.pathButton = QPushButton('Select Path Points File')
                self.pathButton.clicked.connect(self.selectPathPointsFile)
                self.pathButton.setToolTip('Click to select a file containing path points.')
                self.pathButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.pathButton, row, 7)
            
            if name == "Escape Routing":
                self.escapeButton = QPushButton('Select Escape Routing File')
                self.escapeButton.clicked.connect(self.selectEscapeRoutingFile)
                self.escapeButton.setToolTip('Click to select a file containing pad coordinates for escape routing.')
                self.escapeButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.escapeButton, row, 7)

            if name == "Custom Test Structure":
                self.customTestCellComboBox = QComboBox()
                self.customTestCellComboBox.setPlaceholderText("Select Custom Test Structure Cell")
                self.customTestCellComboBox.activated.connect(self.handleCustomTestCellName)
                self.customTestCellComboBox.setToolTip('Select a custom test structure cell.')
                self.customTestCellComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.customTestCellComboBox, row, 7)
                
                # New button to select other .gds file
                self.selectOtherGDSButton = QPushButton('Select Other .gds File')
                self.selectOtherGDSButton.clicked.connect(self.selectOtherGDSFile)
                self.selectOtherGDSButton.setToolTip('Click to select another .gds file.')
                self.selectOtherGDSButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.selectOtherGDSButton, row, 8)

                # Reset file button
                self.resetOtherGDSButton = QPushButton('Reset Other .gds File')
                self.resetOtherGDSButton.clicked.connect(self.resetOtherGDSFile)
                self.resetOtherGDSButton.setToolTip('Click to reset the other .gds file.')
                self.resetOtherGDSButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                gridLayout.addWidget(self.resetOtherGDSButton, row, 9)
                self.resetOtherGDSButton.hide()

            row += 1

            defaultParams = deepcopy(self.defaultParams[name])
            self.testStructures.append((testCheckBox, testCellComboBox, paramComboBox, paramValueEdit, defaultParams, addButton))

        testLayout.addLayout(gridLayout)
        leftLayout.addLayout(testLayout)

        # Layers layout
        layersHBoxLayout = QHBoxLayout()  # Change from QVBoxLayout to QHBoxLayout
        layerAndCellMenuLabel = QLabel('Layers and Cells Menu')
        leftLayout.addWidget(layerAndCellMenuLabel)
        layersLabel = QLabel('Layers:')
        layersLabel.setToolTip('Layers available in the design.')
        layersLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(layersLabel)

        self.layersComboBox = QComboBox()
        self.layersComboBox.setToolTip('Select a layer from the list.')
        self.layersComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.layersComboBox)

        self.selectSubstrateLayerButton = QPushButton('Select Substrate Layer')
        self.selectSubstrateLayerButton.clicked.connect(self.selectSubstrateLayer)
        self.selectSubstrateLayerButton.setToolTip('Click to select the substrate layer from the dropdown menu.')
        self.selectSubstrateLayerButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.selectSubstrateLayerButton)

        # New Excluded Layers input field
        self.excludedLayersEdit = QLineEdit()
        self.excludedLayersEdit.setPlaceholderText('Excluded Layers')
        self.excludedLayersEdit.editingFinished.connect(self.updateExcludedLayers)
        self.excludedLayersEdit.setToolTip('type:(comma-separated list of layer number integers or layer name strings) Enter comma-separated list of layer numbers or names to exclude from automatic placement search.')
        self.excludedLayersEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.excludedLayersEdit)

        # New Calculate Layer Area button and Layer Area text box
        self.calculateLayerAreaButton = QPushButton('Calculate Layer Area')
        self.calculateLayerAreaButton.clicked.connect(self.calculateLayerArea)
        self.calculateLayerAreaButton.setToolTip('Click to calculate the area for the selected layer.')
        self.calculateLayerAreaButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.calculateLayerAreaButton)

        self.layerCellComboBox = QComboBox()
        self.layerCellComboBox.setPlaceholderText("Select cell on which to calculate area")
        self.layerCellComboBox.setToolTip("Select cell on which to calculate area (optional, will default to the first top cell in design if not provided)")
        self.layerCellComboBox.currentTextChanged.connect(self.calculateLayerArea)
        self.layerCellComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.layerCellComboBox)

        self.layerAreaEdit = QLineEdit()
        self.layerAreaEdit.setPlaceholderText('Layer Area (mm^2)')
        self.layerAreaEdit.setReadOnly(True)
        self.layerAreaEdit.setToolTip('Displays the calculated area of the selected layer in mm^2.')
        self.layerAreaEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layersHBoxLayout.addWidget(self.layerAreaEdit)

        # Define Layer layout
        defineLayerHBoxLayout = QHBoxLayout()
        defineLayerButton = QPushButton('Define New Layer')
        defineLayerButton.clicked.connect(self.defineNewLayer)
        defineLayerButton.setToolTip('Click to define a new layer.')
        defineLayerButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.newLayerNumberEdit = PushButtonEdit(defineLayerButton)
        self.newLayerNumberEdit.setPlaceholderText('Layer Number')
        self.newLayerNumberEdit.setToolTip('type:(integer) Enter the number of the new layer.')
        self.newLayerNumberEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.newLayerNameEdit = PushButtonEdit(defineLayerButton)
        self.newLayerNameEdit.setPlaceholderText('Layer Name')
        self.newLayerNameEdit.setToolTip('type:(string) Enter the name of the new layer.')
        self.newLayerNameEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        defineLayerHBoxLayout.addWidget(self.newLayerNumberEdit)
        defineLayerHBoxLayout.addWidget(self.newLayerNameEdit)
        defineLayerHBoxLayout.addWidget(defineLayerButton)

        # Layers and Define Layer layout
        layersVBoxLayout = QVBoxLayout()
        layersVBoxLayout.addLayout(layersHBoxLayout)
        layersVBoxLayout.addLayout(defineLayerHBoxLayout)

        leftLayout.addLayout(layersVBoxLayout)

        mainLayout.addLayout(leftLayout)  # Add the left layout to the main layout

        # Plot Area Layout
        plotAreaLayout = QVBoxLayout()
        self.fig = Figure(figsize=(20, 12))  # Adjust the figsize to make the plot bigger
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Connect the click event to the handler
        self.canvas.mpl_connect('button_press_event', self.on_click)
        plotAreaLayout.addWidget(self.canvas)

        # Add the navigation toolbar to the layout
        self.toolbar = NavigationToolbar(self.canvas, self)
        plotAreaLayout.addWidget(self.toolbar)

        # Add Routing Mode and Flare Mode buttons
        modeButtonLayout = QHBoxLayout()
        self.routingModeButton = QPushButton('Routing Mode')
        self.routingModeButton.clicked.connect(self.setRoutingMode)
        self.routingModeButton.setToolTip('Click to enter routing mode.')
        self.routingModeButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.flareModeButton = QPushButton('Flare Mode')
        self.flareModeButton.clicked.connect(self.setFlareMode)
        self.flareModeButton.setToolTip('Click to enter flare (fan out) mode.')
        self.flareModeButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        modeButtonLayout.addWidget(self.routingModeButton)
        modeButtonLayout.addWidget(self.flareModeButton)
        plotAreaLayout.addLayout(modeButtonLayout)

        # Add text fields for Flare Mode
        flareModeLayout = QHBoxLayout()
        self.endingTraceWidthEdit = QLineEdit()
        self.endingTraceWidthEdit.setPlaceholderText('Ending Trace Width')
        self.endingTraceWidthEdit.setToolTip('type:(number) Enter the ending trace width of the fan out in um.')
        self.endingTraceWidthEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.endingTraceSpaceEdit = QLineEdit()
        self.endingTraceSpaceEdit.setPlaceholderText('Ending Trace Space')
        self.endingTraceSpaceEdit.setToolTip('type:(number) Enter the ending trace space of the fan out in um.')
        self.endingTraceSpaceEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.flareRoutingAngleEdit = QLineEdit()
        self.flareRoutingAngleEdit.setText('90')
        self.flareRoutingAngleEdit.setToolTip('type:(45 or 90) Enter the flare routing angle in degrees: 90 degrees is handled with smooth turns.')
        self.flareRoutingAngleEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.flareEscapeExtentEdit = QLineEdit()
        self.flareEscapeExtentEdit.setText('100')
        self.flareEscapeExtentEdit.setToolTip('type:(number) Enter the extent of the escape in um: increasing this can help avoid collisions.')
        self.flareEscapeExtentEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.flareFinalLengthEdit = QLineEdit()
        self.flareFinalLengthEdit.setText('100')
        self.flareFinalLengthEdit.setToolTip('type:(number) Enter the final length of the traces in the flare in um.')
        self.flareFinalLengthEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.flareAutoroutingAngleEdit = QLineEdit()
        self.flareAutoroutingAngleEdit.setText('45')
        self.flareAutoroutingAngleEdit.setToolTip('type:(45 or 90) Enter the angle for autorouting in degrees.')
        self.flareAutoroutingAngleEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        flareModeLayout.addWidget(self.endingTraceWidthEdit)
        flareModeLayout.addWidget(self.endingTraceSpaceEdit)
        flareModeLayout.addWidget(self.flareRoutingAngleEdit)
        flareModeLayout.addWidget(self.flareEscapeExtentEdit)
        flareModeLayout.addWidget(self.flareFinalLengthEdit)
        flareModeLayout.addWidget(self.flareAutoroutingAngleEdit)
        plotAreaLayout.addLayout(flareModeLayout)

        self.endingTraceWidthEdit.hide()
        self.endingTraceSpaceEdit.hide()
        self.flareRoutingAngleEdit.hide()
        self.flareEscapeExtentEdit.hide()
        self.flareFinalLengthEdit.hide()
        self.flareAutoroutingAngleEdit.hide()

        mainLayout.addLayout(plotAreaLayout)  # Add the plot area layout to the main layout

        # Define Cell layout
        defineCellHBoxLayout = QHBoxLayout()
        defineCellButton = QPushButton('Define New Cell')
        defineCellButton.clicked.connect(self.defineNewCell)
        defineCellButton.setToolTip('Click to define a new cell.')
        defineCellButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.newCellNameEdit = PushButtonEdit(defineCellButton)
        self.newCellNameEdit.setPlaceholderText('Cell Name')
        self.newCellNameEdit.setToolTip('type:(string) Enter the name of the new cell.')
        self.newCellNameEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        defineCellHBoxLayout.addWidget(self.newCellNameEdit)
        defineCellHBoxLayout.addWidget(defineCellButton)
        leftLayout.addLayout(defineCellHBoxLayout)

        leftLayout.addWidget(self.writeButton)  # Add the write button to the left layout

        self.placementCellComboBox = QComboBox()
        self.placementCellComboBox.setPlaceholderText('Select Cell to Place Dies')
        self.placementCellComboBox.setToolTip('Select the cell from the GDS file to place dies.')
        self.placementCellComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.dicingStreetsLayerComboBox = QComboBox()
        self.dicingStreetsLayerComboBox.setPlaceholderText('Select Dicing Streets Layer')
        self.dicingStreetsLayerComboBox.setToolTip('Select the layer for the dicing streets.')
        self.dicingStreetsLayerComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.dieTextLayerComboBox = QComboBox()
        self.dieTextLayerComboBox.setPlaceholderText('Select Die Text Layer')
        self.dieTextLayerComboBox.setToolTip('Select the layer for the die text.')
        self.dieTextLayerComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.subdicingStreetsLayerComboBox = QComboBox()
        self.subdicingStreetsLayerComboBox.setPlaceholderText('Select Subdicing Streets Layer')
        self.subdicingStreetsLayerComboBox.setToolTip('Select the layer for the subdicing streets.')
        self.subdicingStreetsLayerComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.deepSiEtchingLayerComboBox = QComboBox()
        self.deepSiEtchingLayerComboBox.setPlaceholderText('Select Deep Si Etching Layer')
        self.deepSiEtchingLayerComboBox.setToolTip('Select the layer for deep Si etching.')
        self.deepSiEtchingLayerComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setLayout(mainLayout)
        self.setWindowTitle('GDS Automation GUI')
        self.resize(3600, 800)  # Set the initial size of the window
        self.show()

    def resetOtherGDSFile(self):
        logging.info("Resetting other GDS file")
        self.customFileName = None
        self.custom_design = None

        self.updateCellComboBox()
        self.resetOtherGDSButton.hide()

    def updatePlacementLegend(self):
        # Iterate through self.diePlacement and find the colors that are used
        # Associate those colors with the corresponding die labels and notes if they exist
        new_handles = []
        new_labels = []
        for loc in self.diePlacement:
            color = self.diePlacement[loc][1].get_facecolor()
            if color != (0, 0, 0, 0) and color != (0, 0, 0, 1):
                color_already_in_legend = any(
                    [handle.get_facecolor() == color for handle in new_handles]
                )
                
                # If color is not in the legend, add it
                if not color_already_in_legend:
                    die_label = self.diePlacement[loc][0]['dieLabelEdit'].text()
                    die_notes = self.diePlacement[loc][0]['dieNotesEdit'].text()
                    label = f'Label: {die_label}, Notes: {die_notes}'
                    new_patch = patches.Patch(color=color, label=label)
                    new_handles.append(new_patch)
                    new_labels.append(label)

        self.dieAx.legend(new_handles, new_labels, loc='upper right', fontsize=10)
        self.dieCanvas.draw()

    def dieSelectGDSFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.gds'):
                sender = self.sender()
                for rowIndex in self.dieInfo:
                    selectFileButton = self.dieInfo[rowIndex]['selectFileButton']
                    if selectFileButton == sender:
                        break
                # Load the GDS file using GDSDesign
                dieDesign = GDSDesign(filename=fileName)
                sorted_keys = sorted(dieDesign.cells.keys(), key=lambda x: x.lower())
                self.dieInfo[rowIndex]['cellComboBox'].clear()
                self.dieInfo[rowIndex]['cellComboBox'].addItems(sorted_keys)
                logging.info(f"Cell combo box populated with cells: {sorted_keys}")

                # Store the GDSDesign instance
                self.dieInfo[rowIndex]['dieDesign'] = dieDesign
                self.dieInfo[rowIndex]['fileName'] = fileName
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .gds file")
    
    def drawSubstrate(self):
        # Remove the previous wafer patch if it exists
        if hasattr(self, 'wafer_patch'):
            self.wafer_patch.remove()

        # Draw the new wafer patch
        self.wafer_patch = patches.Circle((0, 0), self.waferDiameter / 2, edgecolor='tab:blue', facecolor='none', linewidth=2)
        self.dieAx.add_patch(self.wafer_patch)

        # Set the aspect ratio to be equal
        self.dieAx.set_aspect('equal', 'box')

        # Set the limits of the plot
        self.dieAx.set_xlim(-self.waferDiameter / 2 - AXIS_BUFFER, self.waferDiameter + AXIS_BUFFER)
        self.dieAx.set_ylim(-self.waferDiameter / 2 - AXIS_BUFFER, self.waferDiameter / 2 + AXIS_BUFFER)

        # Increase the size of the tick marks
        self.dieAx.tick_params(axis='both', which='major', labelsize=18, length=10, width=2)
        self.dieAx.grid(True, which='both')

        # Redraw the canvas
        self.dieCanvas.draw()
        logging.info(f"Substrate drawn with diameter {self.waferDiameter} um")

    def onSubstrate4InchChecked(self):
        if self.substrate4InchCheckBox.isChecked():
            self.substrate6InchCheckBox.setChecked(False)

            self.waferDiameter = 100
            self.wafer = Point(0, 0).buffer(self.waferDiameter/2)
            self.drawSubstrate()
            self.createDiePlacement()

            logging.info("4-inch substrate selected")

    def onSubstrate6InchChecked(self):
        if self.substrate6InchCheckBox.isChecked():
            self.substrate4InchCheckBox.setChecked(False)

            self.waferDiameter = 150
            self.wafer = Point(0, 0).buffer(self.waferDiameter/2)
            self.drawSubstrate()
            self.createDiePlacement()

            logging.info("6-inch substrate selected")

    def createDiePlacement(self):
        if self.waferDiameter is None or self.dieWidthEdit.text() == '' or self.dieHeightEdit.text() == '' or self.dicingStreetEdit.text() == '' or self.edgeMarginEdit.text() == '':
            return
        try:
            die_width = float(self.dieWidthEdit.text().strip())
            die_height = float(self.dieHeightEdit.text().strip())
            dicing_street_width = float(self.dicingStreetEdit.text().strip())
            edge_margin = float(self.edgeMarginEdit.text().strip())

            assert die_width > 0, 'Die width must be greater than 0.'
            assert die_height > 0, 'Die height must be greater than 0.'
            assert dicing_street_width >= 0, 'Dicing street width must be greater than or equal to 0.'
            assert edge_margin > 0, 'Edge margin must be greater than 0.'
        except (AssertionError, ValueError, Exception) as e:
            QMessageBox.critical(self, 'Error', str(e), QMessageBox.Ok)
            logging.error(f"Error creating die placement: {e}")
            return
        
        self.dieAx.clear()
        self.drawSubstrate()
        self.diePlacement = {}
        if self.centeredPlacementCheckBox.isChecked():
            starting_y = 0
            while True:
                starting_x = 0
                die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)
                if die.exterior.distance(self.wafer.exterior) < edge_margin:
                    break
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x += die_width + dicing_street_width

                starting_x = -die_width - dicing_street_width
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x -= die_width + dicing_street_width
                
                starting_y += die_height + dicing_street_width

            starting_y = -die_height - dicing_street_width
            while True:
                starting_x = 0
                die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)
                if die.exterior.distance(self.wafer.exterior) < edge_margin:
                    break
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x += die_width + dicing_street_width

                starting_x = -die_width - dicing_street_width
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x -= die_width + dicing_street_width
                
                starting_y -= die_height + dicing_street_width
        else:
            starting_y = die_height/2 + dicing_street_width/2
            while True:
                starting_x = die_width/2 + dicing_street_width/2
                die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)
                if die.exterior.distance(self.wafer.exterior) < edge_margin:
                    break
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x += die_width + dicing_street_width

                starting_x = -die_width/2 - dicing_street_width/2
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x -= die_width + dicing_street_width
                
                starting_y += die_height + dicing_street_width

            starting_y = -die_height/2 - dicing_street_width/2
            while True:
                starting_x = die_width/2 + dicing_street_width/2
                die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)
                if die.exterior.distance(self.wafer.exterior) < edge_margin:
                    break
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x += die_width + dicing_street_width

                starting_x = -die_width/2 - dicing_street_width/2
                while True:
                    die_patch = patches.Rectangle((starting_x-die_width/2, starting_y-die_height/2), die_width, die_height, edgecolor='k', facecolor='none')
                    die = box(starting_x-die_width/2, starting_y-die_height/2, starting_x+die_width/2, starting_y+die_height/2)

                    if die.exterior.distance(self.wafer.exterior) < edge_margin:
                        break

                    # Add the square to the plot
                    self.dieAx.add_patch(die_patch)
                    self.diePlacement[(starting_x, starting_y)] = None, die_patch

                    starting_x -= die_width + dicing_street_width
                
                starting_y -= die_height + dicing_street_width
        self.dieCanvas.draw()
        self.updateDPW()
        self.die_width = die_width
        self.die_height = die_height
        self.dicing_street_width = dicing_street_width
        self.validateDieCells()

        logging.info(f"Die placement created with die width {die_width}, die height {die_height}, dicing street width {dicing_street_width}, and edge margin {edge_margin}")

    def updateDPW(self):
        cnt = 0
        for loc in self.diePlacement:
            if self.diePlacement[loc][1].get_facecolor() == (0, 0, 0, 0) and self.diePlacement[loc][0] is None:
               cnt += 1
        self.dpwTextBox.setText(str(cnt))
        self.dpw = cnt 

        logging.info(f"DPW updated to {cnt}")

    def die_on_click(self, event):
        # Check if the toolbar is in zoom mode
        if self.dieToolbar.mode == '':
            if event.inaxes is not None:
                x, y = event.xdata, event.ydata
                logging.info(f"Click at position: ({x}, {y})")
                # You can process the click coordinates here
                self.die_process_click(x, y)
            else:
                logging.info("Click outside axes bounds")
        else:
            logging.info(f"Toolbar mode is active ({self.dieToolbar.mode}), click not registered")
    
    def die_process_click(self, x, y):
        if len(self.diePlacement.keys()) == 0:
            return
        minDist = np.inf
        closestLoc = None
        for loc in self.diePlacement.keys():
            dist = np.linalg.norm(np.array(loc) - np.array([x, y]))
            if dist < minDist:
                minDist = dist
                closestLoc = loc
        
        logging.info(f"Closest die location: {closestLoc}")
        
        if self.activeRow is not None:
            if self.dieInfo[self.activeRow]['dieDesign'] is not None and self.dieInfo[self.activeRow]['cellComboBox'].currentText() != '':
                original_color = COLOR_SEQUENCE[self.activeRow % len(COLOR_SEQUENCE)]
                active_color = BASE_COLORS.get(original_color)
                if rgb2hex(self.diePlacement[closestLoc][1].get_facecolor()) == active_color.lower():
                    self.diePlacement[closestLoc][1].set_facecolor('none')
                    self.dieCanvas.draw()

                    self.diePlacement[closestLoc] = None, self.diePlacement[closestLoc][1]
                    self.updateDPW()
                    self.updatePlacementLegend()

                    logging.info(f"Die at location {closestLoc} removed")
                else:
                    self.diePlacement[closestLoc][1].set_facecolor(active_color)
                    self.dieCanvas.draw()

                    self.diePlacement[closestLoc] = self.dieInfo[self.activeRow], self.diePlacement[closestLoc][1]
                    self.updateDPW()
                    self.updatePlacementLegend()

                    logging.info(f"Die at location {closestLoc} added")
            else:
                QMessageBox.critical(self, 'Error', 'Please select a GDS file and cell for the die.', QMessageBox.Ok)
                logging.error("Error processing click: GDS file and cell not selected")
                return
        elif self.blacklistMode:
            if self.diePlacement[closestLoc][1].get_facecolor() == (0, 0, 0, 1):
                self.diePlacement[closestLoc][1].set_facecolor('none')
                self.dieCanvas.draw()
                self.diePlacement[closestLoc] = None, self.diePlacement[closestLoc][1]

                self.updateDPW()
                self.updatePlacementLegend()

                logging.info(f"Die at location {closestLoc} removed from blacklist")
            else:
                self.diePlacement[closestLoc][1].set_facecolor('black')
                self.dieCanvas.draw()
                self.diePlacement[closestLoc] = None, self.diePlacement[closestLoc][1]

                self.updateDPW()
                self.updatePlacementLegend()    

                logging.info(f"Die at location {closestLoc} added to blacklist")
        else:
            QMessageBox.critical(self, 'Error', 'Please select a row in the Die Placement Menu or select Blacklist Mode.', QMessageBox.Ok)
            logging.error("Error processing click: No active row or blacklist mode selected")
            return
    
    def autoPlaceDies(self):
        if self.dpw == 0:
            QMessageBox.critical(self, 'Error', 'No spaces to place dies.', QMessageBox.Ok)
            logging.error("Error placing dies: No spaces available")
            return
        
        keys = [key for key, value in self.diePlacement.items() if value[0] is None and value[1].get_facecolor() != (0, 0, 0, 1)]
        if self.shuffleCheckBox.isChecked():
            random.shuffle(keys)
        else:
            keys = sorted(keys, key=lambda x: (x[1], x[0]))

        numDies_tot = 0
        for rowIndex in self.dieInfo:
            if self.dieInfo[rowIndex]['numDiesEdit'].text() == '' or self.dieInfo[rowIndex]['cellComboBox'].currentText() == '':
                continue
            try:
                numDies_tot += int(self.dieInfo[rowIndex]['numDiesEdit'].text().strip())
            except:
                QMessageBox.critical(self, 'Error', 'Number of dies must be an integer.', QMessageBox.Ok)
                logging.error("Error placing dies: Number of dies not an integer")
                return
        logging.info(f"Total number of dies to place: {numDies_tot}")
        if numDies_tot > self.dpw:
            QMessageBox.critical(self, 'Error', 'Not enough spaces to place all dies.', QMessageBox.Ok)
            logging.error("Error placing dies: Not enough spaces available")
            return
        
        cnt = 0
        for rowIndex in self.dieInfo:
            if self.dieInfo[rowIndex]['numDiesEdit'].text() == '' or self.dieInfo[rowIndex]['cellComboBox'].currentText() == '':
                continue
            numDies = int(self.dieInfo[rowIndex]['numDiesEdit'].text().strip())
            original_color = COLOR_SEQUENCE[rowIndex % len(COLOR_SEQUENCE)]
            active_color = BASE_COLORS.get(original_color)
            for i in range(numDies):
                self.diePlacement[keys[cnt]][1].set_facecolor(active_color)
                self.diePlacement[keys[cnt]] = self.dieInfo[rowIndex], self.diePlacement[keys[cnt]][1]
                cnt += 1
            self.dieInfo[rowIndex]['numDiesEdit'].setText('0')
        
        self.dieCanvas.draw()
        self.updateDPW()
        self.updatePlacementLegend()

        logging.info(f"{numDies_tot} dies placed automatically")
        
    # Method to set the active row
    def setActiveRow(self, rowIndex):
        # Reset the color of the previous active row
        if self.activeRow is not None:
            prev_color = COLOR_SEQUENCE[self.activeRow % len(COLOR_SEQUENCE)]
            self.dieInfo[self.activeRow]['rowWidget'].setStyleSheet(f"background-color: {prev_color}; padding: 5px;")

        if self.activeRow == rowIndex:
            self.activeRow = None
            logging.info("Active row unset")
            return
        
        if self.blacklistMode:
            self.setBlacklistMode()
        
        # Set the new active row
        self.activeRow = rowIndex
        original_color = COLOR_SEQUENCE[self.activeRow % len(COLOR_SEQUENCE)]
        active_color = BASE_COLORS.get(original_color)
        self.dieInfo[self.activeRow]['rowWidget'].setStyleSheet(f"background-color: {active_color}; padding: 5px;")

        logging.info(f"Active row set to {self.activeRow}")

    def validateDieCells(self):
        if self.die_width is None or self.die_height is None:
            return
        for rowIndex in self.dieInfo:
            cellComboBox = self.dieInfo[rowIndex]['cellComboBox']
            dieDesign = self.dieInfo[rowIndex]['dieDesign']
            if cellComboBox.currentText() != '':
                cell_name = cellComboBox.currentText()
                cell_width, cell_height, cell_offset = dieDesign.calculate_cell_size(cell_name)
                logging.info(f"Cell {cell_name} dimensions: {cell_width} x {cell_height} um, offset: {cell_offset}")
                if round(cell_width, 3) > self.die_width*1000 or round(cell_height, 3) > self.die_height*1000:
                    # Show a warning box if the cell dimensions exceed the die dimensions
                    QMessageBox.warning(self, 'Warning', f"Cell {cell_name} dimensions exceed the die dimensions.", QMessageBox.Ok)
                    logging.warning(f"Cell {cell_name} dimensions exceed the die dimensions")
                self.dieInfo[rowIndex]['offset'] = cell_offset
                if self.deepSiEtchingLayerComboBox.currentText() != '':
                    deepSiEtchingLayer = self.deepSiEtchingLayerComboBox.currentText().split(':')[1].strip()
                    deepSiEtchMin, deepSiEtchMax = dieDesign.get_minmax_feature_size(cell_name, deepSiEtchingLayer)
                    self.dieInfo[rowIndex]['dieDeepSiEtchingMinFeatureSizeEdit'].setText(f'{round(deepSiEtchMin, 1)}um')
                    self.dieInfo[rowIndex]['dieDeepSiEtchingMaxFeatureSizeEdit'].setText(f'{round(deepSiEtchMax, 1)}um')
                    logging.info(f"Cell {cell_name} deep Si etching feature size: {deepSiEtchMin} - {deepSiEtchMax} um")
        
        logging.info("Die cells validated")

    def placeDiesOnDesign(self):
        if self.gds_design is None:
            QMessageBox.critical(self, 'Error', 'Please load or create a GDS file with the main window.', QMessageBox.Ok)
            logging.error("Error placing dies: No GDS file loaded")
            return
        if self.placementCellComboBox.currentText() == '':
            QMessageBox.critical(self, 'Error', 'Please select a cell to place the dies.', QMessageBox.Ok)
            logging.error("Error placing dies: No cell selected")
            return
        if self.dieTextLayerComboBox.currentText() != '':
            die_text_layer = self.dieTextLayerComboBox.currentText()
        if self.dicingStreetsCheckBox.isChecked() and self.dicingStreetsLayerComboBox.currentText() != '':
            dicing_layer = self.dicingStreetsLayerComboBox.currentText()
        self.addSnapshot()

        total_locations = len(self.diePlacement.keys())
        progress_cnt = 0
        self.diePlacementProgressBar.show()
        found_die_labels = {}
        for loc in self.diePlacement:
            progress = int((progress_cnt + 1) / total_locations * 100)
            self.diePlacementProgressBar.setValue(progress)
            if self.dicingStreetsCheckBox.isChecked() and self.dicingStreetsLayerComboBox.currentText() == '':
                QMessageBox.critical(self, 'Error', 'Please select a layer for the dicing streets.', QMessageBox.Ok)
                logging.error("Error placing dies: No layer selected for dicing streets")
                self.diePlacementProgressBar.setValue(0)
                self.diePlacementProgressBar.hide()
                return
            if self.dicingStreetsCheckBox.isChecked() and self.dicingStreetsLayerComboBox.currentText() != '':
                dicing_layer_name = self.dicingStreetsLayerComboBox.currentText().split(':')[1].strip()
                dicing_street_L_LL = (loc[0] - self.die_width/2 - self.dicing_street_width/2)*1000, (loc[1] - self.die_height/2 - self.dicing_street_width/2)*1000
                dicing_street_L_UR = (loc[0] - self.die_width/2)*1000, (loc[1] + self.die_height/2 + self.dicing_street_width/2)*1000
                dicing_street_R_LL = (loc[0] + self.die_width/2)*1000, (loc[1] - self.die_height/2 - self.dicing_street_width/2)*1000
                dicing_street_R_UR = (loc[0] + self.die_width/2 + self.dicing_street_width/2)*1000, (loc[1] + self.die_height/2 + self.dicing_street_width/2)*1000
                dicing_street_T_LL = (loc[0] - self.die_width/2 - self.dicing_street_width/2)*1000, (loc[1] + self.die_height/2)*1000
                dicing_street_T_UR = (loc[0] + self.die_width/2 + self.dicing_street_width/2)*1000, (loc[1] + self.die_height/2 + self.dicing_street_width/2)*1000
                dicing_street_B_LL = (loc[0] - self.die_width/2 - self.dicing_street_width/2)*1000, (loc[1] - self.die_height/2 - self.dicing_street_width/2)*1000
                dicing_street_B_UR = (loc[0] + self.die_width/2 + self.dicing_street_width/2)*1000, (loc[1] - self.die_height/2)*1000
                self.gds_design.add_rectangle(self.placementCellComboBox.currentText(), dicing_layer_name, lower_left=dicing_street_L_LL, upper_right=dicing_street_L_UR)
                self.gds_design.add_rectangle(self.placementCellComboBox.currentText(), dicing_layer_name, lower_left=dicing_street_R_LL, upper_right=dicing_street_R_UR)
                self.gds_design.add_rectangle(self.placementCellComboBox.currentText(), dicing_layer_name, lower_left=dicing_street_T_LL, upper_right=dicing_street_T_UR)
                self.gds_design.add_rectangle(self.placementCellComboBox.currentText(), dicing_layer_name, lower_left=dicing_street_B_LL, upper_right=dicing_street_B_UR)
            if self.diePlacement[loc][0] is not None:
                child_cell_name = self.diePlacement[loc][0]['cellComboBox'].currentText()
                child_design = self.diePlacement[loc][0]['dieDesign']
                child_filename = self.diePlacement[loc][0]['fileName']

                if child_cell_name not in self.gds_design.lib.cells:
                    self.gds_design.lib.add(child_design.lib.cells[child_cell_name],
                                        overwrite_duplicate=True, include_dependencies=True, update_references=False)
                    unique_layers = set()
                    for cell_name in self.gds_design.lib.cells.keys():
                        if cell_name != '$$$CONTEXT_INFO$$$':
                            polygons_by_spec = self.gds_design.lib.cells[cell_name].get_polygons(by_spec=True)
                            for (lay, dat), polys in polygons_by_spec.items():
                                unique_layers.add(lay)
                    
                    for layer_number in unique_layers:
                        continueFlag = False
                        for number, name in self.layerData:
                            if int(number) == layer_number:
                                continueFlag = True
                                break
                        if continueFlag:
                            continue
                        self.gds_design.define_layer(str(layer_number), layer_number)
                        logging.info(f"Layer defined: {layer_number} with number {layer_number}")
                        
                        # Add new layer if it doesn't exist already
                        self.layerData.append((str(layer_number), str(layer_number)))
                        logging.info(f"New Layer added: {layer_number} - {layer_number}")

                    logging.info(f"Current layers: {self.gds_design.layers}")
                    self.updateLayersComboBox()

                    # Iterate through each item in the combo box
                    for index in range(self.dieTextLayerComboBox.count()):
                        entry = self.dieTextLayerComboBox.itemText(index)  # Get the text of the item at the current index
                        
                        if entry == die_text_layer:
                            self.dieTextLayerComboBox.setCurrentIndex(index)
                            break

                    # Iterate through each item in the combo box
                    for index in range(self.dicingStreetsLayerComboBox.count()):
                        entry = self.dicingStreetsLayerComboBox.itemText(index)  # Get the text of the item at the current index
                        
                        if entry == dicing_layer:
                            self.dicingStreetsLayerComboBox.setCurrentIndex(index)
                            break

                die_label = self.diePlacement[loc][0]['dieLabelEdit'].text()
                if die_label != '' and self.dieTextLayerComboBox.currentText() == '':
                    QMessageBox.critical(self, 'Error', 'Please select a layer for the die text.', QMessageBox.Ok)
                    logging.error("Error placing dies: No layer selected for die text")

                    self.diePlacementProgressBar.setValue(0)
                    self.diePlacementProgressBar.hide()
                    return
                die_notes = self.diePlacement[loc][0]['dieNotesEdit'].text()
                die_layers = child_design.get_layers_on_cell(child_cell_name)
                if 'subdicing' in die_notes.lower():
                    try:
                        subdicing_layer = int(self.subdicingStreetsLayerComboBox.currentText().split(':')[0].strip())
                    except:
                        QMessageBox.critical(self, 'Error', 'Subdicing layer must be an integer.', QMessageBox.Ok)
                        logging.error("Error placing dies: Subdicing layer not an integer")

                        self.diePlacementProgressBar.setValue(0)
                        self.diePlacementProgressBar.hide()
                        return
                    if subdicing_layer not in die_layers:
                        QMessageBox.critical(self, 'Error', 'Subdicing layer not found in die layers.', QMessageBox.Ok)
                        logging.error("Error placing dies: Subdicing layer not found in die layers")

                        self.diePlacementProgressBar.setValue(0)
                        self.diePlacementProgressBar.hide()
                        return
                offset = self.diePlacement[loc][0]['offset']

                position = (loc[0]*1000 - offset[0], loc[1]*1000 - offset[1])   # Convert to um
                self.gds_design.add_cell_reference(self.placementCellComboBox.currentText(), child_cell_name, position)

                if die_label != '':
                    if die_label not in found_die_labels:
                        found_die_labels[die_label] = 1
                    else:
                        found_die_labels[die_label] += 1
                    die_label = die_label + str(found_die_labels[die_label])
                    if self.diePlacement[loc][0]['dieTextPosition'] is None:
                        self.gds_design.add_text(self.placementCellComboBox.currentText(), 
                                                die_label, 
                                                self.dieTextLayerComboBox.currentText().split(':')[1].strip(), 
                                                ((loc[0]+self.die_width/2)*1000-2*len(die_label)*self.dieLabelTextHeight/TEXT_HEIGHT_FACTOR*GDS_TEXT_SPACING_FACTOR-self.dieLabelTextBuffer, 
                                                (loc[1]+self.die_height/2)*1000-self.dieLabelTextHeight-self.dieLabelTextBuffer), 
                                                self.dieLabelTextHeight/TEXT_HEIGHT_FACTOR)
                    else:
                        x, y = self.diePlacement[loc][0]['dieTextPosition']
                        self.gds_design.add_text(self.placementCellComboBox.currentText(), 
                                                die_label, 
                                                self.dieTextLayerComboBox.currentText().split(':')[1].strip(), 
                                                ((loc[0]+x)*1000, (loc[1]+y)*1000), 
                                                self.dieLabelTextHeight/TEXT_HEIGHT_FACTOR)
                
                self.logTestStructure(die_label, {'notes': die_notes, 
                                                  'center position (um)': (loc[0]*1000, loc[1]*1000), 
                                                  'die cell name': child_cell_name,
                                                  'die layers': die_layers, 
                                                  'die filename': child_filename})
            
            progress_cnt += 1
                
        self.writeToGDS()
        placement_map_filename = ''.join(self.outputFileName.split('.')[:-1]) + '_die_placement.png'
        self.dieFig.savefig(placement_map_filename, dpi=300)
        logging.info(f"Dies placed on design {self.outputFileName}, map saved to {placement_map_filename}")

        # Reset progress bar to 0 or hide it when the task is complete
        self.diePlacementProgressBar.setValue(0)
        self.diePlacementProgressBar.hide()
        
    # Method to add a row
    def addRow(self):
        logging.info("Adding a new row to the Die Placement Menu")
        rowLayout = QHBoxLayout()
        
        # Apply background color to the row
        color = COLOR_SEQUENCE[self.rowIndex % len(COLOR_SEQUENCE)]
        rowWidget = QWidget()
        rowWidget.setStyleSheet(f"background-color: {color}; padding: 5px;")
        rowWidget.setLayout(rowLayout)

        rowWidget.mousePressEvent = lambda event, widget=rowWidget, idx=self.rowIndex: self.setActiveRow(idx)

        # Select File Button
        selectFileButton = QPushButton('Select GDS File')
        selectFileButton.clicked.connect(self.dieSelectGDSFile)
        selectFileButton.setToolTip('Click to select the GDS file for the die.')
        rowLayout.addWidget(selectFileButton)

        # Cell Dropdown Combo Box
        cellComboBox = QComboBox()
        cellComboBox.setMinimumWidth(1000)
        cellComboBox.setPlaceholderText('Select Cell')
        cellComboBox.currentTextChanged.connect(self.validateDieCells)
        cellComboBox.setToolTip('Select the cell from the GDS file to place.')
        rowLayout.addWidget(cellComboBox)

        # Text Input Field for Number of Dies
        numDiesEdit = PushButtonEdit(self.autoPlaceButton)
        numDiesEdit.setPlaceholderText('Number of Dies')
        numDiesEdit.setToolTip('type:(integer) Enter the number of dies to place.')
        rowLayout.addWidget(numDiesEdit)

        # Text Input Field for Die Label
        dieLabelEdit = PushButtonEdit(self.autoPlaceButton)
        dieLabelEdit.setPlaceholderText('Die Label')
        dieLabelEdit.setToolTip('type:(string) Enter the text to display for the die label.')
        dieLabelEdit.editingFinished.connect(self.updatePlacementLegend)
        rowLayout.addWidget(dieLabelEdit)

        # Text Input Field for Die Notes
        dieNotesEdit = PushButtonEdit(self.autoPlaceButton)
        dieNotesEdit.setPlaceholderText('Die Notes')
        dieNotesEdit.setToolTip('type:(string) Enter any notes for the die.')
        dieNotesEdit.editingFinished.connect(self.updatePlacementLegend)
        rowLayout.addWidget(dieNotesEdit)

        dieTextPositionEdit = PushButtonEdit(self.autoPlaceButton)
        dieTextPositionEdit.setPlaceholderText('Label Position x,y (mm)')
        dieTextPositionEdit.setToolTip('type:(comma-separated tuple x,y) Enter the bottom-left text position for the die labels in mm assuming 0,0 is at the center of the window for the die. Can leave blank for default.')
        dieTextPositionEdit.editingFinished.connect(self.updateDieLabelPosition)
        rowLayout.addWidget(dieTextPositionEdit)

        dieDeepSiEtchingMinFeatureSizeEdit = QLineEdit()
        dieDeepSiEtchingMinFeatureSizeEdit.setPlaceholderText('0')
        dieDeepSiEtchingMinFeatureSizeEdit.setReadOnly(True)
        dieDeepSiEtchingMinFeatureSizeEdit.setToolTip('Displays the minimum feature size for deep Si etching.')
        rowLayout.addWidget(dieDeepSiEtchingMinFeatureSizeEdit)

        dieDeepSiEtchingMaxFeatureSizeEdit = QLineEdit()
        dieDeepSiEtchingMaxFeatureSizeEdit.setPlaceholderText('0')
        dieDeepSiEtchingMaxFeatureSizeEdit.setReadOnly(True)
        dieDeepSiEtchingMaxFeatureSizeEdit.setToolTip('Displays the maximum feature size for deep Si etching.')
        rowLayout.addWidget(dieDeepSiEtchingMaxFeatureSizeEdit)

        # Add the row widget (with layout and color) to the left layout
        self.dieLeftLayout.addWidget(rowWidget)
        self.dieInfo[self.rowIndex] = {}
        self.dieInfo[self.rowIndex]['selectFileButton'] = selectFileButton
        self.dieInfo[self.rowIndex]['cellComboBox'] = cellComboBox
        self.dieInfo[self.rowIndex]['numDiesEdit'] = numDiesEdit
        self.dieInfo[self.rowIndex]['dieLabelEdit'] = dieLabelEdit
        self.dieInfo[self.rowIndex]['dieNotesEdit'] = dieNotesEdit
        self.dieInfo[self.rowIndex]['dieTextPositionEdit'] = dieTextPositionEdit
        self.dieInfo[self.rowIndex]['rowWidget'] = rowWidget
        self.dieInfo[self.rowIndex]['dieDesign'] = None
        self.dieInfo[self.rowIndex]['offset'] = None
        self.dieInfo[self.rowIndex]['fileName'] = None
        self.dieInfo[self.rowIndex]['dieTextPosition'] = None
        self.dieInfo[self.rowIndex]['dieDeepSiEtchingMinFeatureSizeEdit'] = dieDeepSiEtchingMinFeatureSizeEdit
        self.dieInfo[self.rowIndex]['dieDeepSiEtchingMaxFeatureSizeEdit'] = dieDeepSiEtchingMaxFeatureSizeEdit
        self.rowIndex += 1
        
    def showDiePlacementUtility(self):
        # Create a new window for the Die Placement Utility
        self.diePlacementWindow = QDialog(self, Qt.Window)
        self.diePlacementWindow.setWindowTitle('Die Placement Menu')

        self.waferDiameter = None
        self.wafer = None
        self.activeRow = None
        self.diePlacement = {}
        self.dieInfo = {}
        self.dpw = 0
        self.blacklistMode = False
        self.rowIndex = 0
        self.die_width = None
        self.die_height = None
        self.dicing_street_width = None
        self.dieLabelTextBuffer = 100
        self.dieLabelTextHeight = 200

        # Main layout
        mainLayout = QHBoxLayout()

        # Left layout for file selection, cell dropdown, and text input
        self.dieLeftLayout = QVBoxLayout()

        # Substrate layout
        substrateLayout = QHBoxLayout()

        # Substrate label
        substrateLabel = QLabel('Substrate:')
        substrateLayout.addWidget(substrateLabel)

        # Checkbox for 4" (100mm)
        self.substrate4InchCheckBox = QCheckBox('4" (100mm)')
        self.substrate4InchCheckBox.stateChanged.connect(self.onSubstrate4InchChecked)
        substrateLayout.addWidget(self.substrate4InchCheckBox)

        # Checkbox for 6" (150mm)
        self.substrate6InchCheckBox = QCheckBox('6" (150mm)')
        self.substrate6InchCheckBox.stateChanged.connect(self.onSubstrate6InchChecked)
        substrateLayout.addWidget(self.substrate6InchCheckBox)

        # Add the substrate layout to the top of the left layout
        self.dieLeftLayout.addLayout(substrateLayout)

        dieDimensionsLayout = QHBoxLayout()
        dieWidthLabel = QLabel('Die Width (mm):')
        self.dieWidthEdit = EnterLineEdit()
        self.dieWidthEdit.setPlaceholderText('Die Width (mm)')
        self.dieWidthEdit.editingFinished.connect(self.createDiePlacement)
        self.dieWidthEdit.setToolTip('type:(number) Enter the width of the die in mm.')

        dieHeightLabel = QLabel('Die Height (mm):')
        self.dieHeightEdit = EnterLineEdit()
        self.dieHeightEdit.setPlaceholderText('Die Height (mm)')
        self.dieHeightEdit.editingFinished.connect(self.createDiePlacement)
        self.dieHeightEdit.setToolTip('type:(number) Enter the height of the die in mm.')

        dicingStreetLabel = QLabel('Dicing Street Width (mm):')
        self.dicingStreetEdit = EnterLineEdit()
        self.dicingStreetEdit.setPlaceholderText('Dicing Street Width (mm)')
        self.dicingStreetEdit.editingFinished.connect(self.createDiePlacement)
        self.dicingStreetEdit.setToolTip('type:(number) Enter the width of the dicing street in mm.')

        edgeMarginLabel = QLabel('Edge Margin (mm):')
        self.edgeMarginEdit = EnterLineEdit()
        self.edgeMarginEdit.setPlaceholderText('Edge Margin (mm)')
        self.edgeMarginEdit.editingFinished.connect(self.createDiePlacement)
        self.edgeMarginEdit.setToolTip('type:(number) Enter the edge margin in mm.')

        centeredPlacementLabel = QLabel('Centered Placement:')
        self.centeredPlacementCheckBox = QCheckBox()
        self.centeredPlacementCheckBox.stateChanged.connect(self.createDiePlacement)
        self.centeredPlacementCheckBox.setToolTip('Check to place the dies in a centered arrangement.')

        self.dpwTextBox = QLineEdit()
        self.dpwTextBox.setPlaceholderText('Available Die Locations')
        self.dpwTextBox.setText(str(self.dpw))
        self.dpwTextBox.setReadOnly(True)
        self.dpwTextBox.setToolTip('Displays the number of available locations for dies to be placed.')

        dieDimensionsLayout.addWidget(dieWidthLabel)
        dieDimensionsLayout.addWidget(self.dieWidthEdit)
        dieDimensionsLayout.addWidget(dieHeightLabel)
        dieDimensionsLayout.addWidget(self.dieHeightEdit)
        dieDimensionsLayout.addWidget(dicingStreetLabel)
        dieDimensionsLayout.addWidget(self.dicingStreetEdit)
        dieDimensionsLayout.addWidget(edgeMarginLabel)
        dieDimensionsLayout.addWidget(self.edgeMarginEdit)
        dieDimensionsLayout.addWidget(centeredPlacementLabel)
        dieDimensionsLayout.addWidget(self.centeredPlacementCheckBox)
        dieDimensionsLayout.addWidget(self.dpwTextBox)

        self.dieLeftLayout.addLayout(dieDimensionsLayout)

        # Die Placement layout
        diePlacementLayout = QHBoxLayout()
        placementCellLabel = QLabel('Cell to Place Dies:')
        self.dicingStreetsCheckBox = QCheckBox('Add Dicing Streets?')
        self.dicingStreetsCheckBox.stateChanged.connect(self.dicingStreetsCheckBoxChanged)
        dieTextLayerLabel = QLabel('Layer for Die Labels:')
        dieTextSizeLabel = QLabel('Label Text Height:')
        dieTextSizeTextBox = EnterLineEdit()
        dieTextSizeTextBox.setText(str(self.dieLabelTextHeight))
        dieTextSizeTextBox.setToolTip('type:(number) Enter the text height for the die labels in um.')
        dieTextSizeTextBox.editingFinished.connect(self.setDieLabelTextHeight)
        subdicingStreetsLayerLabel = QLabel('Subdicing Streets Layer:')
        deepSiEtchingLayerLabel = QLabel('Deep Si Etching Layer:')
        diePlacementLayout.addWidget(placementCellLabel)
        diePlacementLayout.addWidget(self.placementCellComboBox)
        diePlacementLayout.addWidget(dieTextLayerLabel)
        diePlacementLayout.addWidget(self.dieTextLayerComboBox)
        diePlacementLayout.addWidget(dieTextSizeLabel)
        diePlacementLayout.addWidget(dieTextSizeTextBox)
        diePlacementLayout.addWidget(subdicingStreetsLayerLabel)
        diePlacementLayout.addWidget(self.subdicingStreetsLayerComboBox)
        diePlacementLayout.addWidget(deepSiEtchingLayerLabel)
        diePlacementLayout.addWidget(self.deepSiEtchingLayerComboBox)
        diePlacementLayout.addWidget(self.dicingStreetsCheckBox)
        diePlacementLayout.addWidget(self.dicingStreetsLayerComboBox)

        self.dicingStreetsLayerComboBox.hide()
        self.dieLeftLayout.addLayout(diePlacementLayout)

        addRowButton = QPushButton('+ Add Row')
        addRowButton.clicked.connect(self.addRow)
        self.dieLeftLayout.addWidget(addRowButton)

        buttonLayout = QHBoxLayout()
        self.autoPlaceButton = QPushButton('Automatically Place Dies')
        self.autoPlaceButton.clicked.connect(self.autoPlaceDies)
        self.autoPlaceButton.setToolTip('Click to automatically place the dies in the available locations.')
        buttonLayout.addWidget(self.autoPlaceButton)
        self.shuffleCheckBox = QCheckBox('Shuffle Placement?')
        self.shuffleCheckBox.setToolTip('Check to shuffle the automatic placement of the dies.')
        buttonLayout.addWidget(self.shuffleCheckBox)
        clearButton = QPushButton('Clear Die Placement')
        clearButton.clicked.connect(self.createDiePlacement)
        clearButton.setToolTip('Click to clear the die placement.')
        buttonLayout.addWidget(clearButton)

        self.dieLeftLayout.addLayout(buttonLayout)

        placementLayout = QVBoxLayout()
        placeDiesButton = QPushButton('Finalize and Write to GDS')
        placeDiesButton.clicked.connect(self.placeDiesOnDesign)
        placeDiesButton.setToolTip('Click to place the selected dies on the loaded .gds design.')
        placementLayout.addWidget(placeDiesButton)
        self.dieLeftLayout.addLayout(placementLayout)

        # Initial row
        self.addRow()

        # Add left layout to main layout
        mainLayout.addLayout(self.dieLeftLayout)

        diePlotLayout = QVBoxLayout()
        # Graphical Interface using Matplotlib
        self.dieFig = Figure(figsize=(20, 12))  # Adjust size as needed
        self.dieCanvas = FigureCanvas(self.dieFig)
        self.dieCanvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dieCanvas.mpl_connect('button_press_event', self.die_on_click)
        self.dieAx = self.dieFig.add_subplot(111)
        diePlotLayout.addWidget(self.dieCanvas)

        # Add the navigation toolbar to the layout
        self.dieToolbar = NavigationToolbar(self.dieCanvas, self)
        diePlotLayout.addWidget(self.dieToolbar)

        modeButtonLayout = QHBoxLayout()
        self.blacklistButton = QPushButton('Blacklist Mode')
        self.blacklistButton.setToolTip('Click to enter blacklist mode.')
        self.blacklistButton.clicked.connect(self.setBlacklistMode)
        modeButtonLayout.addWidget(self.blacklistButton)
        diePlotLayout.addLayout(modeButtonLayout)

        # Create a progress bar
        self.diePlacementProgressBar = QProgressBar(self)
        self.diePlacementProgressBar.setMaximum(100)  # Set the maximum value of the progress bar
        self.diePlacementProgressBar.setValue(0)  # Initialize with 0 value
        self.diePlacementProgressBar.hide()
        
        # Add the progress bar to the layout
        diePlotLayout.addWidget(self.diePlacementProgressBar)

        mainLayout.addLayout(diePlotLayout)

        # Set the layout for the pop-up window
        self.diePlacementWindow.setLayout(mainLayout)
        self.diePlacementWindow.resize(3000, 1200)  # Adjust window size as needed
        self.diePlacementWindow.show()

    def updateDieLabelPosition(self):
        sender = self.sender()
        for rowIndex in self.dieInfo:
            dieTextPositionEdit= self.dieInfo[rowIndex]['dieTextPositionEdit']
            if dieTextPositionEdit == sender:
                break

        raw_text = sender.text()
        if raw_text == '':
            self.dieInfo[rowIndex]['dieTextPosition'] = None
            logging.info("Die label position set to None")
            return
        if self.die_width is None or self.die_height is None:
            QMessageBox.critical(self, 'Error', 'Please set the die dimensions before positioning labels.', QMessageBox.Ok)
            logging.error("Error updating die label position: Die dimensions not set")
            return
        split = raw_text.split(',')
        if len(split) != 2:
            QMessageBox.critical(self, 'Error', 'Invalid format for die label position.', QMessageBox.Ok)
            logging.error("Error updating die label position: Invalid format")
            return
        try:
            x = float(split[0].strip())
            y = float(split[1].strip())
            if x <= -self.die_width/2 or x >= self.die_width/2 or y <= -self.die_height/2 or y >= self.die_height/2:
                QMessageBox.critical(self, 'Error', 'Die label position outside the die dimensions.', QMessageBox.Ok)
                logging.error("Error updating die label position: Position outside die dimensions")
                return
            self.dieInfo[rowIndex]['dieTextPosition'] = (x, y)
            logging.info(f"Die label position set to {self.dieInfo[rowIndex]['dieTextPosition']}")
        except:
            QMessageBox.critical(self, 'Error', 'Invalid format for die label position.', QMessageBox.Ok)
            logging.error("Error updating die label position: Invalid format")
            return

    def setDieLabelTextHeight(self):
        self.dieLabelTextHeight = float(self.sender().text())
        logging.info(f"Die label text height set to {self.dieLabelTextHeight}")

    def dicingStreetsCheckBoxChanged(self):
        if self.dicingStreetsCheckBox.isChecked():
            self.dicingStreetsLayerComboBox.show()
            logging.info("Dicing streets checkbox checked")
        else:
            self.dicingStreetsLayerComboBox.hide()
            logging.info("Dicing streets checkbox unchecked")

    def setBlacklistMode(self):
        self.blacklistMode = not self.blacklistMode
        if self.blacklistMode:
            self.setActiveRow(self.activeRow)
            self.blacklistButton.setStyleSheet("background-color: lightgreen")
            logging.info("Blacklist mode is active")
        else:
            self.blacklistButton.setStyleSheet("")
            logging.info("Blacklist mode is inactive")

    def defineNewCell(self):
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No GDS design loaded.", QMessageBox.Ok)
            logging.error("No GDS design loaded.")
            return
        if self.newCellNameEdit.text() == "":
            QMessageBox.critical(self, "Input Error", "No cell name provided.", QMessageBox.Ok)
            logging.error("No cell name provided.")
            return
        if self.outputFileName == "":
            QMessageBox.critical(self, "Output Error", "No output file name provided.", QMessageBox.Ok)
            logging.error("No output file name provided.")
            return
        self.gds_design.add_cell(self.newCellNameEdit.text().strip())
        self.updateCellComboBox()

        self.addSnapshot()
        self.writeToGDS()

    def setRoutingMode(self):
        self.routingMode = True
        self.flareMode = False
        self.updateModeButtons()
        self.endingTraceWidthEdit.hide()
        self.endingTraceSpaceEdit.hide()
        self.flareRoutingAngleEdit.hide()
        self.flareEscapeExtentEdit.hide()
        self.flareFinalLengthEdit.hide()
        self.flareAutoroutingAngleEdit.hide()

    def setFlareMode(self):
        self.routingMode = False
        self.flareMode = True
        self.updateModeButtons()
        self.endingTraceWidthEdit.show()
        self.endingTraceSpaceEdit.show()
        self.flareRoutingAngleEdit.show()
        self.flareEscapeExtentEdit.show()
        self.flareFinalLengthEdit.show()
        self.flareAutoroutingAngleEdit.show()

    def updateModeButtons(self):
        if self.routingMode:
            self.routingModeButton.setStyleSheet("background-color: lightgreen")
            self.flareModeButton.setStyleSheet("")
        else:
            self.routingModeButton.setStyleSheet("")
            self.flareModeButton.setStyleSheet("background-color: lightgreen")
    
    def showMatplotlibWindow(self):
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No GDS design loaded.", QMessageBox.Ok)
            logging.error("No GDS design loaded.")
            return
        if self.cellComboBox.currentText() == "":
            QMessageBox.critical(self, "Selection Error", "No cell selected from the dropdown menu.", QMessageBox.Ok)
            logging.error("No cell selected from the dropdown menu.")
            return
        if self.plotLayersComboBox.currentText() == "":
            QMessageBox.critical(self, "Selection Error", "No layer selected from the dropdown menu.", QMessageBox.Ok)
            logging.error("No layer selected from the dropdown menu.")
            return

        self.update_plot_data()

    def update_plot_data(self):
        if self.gds_design is None:
            return
        if self.cellComboBox.currentText() == "":
            return
        if self.plotLayersComboBox.currentText() == "":
            return
        selected_cell = self.cellComboBox.currentText()
        cell = self.gds_design.check_cell_exists(selected_cell)
        polygons_by_spec = cell.get_polygons(by_spec=True)
        plot_layer_polygons = []
        plot_layer_number = int(self.plotLayersComboBox.currentText().split(':')[0].strip())

        for (lay, dat), polys in polygons_by_spec.items():
            for poly in polys:
                if lay == plot_layer_number:
                    plot_layer_polygons.append(Polygon(poly))
    
        self.ax.clear()
        for poly in plot_layer_polygons:
            x, y = poly.exterior.xy
            self.ax.plot(x, y, color='tab:blue')

        self.ax.set_aspect('equal', 'datalim')
        # Increase the size of the tick marks
        self.ax.tick_params(axis='both', which='major', labelsize=18, length=10, width=2)
        self.canvas.draw()

    def on_click(self, event):
        # Check if the toolbar is in zoom mode
        if self.toolbar.mode == '':
            if event.inaxes is not None:
                x, y = event.xdata, event.ydata
                logging.info(f"Click at position: ({x}, {y})")
                # You can process the click coordinates here
                self.process_click(x, y)
            else:
                logging.info("Click outside axes bounds")
        else:
            logging.info(f"Toolbar mode is active ({self.toolbar.mode}), click not registered")

    def process_click(self, x, y):
        # Implement your processing logic here
        logging.info(f"Processing click at: ({x}, {y})")

        if self.routingMode:
            logging.info("Routing mode is active")
            min_dist = np.inf
            route_ports = None
            route_orientations = None
            route_trace_width = None
            route_trace_space = None

            cell = self.gds_design.check_cell_exists(self.cellComboBox.currentText())
            layer_number = int(self.plotLayersComboBox.currentText().split(':')[0].strip())
            layer_name = self.plotLayersComboBox.currentText().split(':')[1].strip()
            for escapeDict in self.escapeDicts[self.cellComboBox.currentText()]:
                # Calculate the distance from the click to the escape routing
                for orientation in escapeDict:
                    layer = escapeDict[orientation]['layer_number']
                    if layer == layer_number:
                        dist = np.linalg.norm(np.mean(escapeDict[orientation]['ports'], axis=0)-np.array([x, y]))
                        if dist < min_dist:
                            min_dist = dist
                            route_ports = escapeDict[orientation]['ports']
                            route_orientations = escapeDict[orientation]['orientations']  
                            route_trace_width = escapeDict[orientation]['trace_width']
                            route_trace_space = escapeDict[orientation]['trace_space']
            
            if route_ports is None:
                QMessageBox.critical(self, "Design Error", "No ports found in cell.", QMessageBox.Ok)
                logging.error("No valid ports found in cell.")
                return
            # Query the user to confirm the choice of ports and orientations
            reply = QMessageBox.question(self, "Confirm Ports", f"You have selected {len(route_ports)} ports at center {np.mean(route_ports, axis=0)} with orientation {route_orientations[0]}.", 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.routing.append((route_ports, route_orientations, route_trace_width, route_trace_space))
            else:
                return
            
            if len(self.routing) == 2:
                ports1, orientations1, trace_width1, trace_space1 = self.routing[0]
                ports2, orientations2, trace_width2, trace_space2 = self.routing[1]

                if trace_width1 != trace_width2 or trace_space1 != trace_space2:
                    QMessageBox.critical(self, "Design Error", "Trace pitches do not match.", QMessageBox.Ok)
                    logging.error("Trace pitches do not match.")
                    self.routing = []
                    return
                
                obstacles = []
                polygons_by_spec = cell.get_polygons(by_spec=True)
                for (lay, dat), polys in polygons_by_spec.items():
                    if lay == layer_number:
                        for poly in polys:
                            poly = np.around(poly, 3)
                            obstacles.append(poly.tolist())

                self.addSnapshot()  # Store snapshot before adding new design
                try:
                    if len(ports1) != len(ports2):
                        if len(ports1) < len(ports2):
                            ports2 = ports2[:len(ports1)]
                            orientations2 = orientations2[:len(orientations1)]
                        else:
                            ports1 = ports1[:len(ports2)]
                            orientations1 = orientations1[:len(orientations2)]

                    self.gds_design.route_ports_a_star(self.cellComboBox.currentText(), ports1, orientations1,
                                                ports2, orientations2, trace_width1, trace_space1, layer_name,
                                                show_animation=True, obstacles=obstacles)

                    # Remove the routed ports from the corresponding escapeDicts
                    for escapeDict in self.escapeDicts[self.cellComboBox.currentText()]:
                        for orientation in escapeDict:
                            ports = escapeDict[orientation]['ports']
                            
                            idx1 = np.where(~np.any(np.all(ports[:, None] == ports1, axis=2), axis=1))[0]
                            idx2 = np.where(~np.any(np.all(ports[:, None] == ports2, axis=2), axis=1))[0]

                            idx = np.intersect1d(idx1, idx2)
                            escapeDict[orientation]['ports'] = escapeDict[orientation]['ports'][idx]
                            escapeDict[orientation]['orientations'] = escapeDict[orientation]['orientations'][idx]          
                    
                    # Write the design
                    self.writeToGDS()
                    # Update the available space
                    self.updateAvailableSpace()
                    
                    self.update_plot_data()
                except (Exception, AssertionError, ValueError) as e:
                    QMessageBox.critical(self, "Design Error", f"Error routing ports: {str(e)}", QMessageBox.Ok)
                    logging.error(f"Error routing ports: {str(e)}")

                    self.undo()

                self.routing = []

        elif self.flareMode:
            logging.info("Flare mode is active")
            try:
                ending_trace_width = float(self.endingTraceWidthEdit.text())
                ending_trace_space = float(self.endingTraceSpaceEdit.text())
                flare_routing_angle = float(self.flareRoutingAngleEdit.text())
                flare_escape_extent = float(self.flareEscapeExtentEdit.text())
                flare_final_length = float(self.flareFinalLengthEdit.text())
                flare_autorouting_angle = float(self.flareAutoroutingAngleEdit.text())
            except ValueError:
                QMessageBox.critical(self, "Design Error", "Invalid flare parameters.", QMessageBox.Ok)
                logging.error("Invalid flare parameters.")
                return
            
            min_dist = np.inf
            min_orientation = None
            route_ports = None
            route_orientations = None
            route_trace_width = None
            route_trace_space = None

            cell = self.gds_design.check_cell_exists(self.cellComboBox.currentText())
            layer_number = int(self.plotLayersComboBox.currentText().split(':')[0].strip())
            layer_name = self.plotLayersComboBox.currentText().split(':')[1].strip()
            for i, escapeDict in enumerate(self.escapeDicts[self.cellComboBox.currentText()]):
                # Calculate the distance from the click to the escape routing
                for orientation in escapeDict:
                    layer = escapeDict[orientation]['layer_number']
                    if layer == layer_number:
                        dist = np.linalg.norm(np.mean(escapeDict[orientation]['ports'], axis=0)-np.array([x, y]))
                        if dist < min_dist:
                            min_dist = dist
                            min_orientation = i, orientation
                            route_ports = escapeDict[orientation]['ports']
                            route_orientations = escapeDict[orientation]['orientations']  
                            route_trace_width = escapeDict[orientation]['trace_width']
                            route_trace_space = escapeDict[orientation]['trace_space']
            
            if route_ports is None:
                QMessageBox.critical(self, "Design Error", "No ports found in cell.", QMessageBox.Ok)
                logging.error("No valid ports found in cell.")
                return
            
            # Query the user to confirm the choice of ports and orientations
            reply = QMessageBox.question(self, "Confirm Ports", f"You have selected {len(route_ports)} ports at center {np.mean(route_ports, axis=0)} with orientation {route_orientations[0]}.", 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.addSnapshot()  # Store snapshot before adding new design
                try:
                    new_ports, new_orientations, new_trace_width, new_trace_space = self.gds_design.flare_ports(self.cellComboBox.currentText(), layer_name, route_ports, 
                                                                                                                     route_orientations, route_trace_width, route_trace_space, 
                                                                                                                     ending_trace_width, ending_trace_space, routing_angle=flare_routing_angle,
                                                                                                                     escape_extent=flare_escape_extent, final_length=flare_final_length,
                                                                                                                     autorouting_angle=flare_autorouting_angle)
                
                    self.escapeDicts[self.cellComboBox.currentText()][min_orientation[0]][min_orientation[1]]['ports'] = new_ports
                    self.escapeDicts[self.cellComboBox.currentText()][min_orientation[0]][min_orientation[1]]['orientations'] = new_orientations
                    self.escapeDicts[self.cellComboBox.currentText()][min_orientation[0]][min_orientation[1]]['trace_width'] = new_trace_width
                    self.escapeDicts[self.cellComboBox.currentText()][min_orientation[0]][min_orientation[1]]['trace_space'] = new_trace_space
                    # Write the design
                    self.writeToGDS()
                    # Update the available space
                    self.updateAvailableSpace()
                    
                    self.update_plot_data()
                except (Exception, AssertionError, ValueError) as e:
                    QMessageBox.critical(self, "Design Error", f"Error flaring ports: {str(e)}", QMessageBox.Ok)
                    logging.error(f"Error flaring ports: {str(e)}")

                    self.undo()
                    return
            else:
                return
    
    def updateExcludedLayers(self):
        # Output: sets self.excludedLayers and updates available space and all other polygons
        excluded_layers_input = self.excludedLayersEdit.text()
        excluded_layers = excluded_layers_input.split(',')
        valid_layers = []
        for layer in excluded_layers:
            layer = layer.strip()
            if layer.isdigit():
                layer_number = int(layer)
                if layer_number == self.substrateLayer:
                    QMessageBox.critical(self, "Layer Error", "Cannot exclude the substrate layer.", QMessageBox.Ok)
                    logging.error(f"Excluded Layers input error: Cannot exclude substrate layer {layer}")
                    return
                elif any(int(number) == layer_number for number, name in self.layerData):
                    valid_layers.append(layer_number)
                else:
                    QMessageBox.critical(self, "Layer Error", f"Invalid layer number: {layer}", QMessageBox.Ok)
                    logging.error(f"Excluded Layers input error: Invalid layer number {layer}")
                    return
            else:
                if any(name.lower() == layer.lower() for number, name in self.layerData) and not any(int(number) == self.substrateLayer for number, name in self.layerData if name.lower() == layer.lower()):
                    valid_layers.append(next(int(number) for number, name in self.layerData if name.lower() == layer.lower() and int(number) != self.substrateLayer))
                else:
                    QMessageBox.critical(self, "Layer Error", f"Invalid layer name: {layer}", QMessageBox.Ok)
                    logging.error(f"Excluded Layers input error: Invalid layer name {layer}")
                    return
                
        self.excludedLayers = valid_layers
        logging.info(f"Excluded layers set to: {self.excludedLayers}")
        if type(self.substrateLayer) == int:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if substrate_name:
                self.availableSpace, self.allOtherPolygons = self.gds_design.determine_available_space(substrate_name, self.excludedLayers)
                logging.info(f"Available space calculated.")
                logging.info(f"All other polygons calculated.")

    def calculateLayerArea(self):
        currentLayer = self.layersComboBox.currentText()
        if currentLayer:
            layerName = currentLayer.split(':')[1].strip()
            try:
                if self.layerCellComboBox.currentText() != "":
                    cell_name = self.layerCellComboBox.currentText()
                else:
                    cell_name = None
                area = round(self.gds_design.calculate_area_for_layer(layerName, cell_name=cell_name), 6)
                self.layerAreaEdit.setText(f"{area} mm^2")
                logging.info(f"Layer Area for {layerName}: {area} mm^2")
            except Exception as e:
                QMessageBox.critical(self, "Calculation Error", f"Error calculating area for layer {layerName}: {str(e)}", QMessageBox.Ok)
                logging.error(f"Error calculating area for layer {layerName}: {str(e)}")
        else:
            QMessageBox.warning(self, "Selection Error", "No layer selected from the dropdown menu.", QMessageBox.Ok)

    def createCheckStateHandler(self, state):
        sender = self.sender()
        name = sender.text()
        logging.info(f"{name} {'selected' if state == Qt.Checked else 'unselected'}")
    
    def selectSubstrateLayer(self):
        # Output: sets self.substrateLayer and sets available space and all other polygons
        currentLayer = self.layersComboBox.currentText()
        if currentLayer:
            layerNumber = int(currentLayer.split(':')[0])
            if layerNumber in self.excludedLayers:
                QMessageBox.critical(self, "Layer Error", "Cannot set the substrate layer to an excluded layer.", QMessageBox.Ok)
                logging.error(f"Substrate layer selection error: Cannot set to excluded layer {layerNumber}")
                return
            
            # Initialize available space
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == layerNumber:
                    substrate_name = name
            if substrate_name:
                try:
                    self.availableSpace, self.allOtherPolygons = self.gds_design.determine_available_space(substrate_name, self.excludedLayers)
                    logging.info(f"Available space calculated.")
                    logging.info(f"All other polygons calculated.")

                    self.substrateLayer = layerNumber
                    logging.info(f"Substrate layer set to: {self.substrateLayer}")
                    QMessageBox.information(self, "Substrate Layer Selected", f"Substrate layer set to: {self.substrateLayer}", QMessageBox.Ok)
                except ValueError:
                    QMessageBox.critical(self, "Layer Error", "Substrate layer does not exist in the design. First add substrate shape to the design and then re-select as substrate layer.", QMessageBox.Ok)
                    logging.error(f"Substrate layer selection error: Layer {self.substrateLayer} does not exist in the design.")
        else:
            QMessageBox.warning(self, "Selection Error", "No layer selected from the dropdown menu.", QMessageBox.Ok)

    def createParamChangeHandler(self, param):
        sender = self.sender()
        # Update the default value to display for the specific test structure and parameter
        for checkBox, cellComboBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if comboBox == sender:
                name = checkBox.text()
                value = defaultParams.get(param, '')
                valueEdit.setText(str(value))
                # Set tooltip for the parameter value edit field
                tooltip = self.paramTooltips.get(name, {}).get(param, '')
                comboBox.setToolTip(tooltip)
                # Log that this specific test structure has this parameter selected
                logging.info(f"{name} Parameter {param} selected, display value set to {value}")
                
    def createParamStoreHandler(self):
        sender = self.sender()
        for checkBox, cellComboBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if valueEdit == sender:
                name = checkBox.text()
                comboBox = comboBox
                break
        self.storeParameterValue(comboBox, valueEdit, name)

    def createAddToDesignHandler(self):
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No GDS design loaded.", QMessageBox.Ok)
            logging.error("No GDS design loaded.")
            return
        sender = self.sender()
        for checkBox, _, _, _, _, addButton in self.testStructures:
            if addButton == sender:
                name = checkBox.text()
                break
        self.handleAddToDesign(name)

    def addSnapshot(self):
        logging.info("Adding snapshot to undo stack and clearing redo stack")
        self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons), deepcopy(self.escapeDicts)))
        self.redoStack.clear()

    def readLogEntries(self):
        with open(self.logFileName, 'r') as log_file:
            return log_file.readlines()
        
    def writeLogEntries(self, log_entries):
        with open(self.logFileName, 'w') as log_file:
            log_file.writelines(log_entries)

    def undo(self):
        if self.undoStack:
            logging.info("Adding snapshot to redo stack and reverting to previous state")
            self.redoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons), deepcopy(self.escapeDicts)))
            self.gds_design, log_entries, self.availableSpace, self.allOtherPolygons, self.escapeDicts = self.undoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()

            self.update_plot_data()
        else:
            QMessageBox.critical(self, "Edit Error", "No undo history is currently stored", QMessageBox.Ok)
            logging.error("No undo history is currently stored")

    def redo(self):
        if self.redoStack:
            logging.info("Adding snapshot to undo stack and reverting to previous state")
            self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons), deepcopy(self.escapeDicts)))
            self.gds_design, log_entries, self.availableSpace, self.allOtherPolygons, self.escapeDicts = self.redoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()

            self.update_plot_data()
        else:
            QMessageBox.critical(self, "Edit Error", "No redo history is currently stored", QMessageBox.Ok)
            logging.error("No redo history is currently stored")

    def createBlankDesign(self):
        self.inputFileName = ""
        self.outputFileName = ""
        self.outFileField.setText("")
        self.logFileName = ""
        self.layerData = []
        self.substrateLayer = None
        self.availableSpace = None
        self.allOtherPolygons = None
        self.undoStack = []  # Initialize undo stack
        self.redoStack = []  # Initialize redo stack
        self.escapeDicts = {}  # To store escape routing dictionaries
        self.routing = []
        self.routingMode = False
        self.flareMode = False
        self.pitch_x = None
        self.pitch_y = None
        self.copies_x = None
        self.copies_y = None
        self.center_escape = None

        self.gds_design = GDSDesign()
        logging.info("Blank GDS design created")

        self.updateCellComboBox()
        self.updateLayersComboBox()

        QMessageBox.information(self, "Design Created", "Blank GDS design created.", QMessageBox.Ok)

    def selectInputFile(self):
        # Output: sets self.inputFileName, self.outputFileName, self.logFileName, self.gds_design, self.layerData, and updates layersComboBox and customTestCellComboBox
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.gds'):
                self.inputFileName = fileName
                logging.info(f"Input File: {self.inputFileName}")
                baseName = fileName.rsplit('.', 1)[0]
                self.outputFileName = f"{baseName}-output.gds"
                self.outFileField.setText(self.outputFileName)
                logging.info(f"Output File automatically set to: {self.outputFileName}")

                self.logFileName = f"{self.outputFileName.rsplit('.', 1)[0]}-log.txt"  # Set log file name based on output file name
                logging.info(f"Log File set to: {self.logFileName}")
                self.initLogFile()  # Initialize the log file

                # Load the GDS file using GDSDesign
                self.gds_design = GDSDesign(filename=self.inputFileName)
                self.layerData = [(str(layer['number']), layer_name) for layer_name, layer in self.gds_design.layers.items()]
                logging.info(f"Layers read from file: {self.layerData}")
                self.updateLayersComboBox()

                self.updateCellComboBox()

                self.showMatplotlibWindow()
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .gds file")
    
    def selectOtherGDSFile(self):
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No GDS design loaded.", QMessageBox.Ok)
            logging.error("No GDS design loaded.")
            return
        # Output: sets self.customFileName and self.custom_design, updates customTestCellComboBox
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Other .gds File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.gds'):
                self.customFileName = fileName
                self.custom_design = GDSDesign(filename=fileName)
                logging.info(f"Custom design loaded from: {fileName}")
                QMessageBox.information(self, "File Selected", f"Custom design loaded from: {fileName}", QMessageBox.Ok)
                
                if self.customFileName != self.inputFileName:
                    for cell in self.gds_design.lib.cells:
                        if cell in self.custom_design.lib.cells:
                            idstr = uuid.uuid4().hex[:8]
                            self.custom_design.lib.rename_cell(self.custom_design.lib.cells[cell], f"{cell}_custom_{idstr}", update_references=True)
                            logging.warning(f'Duplicate cell found. Renaming cell {cell} to {cell}_custom_{idstr}')

                # Populate the custom test cell combo box with cell names
                sorted_custom_keys = sorted(self.custom_design.lib.cells.keys(), key=lambda x: x.lower())
                self.customTestCellComboBox.clear()
                self.customTestCellComboBox.addItems(sorted_custom_keys)
                logging.info(f"Custom Test Structure cell names: {sorted_custom_keys}")

                self.resetOtherGDSButton.show()
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .gds file")

    def readPolygonPointsFile(self, fileName):
        # Output: sets self.polygon_points
        try:
            if fileName.lower().endswith('.txt'):
                points = np.loadtxt(fileName, delimiter=',')
            elif fileName.lower().endswith('.csv'):
                points = np.loadtxt(fileName, delimiter=',')
            points_list = [tuple(point) for point in points]
            if all(len(point) == 2 for point in points_list):
                self.polygon_points = points_list
                logging.info(f"Polygon Points read: {self.polygon_points}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            logging.error(f"Error reading polygon points file: {str(e)}")

    def readPathPointsFile(self, fileName):
        # Output: sets self.path_points
        try:
            if fileName.lower().endswith('.txt'):
                points = np.loadtxt(fileName, delimiter=',')
            elif fileName.lower().endswith('.csv'):
                points = np.loadtxt(fileName, delimiter=',')
            points_list = [tuple(point) for point in points]
            if all(len(point) == 2 for point in points_list):
                self.path_points = points_list
                logging.info(f"Path Points read: {self.path_points}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            logging.error(f"Error reading path points file: {str(e)}")

    def selectPolygonPointsFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Polygon Points File", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.txt') or fileName.lower().endswith('.csv'):
                self.readPolygonPointsFile(fileName)
                logging.info(f"Polygon Points File: {fileName}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .txt or .csv file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .txt or .csv file")

    def selectPathPointsFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Path Points File", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.txt') or fileName.lower().endswith('.csv'):
                self.readPathPointsFile(fileName)
                logging.info(f"Path Points File: {fileName}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .txt or .csv file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .txt or .csv file")

    def selectEscapeRoutingFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Escape Routing File", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.txt') or fileName.lower().endswith('.csv'):
                self.readEscapeRoutingPointsFile(fileName)
                logging.info(f"Escape Routing Points File: {fileName}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .txt or .csv file.", QMessageBox.Ok)
                logging.error("File selection error: Not a .txt or .csv file")

    def readEscapeRoutingPointsFile(self, fileName):
        try:
            if fileName.lower().endswith('.txt'):
                points = np.loadtxt(fileName, delimiter=',')
            elif fileName.lower().endswith('.csv'):
                points = np.loadtxt(fileName, delimiter=',')
            if all(len(point) == 2 for point in points):
                diff_x = np.diff(np.unique(points[:, 0]))
                diff_y = np.diff(np.unique(points[:, 1]))
                assert np.all(diff_x == diff_x[0]), "x coordinates are not evenly spaced"
                assert np.all(diff_y == diff_y[0]), "y coordinates are not evenly spaced"
                self.pitch_x = diff_x[0]
                self.pitch_y = diff_y[0]
                self.copies_x = len(np.unique(points[:, 0]))
                self.copies_y = len(np.unique(points[:, 1]))
                self.center_escape = (np.mean(np.unique(points[:, 0])), np.mean(np.unique(points[:, 1])))
                logging.info(f"Escape Routing Points read: center {self.center_escape}, pitch_x {self.pitch_x}, pitch_y {self.pitch_y}, copies_x {self.copies_x}, copies_y {self.copies_y}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            logging.error(f"Error reading escape routing points file: {str(e)}")
    
    def updateCellComboBox(self):
        sorted_keys = sorted(self.gds_design.cells.keys(), key=lambda x: x.lower())

        self.cellComboBox.clear()
        self.cellComboBox.addItems(sorted_keys)
        logging.info(f"Cell combo box populated with cells: {sorted_keys}")

        self.layerCellComboBox.clear()
        self.layerCellComboBox.addItems(sorted_keys)
        logging.info(f"Layer cell combo box populated with cells: {sorted_keys}")

        self.customTestCellComboBox.clear()
        if self.custom_design is None:
            self.customTestCellComboBox.addItems(sorted_keys)
            logging.info(f"Custom Test Structure combo box populated with cells: {sorted_keys}")
        else:
            sorted_custom_keys = sorted(self.custom_design.cells.keys(), key=lambda x: x.lower())
            self.customTestCellComboBox.addItems(sorted_custom_keys)
            logging.info(f"Custom Test Structure combo box populated with cells: {sorted_custom_keys}")

        self.placementCellComboBox.clear()
        self.placementCellComboBox.addItems(sorted_keys)
        logging.info(f"Placement combo box populated with cells: {sorted_keys}")

        for checkBox, cellComboBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            cellComboBox.clear()
            cellComboBox.addItems(sorted_keys)
            logging.info(f"Cell combo box populated for {checkBox.text()} test structure: {sorted_keys}")
                
    def updateLayersComboBox(self):
        self.layersComboBox.clear()
        self.plotLayersComboBox.clear()
        self.dicingStreetsLayerComboBox.clear()
        self.dieTextLayerComboBox.clear()
        self.subdicingStreetsLayerComboBox.clear()
        self.deepSiEtchingLayerComboBox.clear()
        # Add layers to the dropdown sorted by layer number
        self.layerData.sort(key=lambda x: int(x[0]))
        for number, name in self.layerData:
            self.layersComboBox.addItem(f"{number}: {name}")
            self.plotLayersComboBox.addItem(f"{number}: {name}")
            self.dicingStreetsLayerComboBox.addItem(f"{number}: {name}")
            self.dieTextLayerComboBox.addItem(f"{number}: {name}")
            self.subdicingStreetsLayerComboBox.addItem(f"{number}: {name}")
            self.deepSiEtchingLayerComboBox.addItem(f"{number}: {name}")
        logging.info("Layers dropdowns updated")

    def validateOutputFileName(self):
        # Output: sets self.outputFileName and renames log file if needed
        outputFileName = self.outFileField.text()
        if outputFileName.lower().endswith('.gds'):
            oldLogFileName = self.logFileName
            self.outputFileName = outputFileName
            self.logFileName = f"{outputFileName.rsplit('.', 1)[0]}-log.txt"  # Update log file name based on new output file name
            
            if os.path.exists(oldLogFileName):
                if os.path.exists(self.logFileName):
                    reply = QMessageBox.question(self, "Log File Exists", f"Log file {self.logFileName} already exists. Do you want to overwrite it?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        os.replace(oldLogFileName, self.logFileName)
                else:
                    os.rename(oldLogFileName, self.logFileName)  # Rename the existing log file to the new log file name
            else:
                self.initLogFile()
            
            logging.info(f"Output File set to: {self.outputFileName}")
            logging.info(f"Log File renamed to: {self.logFileName}")
        else:
            QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
            self.outFileField.setText(self.outputFileName)
            logging.info("Output file validation error: Not a .gds file")

    def initLogFile(self):
        with open(self.logFileName, 'w') as log_file:
            log_file.write("Test Structure Placement Log\n")
            log_file.write("============================\n\n")

    def storeParameterValue(self, comboBox, valueEdit, name):
        autoplace = False
        # See if Automatic Placement is set to True
        for _, _, cb, _, defaultParams, _ in self.testStructures:
            if cb == comboBox:
                if "Automatic Placement" in defaultParams:
                    if type(defaultParams["Automatic Placement"]) == str:
                        if defaultParams["Automatic Placement"].lower() == 'true':
                            autoplace = True
                    elif defaultParams["Automatic Placement"]:
                        autoplace = True
                break
        # Output: updates the defaultParams dictionary for the specific test structure and parameter
        param = comboBox.currentText()
        value = valueEdit.text()
        if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer":
            value = self.validateLayer(value)
        elif param == "Center" and not(autoplace) and name != "Rectangle" and not(name == "Escape Routing" and self.center_escape is not None and value == ''):
            value = self.validateCenter(value)
        for i, (checkBox, ccb, cb, edit, defaultParams, addButton) in enumerate(self.testStructures):
            if cb == comboBox:
                if param in defaultParams:
                    self.testStructures[i][4][param] = value
                    logging.info(f"{name} {param} updated to {value}")

    def validateLayer(self, layer):
        logging.info(f"Validating Layer: {layer}")
        layer = layer.strip()
        if layer.isdigit():
            layer_number = int(layer)
            for number, name in self.layerData:
                if int(number) == layer_number:
                    logging.info(f"Layer number {layer_number} is valid")
                    return int(number)  # Return the layer name instead of number
        else:
            for number, name in self.layerData:
                if name == layer:
                    logging.info(f"Layer name {layer} is valid")
                    return int(number)
        logging.error("Invalid layer")
        QMessageBox.critical(self, "Layer Error", "Invalid layer. Please select a valid layer.", QMessageBox.Ok)
        return None

    def validateCenter(self, center):
        logging.info(f"Validating Center: {center}")
        if not(center):
            QMessageBox.critical(self, "Center Error", "Please enter a center (x, y) coordinate.", QMessageBox.Ok)
            logging.error(f"Invalid center: {center}")
            return None
        if isinstance(center, tuple):
            return center
        center = center.replace("(", "").replace(")", "").replace(" ", "")
        try:
            x, y = map(float, center.split(','))
            logging.info(f"Center is valid: ({x}, {y})")
            return (x, y)
        except:
            logging.error(f"Invalid center {center}")
            QMessageBox.critical(self, "Center Error", "Invalid center. Please enter a valid (x, y) coordinate.", QMessageBox.Ok)
            return None

    def handleAddToDesign(self, testStructureName):
        # Make sure the checkbox is checked for this test structure
        for checkBox, cellComboBox, _, _, _, _ in self.testStructures:
            if checkBox.text() == testStructureName:
                if not checkBox.isChecked():
                    QMessageBox.critical(self, "Test Structure Error", f"Please check the '{testStructureName}' checkbox to add it to the design.", QMessageBox.Ok)
                    logging.error(f"Add to Design error: '{testStructureName}' checkbox not checked")
                    return
                cell_name = cellComboBox.currentText()
        logging.info(f"Adding {testStructureName} to design")
        self.addSnapshot()  # Store snapshot before adding new design
        params = self.getParameters(testStructureName)
        logging.info(f"Parameters: {params}")
        if params:
            if testStructureName == "MLA Alignment Mark":
                retval = self.addMLAAlignmentMark(cell_name, **params)
            elif testStructureName == "Resistance Test":
                retval = self.addResistanceTest(cell_name, **params)
            elif testStructureName == "Trace Test":
                retval = self.addTraceTest(cell_name, **params)
            elif testStructureName == "Interlayer Via Test":
                retval = self.addInterlayerViaTest(cell_name, **params)
            elif testStructureName == "Electronics Via Test":
                retval = self.addElectronicsViaTest(cell_name, **params)
            elif testStructureName == "Short Test":
                retval = self.addShortTest(cell_name, **params)
            elif testStructureName == "Custom Test Structure":
                retval = self.addCustomTestStructure(cell_name, **params)
            elif testStructureName == "Rectangle":
                retval = self.addRectangle(cell_name, **params)
            elif testStructureName == "Circle":
                retval = self.addCircle(cell_name, **params)
            elif testStructureName == "Text":
                retval = self.addText(cell_name, **params)
            elif testStructureName == "Polygon":
                retval = self.addPolygon(cell_name, **params)
            elif testStructureName == "Path":
                retval = self.addPath(cell_name, **params)
            elif testStructureName == "Escape Routing":
                retval = self.addEscapeRouting(cell_name, **params)
            elif testStructureName == "Connect Rows":
                retval = self.addConnectRows(cell_name, **params)
            
            if retval:
                # Write the design
                self.writeToGDS()
                # Update the available space
                self.updateAvailableSpace()

                self.update_plot_data()
            
            else:
                self.undo()

    def updateAvailableSpace(self):
        if type(self.substrateLayer) == int:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if substrate_name:
                self.availableSpace, self.allOtherPolygons = self.gds_design.update_available_space(substrate_name, self.availableSpace, self.allOtherPolygons, self.excludedLayers)
                logging.info(f"Available space updated.")
                logging.info(f"All other polygons updated.")

    def logTestStructure(self, name, params):
        with open(self.logFileName, 'a') as log_file:
            log_file.write(f"Component: {name}\n")
            for param, value in params.items():
                log_file.write(f"{param}: {value}\n")
            log_file.write("\n")

    def getParameters(self, testStructureName):
        params = {}
        autoplace = False
        # See if Automatic Placement is set to True
        for testCheckBox, cellComboBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if testCheckBox.text() == testStructureName:
                if "Automatic Placement" in defaultParams:
                    if type(defaultParams["Automatic Placement"]) == str:
                        if defaultParams["Automatic Placement"].lower() == 'true':
                            autoplace = True
                    elif defaultParams["Automatic Placement"]:
                        autoplace = True
                break

        for testCheckBox, cellComboBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if testCheckBox.text() == testStructureName:
                for param in self.parameters[testStructureName]:
                    value = defaultParams.get(param, '')
                    logging.info(f"Getting parameter {param}: {value}")
                    if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer" or (param == "Layer Name Short" and value):
                        # Lookup layer number and get name
                        layer_number = self.validateLayer(str(value))
                        if layer_number is None:
                            return
                        for number, name in self.layerData:
                            if int(number) == layer_number:
                                value = name
                    elif param == "Center" and testStructureName != "Rectangle" and not(autoplace) and not(testStructureName == "Escape Routing" and self.center_escape is not None and value == ''):
                        value = self.validateCenter(value)
                        if value is None:
                            return
                    elif type(value) == str:
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        elif value.lower() == 'none' or value.lower() == '':
                            value = None
                    params[param.replace(" ", "_")] = value
        return params
    
    def addConnectRows(self, Cell_Name, Layer, Row_1_Start, Row_1_End, Row_1_Spacing, Row_1_Constant, Row_2_Start, Row_2_End, Row_2_Spacing, Row_2_Constant, Orientation, Trace_Width, Escape_Extent):
        if Orientation is None:
            QMessageBox.critical(self, "Orientation Error", "Please enter an orientation for the connect rows.", QMessageBox.Ok)
            logging.error("Orientation Error: No orientation entered for connect rows")
            return False
        Orientation = Orientation.lower().strip()
        if Orientation == '-x':
            connect_negative = True
            connect_y = False
        elif Orientation == '+x':
            connect_negative = False
            connect_y = False
        elif Orientation == '-y':
            connect_negative = True
            connect_y = True
        elif Orientation == '+y':
            connect_negative = False
            connect_y = True
        else:
            QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
            logging.error("Orientation Error: Invalid orientation entered for connect rows")
            return False
        try:
            self.gds_design.connect_rows(
                cell_name=Cell_Name,
                layer_name=Layer,
                start1=float(Row_1_Start),
                end1=float(Row_1_End),
                spacing1=float(Row_1_Spacing),
                const1=float(Row_1_Constant),
                start2=float(Row_2_Start),
                end2=float(Row_2_End),
                spacing2=float(Row_2_Spacing),
                const2=float(Row_2_Constant),
                trace_width=float(Trace_Width),
                escape_extent=float(Escape_Extent),
                connect_y=connect_y,
                connect_negative=connect_negative
            )
            logging.info(f"Rows connected in {Cell_Name} on layer {Layer}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error connecting rows: {str(e)}", QMessageBox.Ok)
            logging.error(f"Error connecting rows: {str(e)}")
            return False

    def addEscapeRouting(self, Cell_Name, Layer, Center, Copies_X, Copies_Y, Pitch_X, Pitch_Y, Trace_Width, Trace_Space, Pad_Diameter, Orientation, Escape_Extent, Cable_Tie_Routing_Angle, Autorouting_Angle):
        if Orientation is None:
            QMessageBox.critical(self, "Orientation Error", "Please enter an orientation for the escape routing.", QMessageBox.Ok)
            logging.error("Orientation Error: No orientation entered for escape routing")
            return False
        Orientation = Orientation.lower()
        split = Orientation.split(',')
        if split[0].strip() == '1':
            if split[1].strip() == '-x':
                escape_y = False
                escape_negative = True
            elif split[1].strip() == '+x':
                escape_y = False
                escape_negative = False
            elif split[1].strip() == '-y':
                escape_y = True
                escape_negative = True
            elif split[1].strip() == '+y':
                escape_y = True
                escape_negative = False
            else:
                QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
                logging.error("Orientation Error: Invalid orientation entered for escape routing")
                return False
            
            try:
                escape_dict = self.gds_design.add_regular_array_escape_one_sided(
                    trace_cell_name=Cell_Name,
                    center=Center if Center else self.center_escape,
                    layer_name=Layer,
                    pitch_x=float(Pitch_X) if Pitch_X else self.pitch_x,
                    pitch_y=float(Pitch_Y) if Pitch_Y else self.pitch_y,
                    array_size_x=int(Copies_X) if Copies_X else self.copies_x,
                    array_size_y=int(Copies_Y) if Copies_Y else self.copies_y,
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y,
                    escape_negative=escape_negative,
                    escape_extent=float(Escape_Extent),
                    trace_space=float(Trace_Space) if Trace_Space else None,
                    cable_tie_routing_angle=float(Cable_Tie_Routing_Angle),
                    autorouting_angle=float(Autorouting_Angle)
                )
                if Cell_Name not in self.escapeDicts:
                    self.escapeDicts[Cell_Name] = []
                self.escapeDicts[Cell_Name].append(escape_dict)
                logging.info(f"One-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding one-sided escape: {str(e)}", QMessageBox.Ok)
                logging.error(f"One-sided escape placement error: {str(e)}")
                return False
            
        elif split[0].strip() == '2':
            if split[1].strip() == 'x':
                escape_y = False
            elif split[1].strip() == 'y':
                escape_y = True
            else:
                QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
                logging.error("Orientation Error: Invalid orientation entered for escape routing")
                return False

            try:
                escape_dict = self.gds_design.add_regular_array_escape_two_sided(
                    trace_cell_name=Cell_Name,
                    center=Center if Center else self.center_escape,
                    layer_name=Layer,
                    pitch_x=float(Pitch_X) if Pitch_X else self.pitch_x,
                    pitch_y=float(Pitch_Y) if Pitch_Y else self.pitch_y,
                    array_size_x=int(Copies_X) if Copies_X else self.copies_x,
                    array_size_y=int(Copies_Y) if Copies_Y else self.copies_y,
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y,
                    escape_extent=float(Escape_Extent),
                    trace_space=float(Trace_Space) if Trace_Space else None,
                    cable_tie_routing_angle=float(Cable_Tie_Routing_Angle),
                    autorouting_angle=float(Autorouting_Angle)
                )
                if Cell_Name not in self.escapeDicts:
                    self.escapeDicts[Cell_Name] = []
                self.escapeDicts[Cell_Name].append(escape_dict)
                logging.info(f"Two-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding two-sided escape: {str(e)}", QMessageBox.Ok)
                logging.error(f"Two-sided escape placement error: {str(e)}")
                return False
        elif split[0].strip() == '3':
            if split[1].strip() == '-x':
                escape_y = False
                escape_negative = True
            elif split[1].strip() == '+x':
                escape_y = False
                escape_negative = False
            elif split[1].strip() == '-y':
                escape_y = True
                escape_negative = True
            elif split[1].strip() == '+y':
                escape_y = True
                escape_negative = False
            else:
                QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
                logging.error("Orientation Error: Invalid orientation entered for escape routing")
                return False
            
            try:
                escape_dict = self.gds_design.add_regular_array_escape_three_sided(
                    trace_cell_name=Cell_Name,
                    center=Center if Center else self.center_escape,
                    layer_name=Layer,
                    pitch_x=float(Pitch_X) if Pitch_X else self.pitch_x,
                    pitch_y=float(Pitch_Y) if Pitch_Y else self.pitch_y,
                    array_size_x=int(Copies_X) if Copies_X else self.copies_x,
                    array_size_y=int(Copies_Y) if Copies_Y else self.copies_y,
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y,
                    escape_negative=escape_negative,
                    escape_extent=float(Escape_Extent),
                    trace_space=float(Trace_Space) if Trace_Space else None,
                    cable_tie_routing_angle=float(Cable_Tie_Routing_Angle),
                    autorouting_angle=float(Autorouting_Angle)
                )
                if Cell_Name not in self.escapeDicts:
                    self.escapeDicts[Cell_Name] = []
                self.escapeDicts[Cell_Name].append(escape_dict)
                logging.info(f"Three-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding three-sided escape: {str(e)}", QMessageBox.Ok)
                logging.error(f"Three-sided escape placement error: {str(e)}")
                return False
        elif split[0].strip() == '4':
            try:
                escape_dict = self.gds_design.add_regular_array_escape_four_sided(
                    trace_cell_name=Cell_Name,
                    center=Center if Center else self.center_escape,
                    layer_name=Layer,
                    pitch_x=float(Pitch_X) if Pitch_X else self.pitch_x,
                    pitch_y=float(Pitch_Y) if Pitch_Y else self.pitch_y,
                    array_size_x=int(Copies_X) if Copies_X else self.copies_x,
                    array_size_y=int(Copies_Y) if Copies_Y else self.copies_y,
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_extent=float(Escape_Extent),
                    trace_space=float(Trace_Space) if Trace_Space else None,
                    cable_tie_routing_angle=float(Cable_Tie_Routing_Angle),
                    autorouting_angle=float(Autorouting_Angle)
                )
                if Cell_Name not in self.escapeDicts:
                    self.escapeDicts[Cell_Name] = []
                self.escapeDicts[Cell_Name].append(escape_dict)
                logging.info(f"Four-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding four-sided escape: {str(e)}", QMessageBox.Ok)
                logging.error(f"Four-sided escape placement error: {str(e)}")
                return False
        else:
            QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
            logging.error("Orientation Error: Invalid orientation entered for escape routing")
            return False

    def addMLAAlignmentMark(self, Cell_Name, Layer, Center, Outer_Rect_Width, Outer_Rect_Height, Interior_Width, Interior_X_Extent, Interior_Y_Extent, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_MLA_alignment_mark(
                    cell_name=Cell_Name,
                    layer_name=Layer,
                    center=Center,
                    rect_width=float(Outer_Rect_Width),
                    rect_height=float(Outer_Rect_Height),
                    width_interior=float(Interior_Width),
                    extent_x_interior=float(Interior_X_Extent),
                    extent_y_interior=float(Interior_Y_Extent)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding MLA Alignment Mark: {str(e)}", QMessageBox.Ok)
                logging.error(f"MLA Alignment Mark placement error: {str(e)}")
                return False
        # If automatic placement is set to true, place the feature on a temporary cell, determine the size, and then place it on the top cell in a position where there is no overlap
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass  # If the cell doesn't exist, just ignore the error
            
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_MLA_alignment_mark(
                    cell_name=TEMP_CELL_NAME,
                    layer_name=Layer,
                    center=(0,0),
                    rect_width=float(Outer_Rect_Width),
                    rect_height=float(Outer_Rect_Height),
                    width_interior=float(Interior_Width),
                    extent_x_interior=float(Interior_X_Extent),
                    extent_y_interior=float(Interior_Y_Extent)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding MLA Alignment Mark: {str(e)}", QMessageBox.Ok)
                logging.error(f"MLA Alignment Mark placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("MLA Alignment Mark placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the MLA Alignment Mark. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("MLA Alignment Mark placement error: No space available")
                return False
            self.gds_design.add_MLA_alignment_mark(
                cell_name=Cell_Name,
                layer_name=Layer,
                center=Center,
                rect_width=float(Outer_Rect_Width),
                rect_height=float(Outer_Rect_Height),
                width_interior=float(Interior_Width),
                extent_x_interior=float(Interior_X_Extent),
                extent_y_interior=float(Interior_Y_Extent)
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("MLA Alignment Mark placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Outer Rect Width": Outer_Rect_Width,
            "Outer Rect Height": Outer_Rect_Height,
            "Interior Width": Interior_Width,
            "Interior X Extent": Interior_X_Extent,
            "Interior Y Extent": Interior_Y_Extent
        }
        self.logTestStructure("MLA Alignment Mark", params)  # Log the test structure details
        logging.info(f"MLA Alignment Mark added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addResistanceTest(self, Cell_Name, Layer, Center, Probe_Pad_Width, Probe_Pad_Height, Probe_Pad_Spacing, Plug_Width, Plug_Height, Trace_Width, Trace_Spacing, Switchbacks, X_Extent, Text_Height, Text, Add_Interlayer_Short, Layer_Name_Short, Short_Text, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_resistance_test_structure(
                    cell_name=Cell_Name,
                    layer_name=Layer,
                    center=Center,
                    probe_pad_width=float(Probe_Pad_Width),
                    probe_pad_height=float(Probe_Pad_Height),
                    probe_pad_spacing=float(Probe_Pad_Spacing),
                    plug_width=float(Plug_Width),
                    plug_height=float(Plug_Height),
                    trace_width=float(Trace_Width),
                    trace_spacing=float(Trace_Spacing),
                    switchbacks=int(Switchbacks),
                    x_extent=float(X_Extent),
                    text_height=float(Text_Height),
                    text=Text if Text else Layer,  # Use the layer name if text is not provided
                    add_interlayer_short=Add_Interlayer_Short,
                    short_text=Short_Text if Short_Text else Layer_Name_Short,  # Use the layer name for short text if not provided
                    layer_name_short=Layer_Name_Short
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Resistance Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Resistance Test placement error: {str(e)}")
                return False
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass
                
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_resistance_test_structure(
                    cell_name=TEMP_CELL_NAME,
                    layer_name=Layer,
                    center=(0,0),
                    probe_pad_width=float(Probe_Pad_Width),
                    probe_pad_height=float(Probe_Pad_Height),
                    probe_pad_spacing=float(Probe_Pad_Spacing),
                    plug_width=float(Plug_Width),
                    plug_height=float(Plug_Height),
                    trace_width=float(Trace_Width),
                    trace_spacing=float(Trace_Spacing),
                    switchbacks=int(Switchbacks),
                    x_extent=float(X_Extent),
                    text_height=float(Text_Height),
                    text=Text if Text else Layer,  # Use the layer name if text is not provided
                    add_interlayer_short=Add_Interlayer_Short,
                    short_text=Short_Text if Short_Text else Layer_Name_Short,  # Use the layer name for short text if not provided
                    layer_name_short=Layer_Name_Short
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Resistance Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Resistance Test placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("Resistance Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Resistance Test. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("Resistance Test placement error: No space available")
                return False
            self.gds_design.add_resistance_test_structure(
                cell_name=Cell_Name,
                layer_name=Layer,
                center=Center,
                probe_pad_width=float(Probe_Pad_Width),
                probe_pad_height=float(Probe_Pad_Height),
                probe_pad_spacing=float(Probe_Pad_Spacing),
                plug_width=float(Plug_Width),
                plug_height=float(Plug_Height),
                trace_width=float(Trace_Width),
                trace_spacing=float(Trace_Spacing),
                switchbacks=int(Switchbacks),
                x_extent=float(X_Extent),
                text_height=float(Text_Height),
                text=Text if Text else Layer,  # Use the layer name if text is not provided
                add_interlayer_short=Add_Interlayer_Short,
                short_text=Short_Text if Short_Text else Layer_Name_Short,  # Use the layer name for short text if not provided
                layer_name_short=Layer_Name_Short
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("Resistance Test placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Probe Pad Width": Probe_Pad_Width,
            "Probe Pad Height": Probe_Pad_Height,
            "Probe Pad Spacing": Probe_Pad_Spacing,
            "Plug Width": Plug_Width,
            "Plug Height": Plug_Height,
            "Trace Width": Trace_Width,
            "Trace Spacing": Trace_Spacing,
            "Switchbacks": Switchbacks,
            "X Extent": X_Extent,
            "Text Height": Text_Height,
            "Text": Text,
            "Add Interlayer Short": Add_Interlayer_Short,
            "Layer Name Short": Layer_Name_Short,
            "Short Text": Short_Text
        }
        self.logTestStructure("Resistance Test", params)  # Log the test structure details
        logging.info(f"Resistance Test added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addTraceTest(self, Cell_Name, Layer, Center, Text, Line_Width, Line_Height, Num_Lines, Line_Spacing, Text_Height, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_line_test_structure(
                    cell_name=Cell_Name,
                    layer_name=Layer,
                    center=Center,
                    text=Text if Text else f"{Layer} TRACE",  # Use the layer name if text is not provided
                    line_width=float(Line_Width),
                    line_height=float(Line_Height),
                    num_lines=int(Num_Lines),
                    line_spacing=float(Line_Spacing),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Trace Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Trace Test placement error: {str(e)}")
                return False
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass
                
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_line_test_structure(
                    cell_name=TEMP_CELL_NAME,
                    layer_name=Layer,
                    center=(0,0),
                    text=Text if Text else f"{Layer} TRACE",  # Use the layer name if text is not provided
                    line_width=float(Line_Width),
                    line_height=float(Line_Height),
                    num_lines=int(Num_Lines),
                    line_spacing=float(Line_Spacing),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Trace Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Trace Test placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("Trace Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Trace Test. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("Trace Test placement error: No space available")
                return False
            self.gds_design.add_line_test_structure(
                cell_name=Cell_Name,
                layer_name=Layer,
                center=Center,
                text=Text if Text else f"{Layer} TRACE",  # Use the layer name if text is not provided
                line_width=float(Line_Width),
                line_height=float(Line_Height),
                num_lines=int(Num_Lines),
                line_spacing=float(Line_Spacing),
                text_height=float(Text_Height)
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("Trace Test placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Text": Text,
            "Line Width": Line_Width,
            "Line Height": Line_Height,
            "Num Lines": Num_Lines,
            "Line Spacing": Line_Spacing,
            "Text Height": Text_Height
        }
        self.logTestStructure("Trace Test", params)  # Log the test structure details
        logging.info(f"Trace Test added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addInterlayerViaTest(self, Cell_Name, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rectangle_Spacing, Layer_1_Rectangle_Width, Layer_1_Rectangle_Height, Layer_2_Rectangle_Width, Layer_2_Rectangle_Height, Via_Width, Via_Height, Text_Height, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_p_via_test_structure(
                    cell_name=Cell_Name,
                    layer_name_1=Layer_Number_1,
                    layer_name_2=Layer_Number_2,
                    via_layer=Via_Layer,
                    center=Center,
                    text=Text if Text else "Interlayer Via",  # Use "Interlayer Via" if text is not provided
                    layer1_rect_spacing=float(Layer_1_Rectangle_Spacing),
                    layer1_rect_width=float(Layer_1_Rectangle_Width),
                    layer1_rect_height=float(Layer_1_Rectangle_Height),
                    layer2_rect_width=float(Layer_2_Rectangle_Width),
                    layer2_rect_height=float(Layer_2_Rectangle_Height),
                    via_width=float(Via_Width),
                    via_height=float(Via_Height),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Interlayer Via Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Interlayer Via Test placement error: {str(e)}")
                return False
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass
                
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_p_via_test_structure(
                    cell_name=TEMP_CELL_NAME,
                    layer_name_1=Layer_Number_1,
                    layer_name_2=Layer_Number_2,
                    via_layer=Via_Layer,
                    center=(0,0),
                    text=Text if Text else "Interlayer Via",  # Use "Interlayer Via" if text is not provided
                    layer1_rect_spacing=float(Layer_1_Rectangle_Spacing),
                    layer1_rect_width=float(Layer_1_Rectangle_Width),
                    layer1_rect_height=float(Layer_1_Rectangle_Height),
                    layer2_rect_width=float(Layer_2_Rectangle_Width),
                    layer2_rect_height=float(Layer_2_Rectangle_Height),
                    via_width=float(Via_Width),
                    via_height=float(Via_Height),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Interlayer Via Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Interlayer Via Test placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("Interlayer Via Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Interlayer Via Test. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("Interlayer Via Test placement error: No space available")
                return False
            self.gds_design.add_p_via_test_structure(
                cell_name=Cell_Name,
                layer_name_1=Layer_Number_1,
                layer_name_2=Layer_Number_2,
                via_layer=Via_Layer,
                center=Center,
                text=Text if Text else "Interlayer Via",  # Use "Interlayer Via" if text is not provided
                layer1_rect_spacing=float(Layer_1_Rectangle_Spacing),
                layer1_rect_width=float(Layer_1_Rectangle_Width),
                layer1_rect_height=float(Layer_1_Rectangle_Height),
                layer2_rect_width=float(Layer_2_Rectangle_Width),
                layer2_rect_height=float(Layer_2_Rectangle_Height),
                via_width=float(Via_Width),
                via_height=float(Via_Height),
                text_height=float(Text_Height)
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("Interlayer Via Test placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer Number 1": Layer_Number_1,
            "Layer Number 2": Layer_Number_2,
            "Via Layer": Via_Layer,
            "Center": Center,
            "Text": Text,
            "Layer 1 Rectangle Spacing": Layer_1_Rectangle_Spacing,
            "Layer 1 Rectangle Width": Layer_1_Rectangle_Width,
            "Layer 1 Rectangle Height": Layer_1_Rectangle_Height,
            "Layer 2 Rectangle Width": Layer_2_Rectangle_Width,
            "Layer 2 Rectangle Height": Layer_2_Rectangle_Height,
            "Via Width": Via_Width,
            "Via Height": Via_Height,
            "Text Height": Text_Height
        }
        self.logTestStructure("Interlayer Via Test", params)  # Log the test structure details
        logging.info(f"Interlayer Via Test added to {Cell_Name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")
        return True
    
    def addRectangle(self, Cell_Name, Layer, Center, Width, Height, Lower_Left, Upper_Right, Rotation):
        if (not Width or not Height or not Center) and (not Lower_Left or not Upper_Right):
            QMessageBox.critical(self, "Input Error", "Please enter either width and height or lower left and upper right coordinates for the rectangle.", QMessageBox.Ok)
            logging.error("Rectangle add error: No dimensions provided")
            return False
        try:
            self.gds_design.add_rectangle(
                cell_name=Cell_Name,
                layer_name=Layer,
                center=self.validateCenter(Center) if Center else None,
                width=float(Width) if Width else None,
                height=float(Height) if Height else None,
                lower_left=self.validateCenter(Lower_Left) if Lower_Left else None,
                upper_right=self.validateCenter(Upper_Right) if Upper_Right else None,
                rotation=float(Rotation)*math.pi/180
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Rectangle: {str(e)}", QMessageBox.Ok)
            logging.error(f"Rectangle placement error: {str(e)}")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Width": Width,
            "Height": Height,
            "Lower Left": Lower_Left,
            "Upper Right": Upper_Right,
            "Rotation": Rotation
        }
        self.logTestStructure("Rectangle", params)  # Log the test structure details
        logging.info(f"Rectangle added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addCircle(self, Cell_Name, Layer, Center, Diameter):
        if not Diameter:
            QMessageBox.critical(self, "Input Error", "Please enter a diameter for the circle.", QMessageBox.Ok)
            logging.error("Circle add error: No diameter provided")
            return False
        try:
            self.gds_design.add_circle_as_polygon(
                cell_name=Cell_Name,
                center=Center,
                radius=float(Diameter)/2,
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Circle: {str(e)}", QMessageBox.Ok)
            logging.error(f"Circle placement error: {str(e)}")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Diameter": Diameter
        }
        self.logTestStructure("Circle", params)  # Log the test structure details
        logging.info(f"Circle added to {Cell_Name} on layer {Layer} at center {Center}")
        return True
    
    def addText(self, Cell_Name, Layer, Center, Text, Height, Rotation):

        # Calculate the width and height of the text
        text_width = len(Text) * float(Height) * TEXT_SPACING_FACTOR
        text_height = float(Height) * TEXT_HEIGHT_FACTOR

        # Calculate the lower-left corner position relative to the center without rotation
        ll_x = Center[0] - (text_width / 2)
        ll_y = Center[1] - (text_height / 2)

        # Apply rotation to the lower-left position
        angle_rad = math.radians(float(Rotation))
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)

        # Translate the lower-left corner to the origin, apply rotation, then translate back
        delta_x = ll_x - Center[0]
        delta_y = ll_y - Center[1]
        rotated_x = Center[0] + (delta_x * cos_angle - delta_y * sin_angle)
        rotated_y = Center[1] + (delta_x * sin_angle + delta_y * cos_angle)

        # Add the text at the calculated position
        try:
            self.gds_design.add_text(
                cell_name=Cell_Name,
                text=Text,
                layer_name=Layer,
                position=(rotated_x, rotated_y),
                height=float(Height),
                angle=float(Rotation)
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Text: {str(e)}", QMessageBox.Ok)
            logging.error(f"Text placement error: {str(e)}")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Text": Text,
            "Height": Height,
            "Rotation": Rotation
        }
        self.logTestStructure("Text", params)  # Log the test structure details
        logging.info(f"Text {Text} added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addPolygon(self, Cell_Name, Layer):
        Points = self.polygon_points
        if len(Points) < 3:
            QMessageBox.critical(self, "Input Error", "Please select a valid polygon points file.", QMessageBox.Ok)
            logging.error("Polygon add error: Invalid points provided")
            return False
        try:
            self.gds_design.add_polygon(
                cell_name=Cell_Name,
                points=Points,
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Polygon: {str(e)}", QMessageBox.Ok)
            logging.error(f"Polygon placement error: {str(e)}")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Points": Points
        }
        self.logTestStructure("Polygon", params)  # Log the test structure details
        logging.info(f"Polygon added to {Cell_Name} on layer {Layer}")
        return True

    def addPath(self, Cell_Name, Layer, Width):
        Points = self.path_points
        if len(Points) < 2:
            QMessageBox.critical(self, "Input Error", "Please select a valid path points file.", QMessageBox.Ok)
            logging.error("Path add error: No points provided")
            return False
        if not Width:
            QMessageBox.critical(self, "Input Error", "Please enter a width for the path.", QMessageBox.Ok)
            logging.error("Path add error: No width provided")
            return False
        try:
            self.gds_design.add_path_as_polygon(
                cell_name=Cell_Name,
                points=Points,
                width=float(Width),
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Path: {str(e)}", QMessageBox.Ok)
            logging.error(f"Path placement error: {str(e)}")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Points": Points,
            "Width": Width
        }
        self.logTestStructure("Path", params)  # Log the test structure details
        logging.info(f"Path added to {Cell_Name} on layer {Layer}")
        return True

    def addElectronicsViaTest(self, Cell_Name, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rect_Width, Layer_1_Rect_Height, Layer_2_Rect_Width, Layer_2_Rect_Height, Layer_2_Rect_Spacing, Via_Width, Via_Height, Via_Spacing, Text_Height, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_electronics_via_test_structure(
                    cell_name=Cell_Name,
                    layer_name_1=Layer_Number_1,
                    layer_name_2=Layer_Number_2,
                    via_layer=Via_Layer,
                    center=Center,
                    text=Text if Text else "ELECTRONICS VIA TEST",  # Use "ELECTRONICS VIA TEST" if text is not provided
                    layer_1_rect_width=float(Layer_1_Rect_Width),
                    layer_1_rect_height=float(Layer_1_Rect_Height),
                    layer_2_rect_width=float(Layer_2_Rect_Width),
                    layer_2_rect_height=float(Layer_2_Rect_Height),
                    layer_2_rect_spacing=float(Layer_2_Rect_Spacing),
                    via_width=float(Via_Width),
                    via_height=float(Via_Height),
                    via_spacing=float(Via_Spacing),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Electronics Via Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Electronics Via Test placement error: {str(e)}")
                return False
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass
                
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_electronics_via_test_structure(
                    cell_name=TEMP_CELL_NAME,
                    layer_name_1=Layer_Number_1,
                    layer_name_2=Layer_Number_2,
                    via_layer=Via_Layer,
                    center=(0,0),
                    text=Text if Text else "ELECTRONICS VIA TEST",  # Use "ELECTRONICS VIA TEST" if text is not provided
                    layer_1_rect_width=float(Layer_1_Rect_Width),
                    layer_1_rect_height=float(Layer_1_Rect_Height),
                    layer_2_rect_width=float(Layer_2_Rect_Width),
                    layer_2_rect_height=float(Layer_2_Rect_Height),
                    layer_2_rect_spacing=float(Layer_2_Rect_Spacing),
                    via_width=float(Via_Width),
                    via_height=float(Via_Height),
                    via_spacing=float(Via_Spacing),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Electronics Via Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Electronics Via Test placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("Electronics Via Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Electronics Via Test. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("Electronics Via Test placement error: No space available")
                return False
            self.gds_design.add_electronics_via_test_structure(
                cell_name=Cell_Name,
                layer_name_1=Layer_Number_1,
                layer_name_2=Layer_Number_2,
                via_layer=Via_Layer,
                center=Center,
                text=Text if Text else "ELECTRONICS VIA TEST",  # Use "ELECTRONICS VIA TEST" if text is not provided
                layer_1_rect_width=float(Layer_1_Rect_Width),
                layer_1_rect_height=float(Layer_1_Rect_Height),
                layer_2_rect_width=float(Layer_2_Rect_Width),
                layer_2_rect_height=float(Layer_2_Rect_Height),
                layer_2_rect_spacing=float(Layer_2_Rect_Spacing),
                via_width=float(Via_Width),
                via_height=float(Via_Height),
                via_spacing=float(Via_Spacing),
                text_height=float(Text_Height)
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("Electronics Via Test placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer Number 1": Layer_Number_1,
            "Layer Number 2": Layer_Number_2,
            "Via Layer": Via_Layer,
            "Center": Center,
            "Text": Text,
            "Layer 1 Rectangle Width": Layer_1_Rect_Width,
            "Layer 1 Rectangle Height": Layer_1_Rect_Height,
            "Layer 2 Rectangle Width": Layer_2_Rect_Width,
            "Layer 2 Rectangle Height": Layer_2_Rect_Height,
            "Layer 2 Rectangle Spacing": Layer_2_Rect_Spacing,
            "Via Width": Via_Width,
            "Via Height": Via_Height,
            "Via Spacing": Via_Spacing,
            "Text Height": Text_Height
        }
        self.logTestStructure("Electronics Via Test", params)  # Log the test structure details
        logging.info(f"Electronics Via Test added to {Cell_Name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")
        return True

    def addShortTest(self, Cell_Name, Layer, Center, Text, Rect_Width, Trace_Width, Num_Lines, Group_Spacing, Num_Groups, Num_Lines_Vert, Text_Height, Automatic_Placement):
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if type(Center) == tuple:
            try:
                self.gds_design.add_short_test_structure(
                    cell_name=Cell_Name,
                    layer_name=Layer,
                    center=Center,
                    text=Text if Text else f"{Layer} SHORT TEST",  # Use the layer name if text is not provided
                    rect_width=float(Rect_Width),
                    trace_width=float(Trace_Width),
                    num_lines=int(Num_Lines),
                    group_spacing=float(Group_Spacing),
                    num_groups=int(Num_Groups),
                    num_lines_vert=int(Num_Lines_Vert),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Short Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Short Test placement error: {str(e)}")
                return False
        elif Automatic_Placement:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass
                
            self.gds_design.add_cell(TEMP_CELL_NAME)
            try:
                self.gds_design.add_short_test_structure(
                    cell_name=TEMP_CELL_NAME,
                    layer_name=Layer,
                    center=(0,0),
                    text=Text if Text else f"{Layer} SHORT TEST",  # Use the layer name if text is not provided
                    rect_width=float(Rect_Width),
                    trace_width=float(Trace_Width),
                    num_lines=int(Num_Lines),
                    group_spacing=float(Group_Spacing),
                    num_groups=int(Num_Groups),
                    num_lines_vert=int(Num_Lines_Vert),
                    text_height=float(Text_Height)
                )
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Short Test: {str(e)}", QMessageBox.Ok)
                logging.error(f"Short Test placement error: {str(e)}")
                return False
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                logging.error("Short Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Short Test. You may need to exclude a layer?", QMessageBox.Ok)
                logging.error("Short Test placement error: No space available")
                return False
            self.gds_design.add_short_test_structure(
                cell_name=Cell_Name,
                layer_name=Layer,
                center=Center,
                text=Text if Text else f"{Layer} SHORT TEST",  # Use the layer name if text is not provided
                rect_width=float(Rect_Width),
                trace_width=float(Trace_Width),
                num_lines=int(Num_Lines),
                group_spacing=float(Group_Spacing),
                num_groups=int(Num_Groups),
                num_lines_vert=int(Num_Lines_Vert),
                text_height=float(Text_Height)
            )
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            logging.error("Short Test placement error: Center position not specified")
            return False
        params = {
            "Cell Name": Cell_Name,
            "Layer": Layer,
            "Center": Center,
            "Text": Text,
            "Rect Width": Rect_Width,
            "Trace Width": Trace_Width,
            "Num Lines": Num_Lines,
            "Group Spacing": Group_Spacing,
            "Num Groups": Num_Groups,
            "Num Lines Vert": Num_Lines_Vert,
            "Text Height": Text_Height
        }
        self.logTestStructure("Short Test", params)  # Log the test structure details
        logging.info(f"Short Test added to {Cell_Name} on layer {Layer} at center {Center}")
        return True

    def addCustomTestStructure(self, Parent_Cell_Name, Center, Magnification, Rotation, X_Reflection, Array, Copies_X, Copies_Y, Pitch_X, Pitch_Y, Automatic_Placement):
        if type(Array) != bool and Array is not None:
            QMessageBox.critical(self, "Array Placement Error", "Please enter 'True' or 'False' for Array.", QMessageBox.Ok)
            logging.error("Array Placement Error: Invalid value entered for Array")
            return False
        if type(X_Reflection) != bool and X_Reflection is not None:
            QMessageBox.critical(self, "Placement Error", "Please enter 'True' or 'False' for X Reflection.", QMessageBox.Ok)
            logging.error("Placement Error: Invalid value entered for X Reflection")
            return False
        if type(Automatic_Placement) != bool and Automatic_Placement is not None:
            QMessageBox.critical(self, "Automatic Placement Error", "Please enter 'True' or 'False' for Automatic Placement.", QMessageBox.Ok)
            logging.error("Automatic Placement Error: Invalid value entered for Automatic Placement")
            return False
        if Parent_Cell_Name == "":
            QMessageBox.critical(self, "Parent Cell Name Error", "Please enter a parent cell name.", QMessageBox.Ok)
            logging.error("Custom Test Structure placement error: No parent cell name provided")
            return False
        # If the custom cell is from another file, add it to the current design
        if self.custom_design is not None:
            if self.customTestCellName not in self.gds_design.lib.cells:
                if not self.customTestCellName:
                    QMessageBox.critical(self, "Custom Test Structure Error", "Please select a custom test structure cell name.", QMessageBox.Ok)
                    logging.error("Custom Test Structure placement error: No cell name provided")
                    return False
                self.gds_design.lib.add(self.custom_design.lib.cells[self.customTestCellName],
                                    overwrite_duplicate=True, include_dependencies=True, update_references=False)
                unique_layers = set()
                for cell_name in self.gds_design.lib.cells.keys():
                    if cell_name != '$$$CONTEXT_INFO$$$':
                        polygons_by_spec = self.gds_design.lib.cells[cell_name].get_polygons(by_spec=True)
                        for (lay, dat), polys in polygons_by_spec.items():
                            unique_layers.add(lay)
                
                for layer_number in unique_layers:
                    continueFlag = False
                    for number, name in self.layerData:
                        if int(number) == layer_number:
                            continueFlag = True
                            break
                    if continueFlag:
                        continue
                    self.gds_design.define_layer(str(layer_number), layer_number)
                    logging.info(f"Layer defined: {layer_number} with number {layer_number}")
                    
                    # Add new layer if it doesn't exist already
                    self.layerData.append((str(layer_number), str(layer_number)))
                    logging.info(f"New Layer added: {layer_number} - {layer_number}")

                logging.info(f"Current layers: {self.gds_design.layers}")
                self.updateLayersComboBox()

        if self.customTestCellName:
            if not Array:
                if type(Center) == tuple:
                    try:
                        self.gds_design.add_cell_reference(
                            parent_cell_name=Parent_Cell_Name,
                            child_cell_name=self.customTestCellName,
                            origin=Center,
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure: {str(e)}", QMessageBox.Ok)
                        logging.error(f"Custom Test Structure placement error: {str(e)}")
                        return False
                elif Automatic_Placement:
                    try:
                        self.gds_design.delete_cell(TEMP_CELL_NAME)
                    except ValueError:
                        pass
                        
                    self.gds_design.add_cell(TEMP_CELL_NAME)
                    try:
                        self.gds_design.add_cell_reference(
                            parent_cell_name=TEMP_CELL_NAME,
                            child_cell_name=self.customTestCellName,
                            origin=(0,0),
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure: {str(e)}", QMessageBox.Ok)
                        logging.error(f"Custom Test Structure placement error: {str(e)}")
                        return False
                    cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
                    self.gds_design.delete_cell(TEMP_CELL_NAME)
                    # Get substrate layer name from layer number:
                    substrate_name = None
                    for number, name in self.layerData:
                        if int(number) == self.substrateLayer:
                            substrate_name = name
                    if not substrate_name:
                        QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                        logging.error("Custom Test Structure placement error: Substrate layer not set")
                        return False
                    available_space = self.availableSpace
                    try:
                        Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
                    except ValueError:
                        QMessageBox.critical(self, "Placement Error", "No space available for the Custom Test Structure. You may need to exclude a layer?", QMessageBox.Ok)
                        logging.error("Custom Test Structure placement error: No space available")
                        return False
                    self.gds_design.add_cell_reference(
                        parent_cell_name=Parent_Cell_Name,
                        child_cell_name=self.customTestCellName,
                        origin=Center,
                        magnification=float(Magnification),
                        rotation=float(Rotation),
                        x_reflection=X_Reflection
                    )
                else:
                    # Show error message that either Automatic Placement must be true or the Center position is specified
                    QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
                    logging.error("Custom Test Structure placement error: Center position not specified")
                    return False
                params = {
                    "Parent Cell Name": Parent_Cell_Name,
                    "Child Cell Name": self.customTestCellName,
                    "Center": Center,
                    "Magnification": Magnification,
                    "Rotation": Rotation,
                    "X Reflection": X_Reflection
                }
                self.logTestStructure("Custom Test Structure", params)  # Log the test structure details
                logging.info(f"Custom Test Structure '{self.customTestCellName}' added to {Parent_Cell_Name} at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}")
                
                return True
            else:
                if type(Center) == tuple:
                    try:
                        self.gds_design.add_cell_array(
                            target_cell_name=Parent_Cell_Name,
                            cell_name_to_array=self.customTestCellName,
                            copies_x=int(Copies_X),
                            copies_y=int(Copies_Y),
                            spacing_x=float(Pitch_X),
                            spacing_y=float(Pitch_Y),
                            origin=Center,
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure Array: {str(e)}", QMessageBox.Ok)
                        logging.error(f"Custom Test Structure Array placement error: {str(e)}")
                        return False
                elif Automatic_Placement:
                    try:
                        self.gds_design.delete_cell(TEMP_CELL_NAME)
                    except ValueError:
                        pass
                        
                    self.gds_design.add_cell(TEMP_CELL_NAME)
                    try:
                        self.gds_design.add_cell_array(
                            target_cell_name=TEMP_CELL_NAME,
                            cell_name_to_array=self.customTestCellName,
                            copies_x=int(Copies_X),
                            copies_y=int(Copies_Y),
                            spacing_x=float(Pitch_X),
                            spacing_y=float(Pitch_Y),
                            origin=(0,0),
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure Array: {str(e)}", QMessageBox.Ok)
                        logging.error(f"Custom Test Structure Array placement error: {str(e)}")
                        return False
                    cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
                    self.gds_design.delete_cell(TEMP_CELL_NAME)
                    # Get substrate layer name from layer number:
                    substrate_name = None
                    for number, name in self.layerData:
                        if int(number) == self.substrateLayer:
                            substrate_name = name
                    if not substrate_name:
                        QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                        logging.error("Custom Test Structure placement error: Substrate layer not set")
                        return False
                    available_space = self.availableSpace
                    try:
                        Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
                    except ValueError:
                        QMessageBox.critical(self, "Placement Error", "No space available for the Custom Test Structure. You may need to exclude a layer?", QMessageBox.Ok)
                        logging.error("Custom Test Structure placement error: No space available")
                        return False
                    self.gds_design.add_cell_array(
                        target_cell_name=Parent_Cell_Name,
                        cell_name_to_array=self.customTestCellName,
                        copies_x=int(Copies_X),
                        copies_y=int(Copies_Y),
                        spacing_x=float(Pitch_X),
                        spacing_y=float(Pitch_Y),
                        origin=Center,
                        magnification=float(Magnification),
                        rotation=float(Rotation),
                        x_reflection=X_Reflection
                    )
                else:
                    # Show error message that either Automatic Placement must be true or the Center position is specified
                    QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
                    logging.error("Custom Test Structure placement error: Center position not specified")
                    return False
                params = {
                    "Parent Cell Name": Parent_Cell_Name,
                    "Child Cell Name": self.customTestCellName,
                    "Center": Center,
                    "Magnification": Magnification,
                    "Rotation": Rotation,
                    "X Reflection": X_Reflection,
                    "Copies X": Copies_X,
                    "Copies Y": Copies_Y,
                    "Pitch X": Pitch_X,
                    "Pitch Y": Pitch_Y
                }
                self.logTestStructure("Custom Test Structure Array", params)  # Log the test structure details
                logging.info(f"Custom Test Structure '{self.customTestCellName}' added to {Parent_Cell_Name} as an array at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}, copies x {Copies_X}, copies y {Copies_Y}, pitch x {Pitch_X}, pitch y {Pitch_Y}")
                return True
            
    def handleCustomTestCellName(self):
        self.customTestCellName = self.customTestCellComboBox.currentText()
        logging.info(f"Custom Test Structure Cell Name set to: {self.customTestCellName}")
        self.checkCustomTestCell()

    def checkCustomTestCell(self):
        if self.customTestCellName:
            if self.custom_design is not None:
                if self.customTestCellName in self.custom_design.lib.cells:
                    logging.info(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
                else:
                    QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)
                    logging.error(f"Custom Test Structure Cell '{self.customTestCellName}' not found in design")
            else:
                if self.customTestCellName in self.gds_design.lib.cells:
                    logging.info(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
                else:
                    QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)
                    logging.error(f"Custom Test Structure Cell '{self.customTestCellName}' not found in design")
        else:
            QMessageBox.critical(self, "Input Error", "Please select a Custom Test Structure Cell Name.", QMessageBox.Ok)
            logging.error("Custom Test Structure Cell Name not selected")

    def writeToGDS(self):
        if self.gds_design:
            outputFileName = self.outFileField.text()
            if outputFileName.lower().endswith('.gds'):
                self.gds_design.write_gds(outputFileName)
                logging.info(f"GDS file written to {outputFileName}")
            else:
                QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
                logging.info("Output file write error: Not a .gds file")
        else:
            QMessageBox.critical(self, "Design Error", "No design loaded to write to GDS.", QMessageBox.Ok)
            logging.error("Write to GDS error: No design loaded")

    def defineNewLayer(self):
        number = self.newLayerNumberEdit.text().strip()
        name = self.newLayerNameEdit.text().strip()
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No design loaded to define a new layer.", QMessageBox.Ok)
            logging.error("Layer definition error: No design loaded")
            return
        if number and name:
            # Define the new layer using GDSDesign
            self.gds_design.define_layer(name, int(number))
            logging.info(f"Layer defined: {name} with number {number}")
            
            # Check if layer already exists and update name if so
            for i, (layer_number, layer_name) in enumerate(self.layerData):
                if layer_number == number:
                    old_name = self.layerData[i][1]
                    self.layerData[i] = (number, name)
                    self.updateLayersComboBox()
                    logging.info(f"Layer {number} name updated from {old_name} to {name}")
                    logging.info(f"Current layers: {self.gds_design.layers}")
                    return
            
            # Add new layer if it doesn't exist already
            self.layerData.append((number, name))
            self.updateLayersComboBox()
            logging.info(f"New Layer added: {number} - {name}")
            logging.info(f"Current layers: {self.gds_design.layers}")
        else:
            QMessageBox.critical(self, "Input Error", "Please enter both Layer Number and Layer Name.", QMessageBox.Ok)
            logging.error("Layer definition error: Missing layer number or name")

def log_unhandled_exception(exctype, value, tb):
    logging.error("Unhandled exception", exc_info=(exctype, value, tb))

    # Show the error message in a message box
    QMessageBox.critical(None, "Error", f"An unhandled exception occurred:\n{value}", QMessageBox.Ok)
    
    # Exit the application after showing the error
    sys.exit(1)

if __name__ == '__main__':
    setup_logging()
    logging.info("Starting the application...")

    parser = argparse.ArgumentParser(description='Run the PyQt5 GUI application.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose mode')
    args = parser.parse_args()

    sys.excepthook = log_unhandled_exception

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path('favicon.ico')))  # Set the application icon here
    ex = MyApp(verbose=True)

    # Connect aboutToQuit signal for additional cleanup or logging
    app.aboutToQuit.connect(lambda: logging.info('Application is exiting.'))

    sys.exit(app.exec_())
