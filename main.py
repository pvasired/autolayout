import sys
import argparse
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit, QFileDialog, QMessageBox, QComboBox, QGridLayout, QToolTip
)
from PyQt5.QtCore import Qt
from gdswriter import GDSDesign  # Import the GDSDesign class
from copy import deepcopy
import math
import numpy as np
import os

TEXT_SPACING_FACTOR = 0.55
TEXT_HEIGHT_FACTOR = 0.7
TEMP_CELL_NAME = "SIZE CHECK TEMP"

class TooltipComboBox(QComboBox):
    def __init__(self, tooltips=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tooltips = tooltips or {}
        self.view().viewport().installEventFilter(self)

    def setItemTooltips(self, tooltips):
        self.tooltips = tooltips

    def eventFilter(self, source, event):
        if event.type() == event.MouseMove and source is self.view().viewport():
            index = self.view().indexAt(event.pos()).row()
            if index >= 0 and index < len(self.tooltips):
                QToolTip.showText(event.globalPos(), self.tooltips[index], self.view().viewport())
            else:
                QToolTip.hideText()
        return super().eventFilter(source, event)

class MyApp(QWidget):
    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose
        self.inputFileName = ""
        self.outputFileName = ""
        self.customTestCellName = ""
        self.logFileName = ""
        self.substrateLayer = None
        self.layerData = []  # To store layer numbers and names
        self.testStructureNames = [
            "MLA Alignment Mark", "Resistance Test", "Trace Test", 
            "Interlayer Via Test", "Electronics Via Test", "Short Test", 
            "Rectangle", "Circle", "Text", "Polygon", "Path", "Custom Test Structure"
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
            "Custom Test Structure": ["Center", "Magnification", "Rotation", "X Reflection", "Array", "Copies X", "Copies Y", "Spacing X", "Spacing Y", "Automatic Placement"]
        }
        self.paramTooltips = {
            "MLA Alignment Mark": {
                "Layer": "Select the layer for the alignment mark.",
                "Center": "Enter the center (x, y) coordinate of the alignment mark.",
                "Outer Rect Width": "Enter the width of the outer rectangle.",
                "Outer Rect Height": "Enter the height of the outer rectangle.",
                "Interior Width": "Enter the width of the interior lines.",
                "Interior X Extent": "Enter the extent of the interior lines in the x direction.",
                "Interior Y Extent": "Enter the extent of the interior lines in the y direction.",
                "Automatic Placement": "Check to automatically place the alignment mark."
            },
            "Resistance Test": {
                "Layer": "Select the layer for the resistance test structure.",
                "Center": "Enter the center (x, y) coordinate of the resistance test structure.",
                "Probe Pad Width": "Enter the width of the probe pad.",
                "Probe Pad Height": "Enter the height of the probe pad.",
                "Probe Pad Spacing": "Enter the spacing between probe pads.",
                "Plug Width": "Enter the width of the plug.",
                "Plug Height": "Enter the height of the plug.",
                "Trace Width": "Enter the width of the traces.",
                "Trace Spacing": "Enter the spacing between traces.",
                "Switchbacks": "Enter the number of switchbacks.",
                "X Extent": "Enter the extent of the structure in the x direction.",
                "Text Height": "Enter the height of the text.",
                "Text": "Enter the text to display on the structure.",
                "Add Interlayer Short": "Check to add an interlayer short.",
                "Layer Name Short": "Enter the name of the short layer.",
                "Short Text": "Enter the text to display for the short.",
                "Automatic Placement": "Check to automatically place the resistance test structure."
            },
            "Trace Test": {
                "Layer": "Select the layer for the trace test structure.",
                "Center": "Enter the center (x, y) coordinate of the trace test structure.",
                "Text": "Enter the text to display on the structure.",
                "Line Width": "Enter the width of the lines.",
                "Line Height": "Enter the height of the lines.",
                "Num Lines": "Enter the number of lines.",
                "Line Spacing": "Enter the spacing between lines.",
                "Text Height": "Enter the height of the text.",
                "Automatic Placement": "Check to automatically place the trace test structure."
            },
            "Interlayer Via Test": {
                "Layer Number 1": "Select the first layer for the interlayer via test structure.",
                "Layer Number 2": "Select the second layer for the interlayer via test structure.",
                "Via Layer": "Select the via layer for the interlayer via test structure.",
                "Center": "Enter the center (x, y) coordinate of the interlayer via test structure.",
                "Text": "Enter the text to display on the structure.",
                "Layer 1 Rectangle Spacing": "Enter the spacing between rectangles on layer 1.",
                "Layer 1 Rectangle Width": "Enter the width of the rectangles on layer 1.",
                "Layer 1 Rectangle Height": "Enter the height of the rectangles on layer 1.",
                "Layer 2 Rectangle Width": "Enter the width of the rectangles on layer 2.",
                "Layer 2 Rectangle Height": "Enter the height of the rectangles on layer 2.",
                "Via Width": "Enter the width of the vias.",
                "Via Height": "Enter the height of the vias.",
                "Text Height": "Enter the height of the text.",
                "Automatic Placement": "Check to automatically place the interlayer via test structure."
            },
            "Electronics Via Test": {
                "Layer Number 1": "Select the first layer for the electronics via test structure.",
                "Layer Number 2": "Select the second layer for the electronics via test structure.",
                "Via Layer": "Select the via layer for the electronics via test structure.",
                "Center": "Enter the center (x, y) coordinate of the electronics via test structure.",
                "Text": "Enter the text to display on the structure.",
                "Layer 1 Rect Width": "Enter the width of the rectangles on layer 1.",
                "Layer 1 Rect Height": "Enter the height of the rectangles on layer 1.",
                "Layer 2 Rect Width": "Enter the width of the rectangles on layer 2.",
                "Layer 2 Rect Height": "Enter the height of the rectangles on layer 2.",
                "Layer 2 Rect Spacing": "Enter the spacing between rectangles on layer 2.",
                "Via Width": "Enter the width of the vias.",
                "Via Height": "Enter the height of the vias.",
                "Via Spacing": "Enter the spacing between vias.",
                "Text Height": "Enter the height of the text.",
                "Automatic Placement": "Check to automatically place the electronics via test structure."
            },
            "Short Test": {
                "Layer": "Select the layer for the short test structure.",
                "Center": "Enter the center (x, y) coordinate of the short test structure.",
                "Text": "Enter the text to display on the structure.",
                "Rect Width": "Enter the width of the rectangles.",
                "Trace Width": "Enter the width of the traces.",
                "Num Lines": "Enter the number of lines.",
                "Group Spacing": "Enter the spacing between groups.",
                "Num Groups": "Enter the number of groups.",
                "Num Lines Vert": "Enter the number of lines in the vertical direction.",
                "Text Height": "Enter the height of the text.",
                "Automatic Placement": "Check to automatically place the short test structure."
            },
            "Rectangle": {
                "Layer": "Select the layer for the rectangle.",
                "Center": "Enter the center (x, y) coordinate of the rectangle.",
                "Width": "Enter the width of the rectangle.",
                "Height": "Enter the height of the rectangle.",
                "Lower Left": "Enter the lower left (x, y) coordinate of the rectangle.",
                "Upper Right": "Enter the upper right (x, y) coordinate of the rectangle.",
                "Rotation": "Enter the rotation angle of the rectangle."
            },
            "Circle": {
                "Layer": "Select the layer for the circle.",
                "Center": "Enter the center (x, y) coordinate of the circle.",
                "Diameter": "Enter the diameter of the circle."
            },
            "Text": {
                "Layer": "Select the layer for the text.",
                "Center": "Enter the center (x, y) coordinate of the text.",
                "Text": "Enter the text to display.",
                "Height": "Enter the height of the text.",
                "Rotation": "Enter the rotation angle of the text."
            },
            "Polygon": {
                "Layer": "Select the layer for the polygon."
            },
            "Path": {
                "Layer": "Select the layer for the path.",
                "Width": "Enter the width of the path."
            },
            "Custom Test Structure": {
                "Center": "Enter the center (x, y) coordinate of the custom test structure.",
                "Magnification": "Enter the magnification factor of the custom test structure.",
                "Rotation": "Enter the rotation angle of the custom test structure.",
                "X Reflection": "Check to reflect the structure in the x direction.",
                "Array": "Check to create an array of the structure.",
                "Copies X": "Enter the number of copies in the x direction.",
                "Copies Y": "Enter the number of copies in the y direction.",
                "Spacing X": "Enter the spacing between copies in the x direction.",
                "Spacing Y": "Enter the spacing between copies in the y direction.",
                "Automatic Placement": "Check to automatically place the custom test structure."
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
            "Custom Test Structure": {
                "Center": '',
                "Magnification": 1,
                "Rotation": 0,
                "X Reflection": False,
                "Array": False,
                "Copies X": 1,
                "Copies Y": 1,
                "Spacing X": 0,
                "Spacing Y": 0,
                "Automatic Placement": False
            }
        }
        self.testStructures = []  # Initialize testStructures here
        self.gds_design = None  # To store the GDSDesign instance
        self.polygon_points = []  # To store polygon points
        self.path_points = [] # To store path points
        self.undoStack = []  # Initialize undo stack
        self.redoStack = []  # Initialize redo stack
        self.initUI()

    def initUI(self):
        # Main Layout
        mainLayout = QVBoxLayout()

        # File selection layout
        fileLayout = QHBoxLayout()
        self.initFileButton = QPushButton('Select Input File')
        self.initFileButton.clicked.connect(self.selectInputFile)
        self.initFileButton.setToolTip('Click to select the input GDS file.')
        self.outFileField = QLineEdit()
        self.outFileField.setPlaceholderText('Output File')
        self.outFileField.editingFinished.connect(self.validateOutputFileName)
        self.outFileField.setToolTip('Enter the name of the output GDS file.')
        fileLayout.addWidget(self.initFileButton)
        fileLayout.addWidget(self.outFileField)
        mainLayout.addLayout(fileLayout)

        # Undo and Redo buttons
        undoRedoLayout = QHBoxLayout()
        self.undoButton = QPushButton('Undo')
        self.undoButton.clicked.connect(self.undo)
        self.undoButton.setToolTip('Undo the last action.')
        self.redoButton = QPushButton('Redo')
        self.redoButton.clicked.connect(self.redo)
        self.redoButton.setToolTip('Redo the previously undone action.')
        undoRedoLayout.addWidget(self.undoButton)
        undoRedoLayout.addWidget(self.redoButton)
        mainLayout.addLayout(undoRedoLayout)

        # Test Structures layout
        testLayout = QVBoxLayout()
        testLabel = QLabel('Test Structures')
        testLayout.addWidget(testLabel)

        gridLayout = QGridLayout()
        row = 0
        for name in self.testStructureNames:
            testCheckBox = QCheckBox(name)
            testCheckBox.stateChanged.connect(self.createCheckStateHandler)
            testCheckBox.setToolTip(f'Check to include {name} in the design.')
            paramLabel = QLabel('Parameters')
            paramComboBox = TooltipComboBox()
            paramComboBox.addItems(self.parameters[name])
            paramComboBox.setItemTooltips([self.paramTooltips[name].get(param, '') for param in self.parameters[name]])
            paramComboBox.currentTextChanged.connect(self.createParamChangeHandler)
            paramComboBox.setToolTip(f'Select parameters for {name}.') 
            paramValueEdit = QLineEdit()
            paramName = paramComboBox.currentText()
            if paramName in self.defaultParams[name]:
                paramValueEdit.setText(str(self.defaultParams[name][paramName]))
            paramValueEdit.editingFinished.connect(self.createParamStoreHandler)
            paramValueEdit.setToolTip(f'Enter value for the selected parameter of {name}.')
            addButton = QPushButton("Add to Design")
            addButton.clicked.connect(self.createAddToDesignHandler)
            addButton.setToolTip(f'Click to add {name} to the design.')

            gridLayout.addWidget(testCheckBox, row, 0)
            gridLayout.addWidget(paramLabel, row, 1)
            gridLayout.addWidget(paramComboBox, row, 2)
            gridLayout.addWidget(paramValueEdit, row, 3)
            gridLayout.addWidget(addButton, row, 4)

            if name == "Polygon":
                self.polygonButton = QPushButton('Select Polygon Points File')
                self.polygonButton.clicked.connect(self.selectPolygonPointsFile)
                self.polygonButton.setToolTip('Click to select a file containing polygon points.')
                gridLayout.addWidget(self.polygonButton, row, 5)
            
            if name == "Path":
                self.pathButton = QPushButton('Select Path Points File')
                self.pathButton.clicked.connect(self.selectPathPointsFile)
                self.pathButton.setToolTip('Click to select a file containing path points.')
                gridLayout.addWidget(self.pathButton, row, 5)

            if name == "Custom Test Structure":
                self.customTestCellComboBox = QComboBox()
                self.customTestCellComboBox.setPlaceholderText("Select Custom Test Structure Cell")
                self.customTestCellComboBox.currentTextChanged.connect(self.handleCustomTestCellName)
                self.customTestCellComboBox.setToolTip('Select a custom test structure cell.')
                gridLayout.addWidget(self.customTestCellComboBox, row, 5)

            row += 1

            defaultParams = deepcopy(self.defaultParams[name])
            self.testStructures.append((testCheckBox, paramComboBox, paramValueEdit, defaultParams, addButton))

        testLayout.addLayout(gridLayout)
        mainLayout.addLayout(testLayout)

        # Layers layout
        layersHBoxLayout = QHBoxLayout()  # Change from QVBoxLayout to QHBoxLayout
        layersLabel = QLabel('Layers:')
        layersLabel.setToolTip('Layers available in the design.')
        layersHBoxLayout.addWidget(layersLabel)

        self.layersComboBox = QComboBox()
        self.layersComboBox.setToolTip('Select a layer from the list.')
        layersHBoxLayout.addWidget(self.layersComboBox)

        self.selectSubstrateLayerButton = QPushButton('Select Substrate Layer')
        self.selectSubstrateLayerButton.clicked.connect(self.selectSubstrateLayer)
        self.selectSubstrateLayerButton.setToolTip('Click to select the substrate layer from the dropdown menu.')
        layersHBoxLayout.addWidget(self.selectSubstrateLayerButton)  # Add the button to the right

        # Define Layer layout
        defineLayerHBoxLayout = QHBoxLayout()
        self.newLayerNumberEdit = QLineEdit()
        self.newLayerNumberEdit.setPlaceholderText('Layer Number')
        self.newLayerNumberEdit.setToolTip('Enter the number of the new layer.')
        self.newLayerNameEdit = QLineEdit()
        self.newLayerNameEdit.setPlaceholderText('Layer Name')
        self.newLayerNameEdit.setToolTip('Enter the name of the new layer.')
        defineLayerButton = QPushButton('Define New Layer')
        defineLayerButton.clicked.connect(self.defineNewLayer)
        defineLayerButton.setToolTip('Click to define a new layer.')
        defineLayerHBoxLayout.addWidget(self.newLayerNumberEdit)
        defineLayerHBoxLayout.addWidget(self.newLayerNameEdit)
        defineLayerHBoxLayout.addWidget(defineLayerButton)

        # Layers and Define Layer layout
        layersVBoxLayout = QVBoxLayout()
        layersVBoxLayout.addLayout(layersHBoxLayout)
        layersVBoxLayout.addLayout(defineLayerHBoxLayout)

        mainLayout.addLayout(layersVBoxLayout)

        # Write to GDS button
        writeButton = QPushButton('Write to GDS')
        writeButton.clicked.connect(self.writeToGDS)
        writeButton.setToolTip('Click to write the current design to a GDS file.')
        mainLayout.addWidget(writeButton)

        self.setLayout(mainLayout)
        self.setWindowTitle('Test Structure Automation GUI')
        self.resize(1200, 800)  # Set the initial size of the window
        self.show()

    def log(self, message):
        if self.verbose:
            print(message)

    def createCheckStateHandler(self, state):
        sender = self.sender()
        name = sender.text()
        self.log(f"{name} {'selected' if state == Qt.Checked else 'unselected'}")
    
    def selectSubstrateLayer(self):
        currentLayer = self.layersComboBox.currentText()
        if currentLayer:
            layerNumber = int(currentLayer.split(':')[0])
            self.substrateLayer = layerNumber
            self.log(f"Substrate layer set to: {self.substrateLayer}")
            QMessageBox.information(self, "Substrate Layer Selected", f"Substrate layer set to: {self.substrateLayer}", QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "Selection Error", "No layer selected from the dropdown menu.", QMessageBox.Ok)

    def createParamChangeHandler(self, param):
        sender = self.sender()
        # Update the default value to display for the specific test structure and parameter
        for checkBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if comboBox == sender:
                name = checkBox.text()
                value = defaultParams.get(param, '')
                valueEdit.setText(str(value))
                # Set tooltip for the parameter value edit field
                tooltip = self.paramTooltips.get(name, {}).get(param, '')
                comboBox.setToolTip(tooltip)
                # Log that this specific test structure has this parameter selected
                self.log(f"{name} Parameter {param} selected, display value set to {value}")
                
    def createParamStoreHandler(self):
        sender = self.sender()
        for checkBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if valueEdit == sender:
                name = checkBox.text()
                comboBox = comboBox
                break
        self.storeParameterValue(comboBox, valueEdit, name)

    def createAddToDesignHandler(self):
        sender = self.sender()
        for checkBox, _, _, _, addButton in self.testStructures:
            if addButton == sender:
                name = checkBox.text()
                break
        self.handleAddToDesign(name)

    def addSnapshot(self):
        self.log("Adding snapshot to undo stack and clearing redo stack")
        self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries()))
        self.redoStack.clear()

    def readLogEntries(self):
        with open(self.logFileName, 'r') as log_file:
            return log_file.readlines()
        
    def writeLogEntries(self, log_entries):
        with open(self.logFileName, 'w') as log_file:
            log_file.writelines(log_entries)

    def undo(self):
        if self.undoStack:
            self.log("Adding snapshot to redo stack and reverting to previous state")
            self.redoStack.append((deepcopy(self.gds_design), self.readLogEntries()))
            self.gds_design, log_entries = self.undoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()
        else:
            QMessageBox.critical(self, "Edit Error", "No undo history is currently stored", QMessageBox.Ok)

    def redo(self):
        if self.redoStack:
            self.log("Adding snapshot to undo stack and reverting to previous state")
            self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries()))
            self.gds_design, log_entries = self.redoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()
        else:
            QMessageBox.critical(self, "Edit Error", "No redo history is currently stored", QMessageBox.Ok)

    def selectInputFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.gds'):
                self.inputFileName = fileName
                self.log(f"Input File: {self.inputFileName}")
                baseName = fileName.rsplit('.', 1)[0]
                self.outputFileName = f"{baseName}-output.gds"
                self.outFileField.setText(self.outputFileName)
                self.log(f"Output File automatically set to: {self.outputFileName}")

                self.logFileName = f"{self.outputFileName.rsplit('.', 1)[0]}-log.txt"  # Set log file name based on output file name
                self.log(f"Log File set to: {self.logFileName}")
                self.initLogFile()  # Initialize the log file

                # Load the GDS file using GDSDesign
                self.gds_design = GDSDesign(filename=self.inputFileName)
                self.layerData = [(str(layer['number']), layer_name) for layer_name, layer in self.gds_design.layers.items()]
                self.log(f"Layers read from file: {self.layerData}")
                self.updateLayersComboBox()

                # Populate the custom test cell combo box with cell names
                self.customTestCellComboBox.clear()
                self.customTestCellComboBox.addItems(self.gds_design.cells.keys())
                self.log(f"Custom Test Structure cell names: {list(self.gds_design.cells.keys())}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                self.log("File selection error: Not a .gds file")

    def readPolygonPointsFile(self, fileName):
        try:
            if fileName.lower().endswith('.txt'):
                points = np.loadtxt(fileName, delimiter=',')
            elif fileName.lower().endswith('.csv'):
                points = np.loadtxt(fileName, delimiter=',')
            points_list = [tuple(point) for point in points]
            if all(len(point) == 2 for point in points_list):
                self.polygon_points = points_list
                self.log(f"Polygon Points read: {self.polygon_points}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            self.log(f"Error reading polygon points file: {str(e)}")

    def readPathPointsFile(self, fileName):
        try:
            if fileName.lower().endswith('.txt'):
                points = np.loadtxt(fileName, delimiter=',')
            elif fileName.lower().endswith('.csv'):
                points = np.loadtxt(fileName, delimiter=',')
            points_list = [tuple(point) for point in points]
            if all(len(point) == 2 for point in points_list):
                self.path_points = points_list
                self.log(f"Path Points read: {self.path_points}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            self.log(f"Error reading path points file: {str(e)}")

    def selectPolygonPointsFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Polygon Points File", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.txt') or fileName.lower().endswith('.csv'):
                self.readPolygonPointsFile(fileName)
                self.log(f"Polygon Points File: {fileName}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .txt or .csv file.", QMessageBox.Ok)
                self.log("File selection error: Not a .txt or .csv file")

    def selectPathPointsFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Path Points File", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.txt') or fileName.lower().endswith('.csv'):
                self.readPathPointsFile(fileName)
                self.log(f"Path Points File: {fileName}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .txt or .csv file.", QMessageBox.Ok)
                self.log("File selection error: Not a .txt or .csv file")
                
    def updateLayersComboBox(self):
        self.layersComboBox.clear()
        # Add layers to the dropdown sorted by layer number
        self.layerData.sort(key=lambda x: int(x[0]))
        for number, name in self.layerData:
            self.layersComboBox.addItem(f"{number}: {name}")
        self.log("Layers dropdown updated")

    def validateOutputFileName(self):
        outputFileName = self.outFileField.text()
        if outputFileName.lower().endswith('.gds'):
            oldLogFileName = self.logFileName
            self.outputFileName = outputFileName
            self.logFileName = f"{outputFileName.rsplit('.', 1)[0]}-log.txt"  # Update log file name based on new output file name
            
            if os.path.exists(oldLogFileName):
                os.rename(oldLogFileName, self.logFileName)  # Rename the existing log file to the new log file name
            
            self.log(f"Output File set to: {self.outputFileName}")
            self.log(f"Log File renamed to: {self.logFileName}")
        else:
            QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
            self.outFileField.setText(self.outputFileName)
            self.log("Output file validation error: Not a .gds file")

    def initLogFile(self):
        with open(self.logFileName, 'w') as log_file:
            log_file.write("Test Structure Placement Log\n")
            log_file.write("============================\n\n")

    def updateParameterValue(self, param, testStructureName):
        for _, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if comboBox.currentText() == param:
                default_value = defaultParams.get(param, '')
                valueEdit.setText(str(default_value))
                self.log(f"{testStructureName} Parameter {param} selected, default value set to {default_value}")

    def storeParameterValue(self, comboBox, valueEdit, name):
        param = comboBox.currentText()
        value = valueEdit.text()
        if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer":
            value = self.validateLayer(value)
        elif param == "Center" and name != "Rectangle":
            value = self.validateCenter(value)
        for i, (checkBox, cb, edit, defaultParams, addButton) in enumerate(self.testStructures):
            if cb == comboBox:
                if param in defaultParams:
                    self.testStructures[i][3][param] = value
                    self.log(f"{name} {param} updated to {value}")

    def validateLayer(self, layer):
        self.log(f"Validating Layer: {layer}")
        layer = layer.strip()
        if layer.isdigit():
            layer_number = int(layer)
            for number, name in self.layerData:
                if int(number) == layer_number:
                    self.log(f"Layer number {layer_number} is valid")
                    return int(number)  # Return the layer name instead of number
        else:
            for number, name in self.layerData:
                if name == layer:
                    self.log(f"Layer name {layer} is valid")
                    return int(number)
        self.log("Invalid layer")
        QMessageBox.critical(self, "Layer Error", "Invalid layer. Please select a valid layer.", QMessageBox.Ok)
        return None

    def validateCenter(self, center):
        self.log(f"Validating Center: {center}")
        if not(center):
            QMessageBox.critical(self, "Center Error", "Please enter a center (x, y) coordinate.", QMessageBox.Ok)
            return None
        if isinstance(center, tuple):
            return center
        center = center.replace("(", "").replace(")", "").replace(" ", "")
        try:
            x, y = map(float, center.split(','))
            self.log(f"Center is valid: ({x}, {y})")
            return (x, y)
        except:
            self.log("Invalid center")
            QMessageBox.critical(self, "Center Error", "Invalid center. Please enter a valid (x, y) coordinate.", QMessageBox.Ok)
            return None

    def handleAddToDesign(self, testStructureName):
        # Make sure the checkbox is checked for this test structure
        for checkBox, _, _, _, _ in self.testStructures:
            if checkBox.text() == testStructureName:
                if not checkBox.isChecked():
                    QMessageBox.critical(self, "Test Structure Error", f"Please check the '{testStructureName}' checkbox to add it to the design.", QMessageBox.Ok)
                    self.log(f"Add to Design error: '{testStructureName}' checkbox not checked")
                    return
        self.log(f"Adding {testStructureName} to design")
        self.addSnapshot()  # Store snapshot before adding new design
        params = self.getParameters(testStructureName)
        self.log(f"Parameters: {params}")
        if params:
            if testStructureName == "MLA Alignment Mark":
                self.addMLAAlignmentMark(**params)
            elif testStructureName == "Resistance Test":
                self.addResistanceTest(**params)
            elif testStructureName == "Trace Test":
                self.addTraceTest(**params)
            elif testStructureName == "Interlayer Via Test":
                self.addInterlayerViaTest(**params)
            elif testStructureName == "Electronics Via Test":
                self.addElectronicsViaTest(**params)
            elif testStructureName == "Short Test":
                self.addShortTest(**params)
            elif testStructureName == "Custom Test Structure":
                self.addCustomTestStructure(**params)
            elif testStructureName == "Rectangle":
                self.addRectangle(**params)
            elif testStructureName == "Circle":
                self.addCircle(**params)
            elif testStructureName == "Text":
                self.addText(**params)
            elif testStructureName == "Polygon":
                self.addPolygon(**params)
            elif testStructureName == "Path":
                self.addPath(**params)
            self.logTestStructure(testStructureName, params)  # Log the test structure details
        # Write the design
        self.writeToGDS()

    def logTestStructure(self, name, params):
        with open(self.logFileName, 'a') as log_file:
            log_file.write(f"Test Structure: {name}\n")
            for param, value in params.items():
                log_file.write(f"{param}: {value}\n")
            log_file.write("\n")

    def getParameters(self, testStructureName):
        params = {}
        autoplace = False
        # See if Automatic Placement is set to True
        for testCheckBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if testCheckBox.text() == testStructureName:
                if "Automatic Placement" in defaultParams:
                    if type(defaultParams["Automatic Placement"]) == str:
                        if defaultParams["Automatic Placement"].lower() == 'true':
                            autoplace = True
                    elif defaultParams["Automatic Placement"]:
                        autoplace = True
                break

        for testCheckBox, comboBox, valueEdit, defaultParams, addButton in self.testStructures:
            if testCheckBox.text() == testStructureName:
                for param in self.parameters[testStructureName]:
                    value = defaultParams.get(param, '')
                    self.log(f"Getting parameter {param}: {value}")
                    if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer" or (param == "Layer Name Short" and value):
                        # Lookup layer number and get name
                        layer_number = self.validateLayer(str(value))
                        if layer_number is None:
                            return
                        for number, name in self.layerData:
                            if int(number) == layer_number:
                                value = name
                    elif param == "Center" and testStructureName != "Rectangle" and not(autoplace):
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

    def addMLAAlignmentMark(self, Layer, Center, Outer_Rect_Width, Outer_Rect_Height, Interior_Width, Interior_X_Extent, Interior_Y_Extent, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if not(Automatic_Placement):
            self.gds_design.add_MLA_alignment_mark(
                cell_name=top_cell_name,
                layer_name=Layer,
                center=Center,
                rect_width=float(Outer_Rect_Width),
                rect_height=float(Outer_Rect_Height),
                width_interior=float(Interior_Width),
                extent_x_interior=float(Interior_X_Extent),
                extent_y_interior=float(Interior_Y_Extent)
            )
        # If automatic placement is set to true, place the feature on a temporary cell, determine the size, and then place it on the top cell in a position where there is no overlap
        else:
            try:
                self.gds_design.delete_cell(TEMP_CELL_NAME)
            except ValueError:
                pass  # If the cell doesn't exist, just ignore the error

            self.gds_design.add_cell(TEMP_CELL_NAME)
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
            cell_width, cell_height, cell_offset = self.gds_design.calculate_cell_size(TEMP_CELL_NAME)
            self.gds_design.delete_cell(TEMP_CELL_NAME)
            # Get substrate layer name from layer number:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if not substrate_name:
                QMessageBox.critical(self, "Substrate Layer Error", "Substrate layer not set. Please select a substrate layer.", QMessageBox.Ok)
                self.log("MLA Alignment Mark placement error: Substrate layer not set")
                return
            available_space = self.gds_design.determine_available_space(substrate_name)
            print(cell_width, cell_height, cell_offset)
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the MLA Alignment Mark.", QMessageBox.Ok)
                self.log("MLA Alignment Mark placement error: No space available")
                return
            self.gds_design.add_MLA_alignment_mark(
                cell_name=top_cell_name,
                layer_name=Layer,
                center=Center,
                rect_width=float(Outer_Rect_Width),
                rect_height=float(Outer_Rect_Height),
                width_interior=float(Interior_Width),
                extent_x_interior=float(Interior_X_Extent),
                extent_y_interior=float(Interior_Y_Extent)
            )

        self.log(f"MLA Alignment Mark added to {top_cell_name} on layer {Layer} at center {Center}")

    def addResistanceTest(self, Layer, Center, Probe_Pad_Width, Probe_Pad_Height, Probe_Pad_Spacing, Plug_Width, Plug_Height, Trace_Width, Trace_Spacing, Switchbacks, X_Extent, Text_Height, Text, Add_Interlayer_Short, Layer_Name_Short, Short_Text, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_resistance_test_structure(
            cell_name=top_cell_name,
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
        self.log(f"Resistance Test added to {top_cell_name} on layer {Layer} at center {Center}")

    def addTraceTest(self, Layer, Center, Text, Line_Width, Line_Height, Num_Lines, Line_Spacing, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_line_test_structure(
            cell_name=top_cell_name,
            layer_name=Layer,
            center=Center,
            text=Text if Text else f"{Layer} TRACE",  # Use the layer name if text is not provided
            line_width=float(Line_Width),
            line_height=float(Line_Height),
            num_lines=int(Num_Lines),
            line_spacing=float(Line_Spacing),
            text_height=float(Text_Height)
        )
        self.log(f"Trace Test added to {top_cell_name} on layer {Layer} at center {Center}")

    def addInterlayerViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rectangle_Spacing, Layer_1_Rectangle_Width, Layer_1_Rectangle_Height, Layer_2_Rectangle_Width, Layer_2_Rectangle_Height, Via_Width, Via_Height, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_p_via_test_structure(
            cell_name=top_cell_name,
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
        self.log(f"Interlayer Via Test added to {top_cell_name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")
    
    def addRectangle(self, Layer, Center, Width, Height, Lower_Left, Upper_Right, Rotation):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_rectangle(
            cell_name=top_cell_name,
            layer_name=Layer,
            center=self.validateCenter(Center) if Center else None,
            width=float(Width) if Width else None,
            height=float(Height) if Height else None,
            lower_left=float(Lower_Left) if Lower_Left else None,
            upper_right=float(Upper_Right) if Upper_Right else None,
            rotation=float(Rotation)*math.pi/180
        )
        self.log(f"Rectangle added to {top_cell_name} on layer {Layer} at center {Center}")

    def addCircle(self, Layer, Center, Diameter):
        if not Diameter:
            QMessageBox.critical(self, "Input Error", "Please enter a diameter for the circle.", QMessageBox.Ok)
            self.log("Circle add error: No diameter provided")
            return
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_circle_as_polygon(
            cell_name=top_cell_name,
            center=Center,
            radius=float(Diameter)/2,
            layer_name=Layer
        )
        self.log(f"Circle added to {top_cell_name} on layer {Layer} at center {Center}")
    
    def addText(self, Layer, Center, Text, Height, Rotation):
        top_cell_name = self.gds_design.top_cell_names[0]

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
        self.gds_design.add_text(
            cell_name=top_cell_name,
            text=Text,
            layer_name=Layer,
            position=(rotated_x, rotated_y),
            height=float(Height),
            angle=float(Rotation)
        )
        self.log(f"Text added to {top_cell_name} on layer {Layer} at center {Center}")

    def addPolygon(self, Layer):
        Points = self.polygon_points
        if len(Points) < 3:
            QMessageBox.critical(self, "Input Error", "Please select a valid polygon points file.", QMessageBox.Ok)
            self.log("Polygon add error: Invalid points provided")
            return
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_polygon(
            cell_name=top_cell_name,
            points=Points,
            layer_name=Layer
        )
        self.log(f"Polygon added to {top_cell_name} on layer {Layer}")

    def addPath(self, Layer, Width):
        Points = self.path_points
        if len(Points) < 2:
            QMessageBox.critical(self, "Input Error", "Please select a valid path points file.", QMessageBox.Ok)
            self.log("Path add error: No points provided")
            return
        if not Width:
            QMessageBox.critical(self, "Input Error", "Please enter a width for the path.", QMessageBox.Ok)
            self.log("Path add error: No width provided")
            return
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_path_as_polygon(
            cell_name=top_cell_name,
            points=Points,
            width=float(Width),
            layer_name=Layer
        )
        self.log(f"Path added to {top_cell_name} on layer {Layer}")

    def addElectronicsViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rect_Width, Layer_1_Rect_Height, Layer_2_Rect_Width, Layer_2_Rect_Height, Layer_2_Rect_Spacing, Via_Width, Via_Height, Via_Spacing, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_electronics_via_test_structure(
            cell_name=top_cell_name,
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
        self.log(f"Electronics Via Test added to {top_cell_name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")

    def addShortTest(self, Layer, Center, Text, Rect_Width, Trace_Width, Num_Lines, Group_Spacing, Num_Groups, Num_Lines_Vert, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        self.gds_design.add_short_test_structure(
            cell_name=top_cell_name,
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
        self.log(f"Short Test added to {top_cell_name} on layer {Layer} at center {Center}")

    def addCustomTestStructure(self, Center, Magnification, Rotation, X_Reflection, Array, Copies_X, Copies_Y, Spacing_X, Spacing_Y, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if self.customTestCellName:
            try:
                if not Array:
                    self.gds_design.add_cell_reference(
                        parent_cell_name=top_cell_name,
                        child_cell_name=self.customTestCellName,
                        origin=Center,
                        magnification=float(Magnification),
                        rotation=float(Rotation),
                        x_reflection=X_Reflection
                    )
                    self.log(f"Custom Test Structure '{self.customTestCellName}' added to {top_cell_name} at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}")
                else:
                    self.gds_design.add_cell_array(
                        target_cell_name=top_cell_name,
                        cell_name_to_array=self.customTestCellName,
                        copies_x=int(Copies_X),
                        copies_y=int(Copies_Y),
                        spacing_x=float(Spacing_X),
                        spacing_y=float(Spacing_Y),
                        origin=Center,
                        magnification=float(Magnification),
                        rotation=float(Rotation),
                        x_reflection=X_Reflection
                    )
                    self.log(f"Custom Test Structure '{self.customTestCellName}' added to {top_cell_name} as an array at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}, copies x {Copies_X}, copies y {Copies_Y}, spacing x {Spacing_X}, spacing y {Spacing_Y}")
            except ValueError:
                QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)
                
    def handleCustomTestCellName(self):
        self.customTestCellName = self.customTestCellComboBox.currentText()
        self.log(f"Custom Test Structure Cell Name set to: {self.customTestCellName}")
        self.checkCustomTestCell()

    def checkCustomTestCell(self):
        if self.customTestCellName:
            try:
                self.gds_design.check_cell_exists(self.customTestCellName)
                self.log(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
            except ValueError:
                QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)

    def writeToGDS(self):
        if self.gds_design:
            outputFileName = self.outFileField.text()
            if outputFileName.lower().endswith('.gds'):
                self.gds_design.write_gds(outputFileName)
                self.log(f"GDS file written to {outputFileName}")
            else:
                QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
                self.log("Output file write error: Not a .gds file")
        else:
            QMessageBox.critical(self, "Design Error", "No design loaded to write to GDS.", QMessageBox.Ok)
            self.log("Write to GDS error: No design loaded")

    def defineNewLayer(self):
        number = self.newLayerNumberEdit.text().strip()
        name = self.newLayerNameEdit.text().strip()
        if number and name:
            try:
                # Define the new layer using GDSDesign
                self.gds_design.define_layer(name, int(number))
                self.log(f"Layer defined: {name} with number {number}")
                
                # Check if layer already exists and update name if so
                for i, (layer_number, layer_name) in enumerate(self.layerData):
                    if layer_number == number:
                        old_name = self.layerData[i][1]
                        self.layerData[i] = (number, name)
                        self.updateLayersComboBox()
                        self.log(f"Layer {number} name updated from {old_name} to {name}")
                        self.log(f"Current layers: {self.gds_design.layers}")
                        return
                
                # Add new layer if it doesn't exist already
                self.layerData.append((number, name))
                self.updateLayersComboBox()
                self.log(f"New Layer added: {number} - {name}")
                self.log(f"Current layers: {self.gds_design.layers}")
            except ValueError as e:
                QMessageBox.critical(self, "Layer Error", str(e), QMessageBox.Ok)
                self.log(f"Layer definition error: {e}")
        else:
            QMessageBox.critical(self, "Input Error", "Please enter both Layer Number and Layer Name.", QMessageBox.Ok)
            self.log("Layer definition error: Missing layer number or name")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the PyQt5 GUI application.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose mode')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    ex = MyApp(verbose=True)
    sys.exit(app.exec_())
