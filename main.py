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
import uuid
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

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
        self.customFileName = ""
        self.substrateLayer = None
        self.excludedLayers = []
        self.availableSpace = None
        self.allOtherPolygons = None
        self.layerData = []  # To store layer numbers and names
        self.testStructureNames = [
            "MLA Alignment Mark", "Resistance Test", "Trace Test", 
            "Interlayer Via Test", "Electronics Via Test", "Short Test", 
            "Rectangle", "Circle", "Text", "Polygon", "Path", "Escape Routing", "Custom Test Structure"
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
            "Escape Routing": ["Cell Name", "Layer", "Center", "Copies X", "Copies Y", "Spacing X", "Spacing Y", "Trace Width", "Pad Diameter", "Orientation"],
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
                "Via Spacing": "Enter the spacing between vias and edge of rectangles in layer 2.",
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
            "Escape Routing": {
                "Cell Name": "Select the cell name for the escape routing.",
                "Layer": "Select the layer for the escape routing.",
                "Center": "Enter the center (x, y) coordinate of the escape routing.",
                "Copies X": "Enter the number of copies in the x direction.",
                "Copies Y": "Enter the number of copies in the y direction.",
                "Spacing X": "Enter the spacing between copies in the x direction.",
                "Spacing Y": "Enter the spacing between copies in the y direction.",
                "Trace Width": "Enter the width of the traces.",
                "Pad Diameter": "Enter the diameter of the pads.",
                "Orientation": "Enter the orientation of the escape routing."
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
                "Automatic Placement": True
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
                "Automatic Placement": True
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
                "Automatic Placement": True
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
                "Automatic Placement": True
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
                "Automatic Placement": True
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
                "Automatic Placement": True
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
                "Cell Name": '',
                "Layer": '',
                "Center": '',
                "Copies X": '',
                "Copies Y": '',
                "Spacing X": '',
                "Spacing Y": '',
                "Trace Width": '',
                "Pad Diameter": '',
                "Orientation": ''
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
                "Automatic Placement": True
            }
        }
        self.testStructures = []  # Initialize testStructures here
        self.gds_design = None  # To store the GDSDesign instance
        self.custom_design = None  # To store the custom design instance
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

        # Add cell dropdown and Matplotlib Button
        plotLayout = QHBoxLayout()
        self.cellComboBox = QComboBox()
        self.cellComboBox.setPlaceholderText("Select Cell")
        self.cellComboBox.setToolTip('Select a cell from the loaded GDS file.')
        plotLayout.addWidget(self.cellComboBox)

        self.matplotlibButton = QPushButton('Routing Tool')
        self.matplotlibButton.clicked.connect(self.showMatplotlibWindow)
        self.matplotlibButton.setToolTip('Click to show an interactive plot of the selected cell for routing.')
        plotLayout.addWidget(self.matplotlibButton)

        mainLayout.addLayout(plotLayout)

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
                
                # New button to select other .gds file
                self.selectOtherGDSButton = QPushButton('Select Other .gds File')
                self.selectOtherGDSButton.clicked.connect(self.selectOtherGDSFile)
                self.selectOtherGDSButton.setToolTip('Click to select another .gds file.')
                gridLayout.addWidget(self.selectOtherGDSButton, row, 6)  # Adjust the position as needed

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

        # New Excluded Layers input field
        self.excludedLayersEdit = QLineEdit()
        self.excludedLayersEdit.setPlaceholderText('Excluded Layers')
        self.excludedLayersEdit.editingFinished.connect(self.updateExcludedLayers)
        self.excludedLayersEdit.setToolTip('Enter comma-separated list of layer numbers or names to exclude from automatic placement search.')
        layersHBoxLayout.addWidget(self.excludedLayersEdit)

        # New Calculate Layer Area button and Layer Area text box
        self.calculateLayerAreaButton = QPushButton('Calculate Layer Area')
        self.calculateLayerAreaButton.clicked.connect(self.calculateLayerArea)
        self.calculateLayerAreaButton.setToolTip('Click to calculate the area for the selected layer.')
        layersHBoxLayout.addWidget(self.calculateLayerAreaButton)

        self.layerAreaEdit = QLineEdit()
        self.layerAreaEdit.setPlaceholderText('Layer Area (mm^2)')
        self.layerAreaEdit.setReadOnly(True)
        self.layerAreaEdit.setToolTip('Displays the calculated area of the selected layer in mm^2.')
        layersHBoxLayout.addWidget(self.layerAreaEdit)

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
        self.resize(1400, 800)  # Set the initial size of the window
        self.show()
    
    def showMatplotlibWindow(self):
        fig = Figure()
        canvas = FigureCanvas(fig)
        
        # Create an example plot
        ax = fig.add_subplot(111)
        t = np.arange(0.0, 3.0, 0.01)
        s = np.sin(2 * np.pi * t)
        ax.plot(t, s)

        # Connect the click event to the handler
        canvas.mpl_connect('button_press_event', self.on_click)

        # Create a new window for the plot
        self.plotWindow = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(canvas)
        self.plotWindow.setLayout(layout)
        self.plotWindow.setWindowTitle("Interactive Matplotlib Plot")
        self.plotWindow.setGeometry(100, 100, 800, 600)
        self.plotWindow.show()

        # Use the selected cell from the dropdown
        selected_cell = self.cellComboBox.currentText()
        self.log(f"Selected cell for plotting: {selected_cell}")
        # Implement logic to use the selected cell for plotting if needed

    def on_click(self, event):
        if event.inaxes is not None:
            x, y = event.xdata, event.ydata
            self.log(f"Click at position: ({x}, {y})")
            # You can process the click coordinates here
            self.process_click(x, y)
        else:
            self.log("Click outside axes bounds")

    def process_click(self, x, y):
        # Implement your processing logic here
        QMessageBox.information(self, "Click Position", f"Click at: ({x}, {y})")
        self.log(f"Processing click at: ({x}, {y})")
    
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
                    self.log(f"Excluded Layers input error: Cannot exclude substrate layer {layer}")
                    return
                elif any(int(number) == layer_number for number, name in self.layerData):
                    valid_layers.append(layer_number)
                else:
                    QMessageBox.critical(self, "Layer Error", f"Invalid layer number: {layer}", QMessageBox.Ok)
                    self.log(f"Excluded Layers input error: Invalid layer number {layer}")
                    return
            else:
                if any(name.lower() == layer.lower() for number, name in self.layerData) and not any(int(number) == self.substrateLayer for number, name in self.layerData if name.lower() == layer.lower()):
                    valid_layers.append(next(int(number) for number, name in self.layerData if name.lower() == layer.lower() and int(number) != self.substrateLayer))
                else:
                    QMessageBox.critical(self, "Layer Error", f"Invalid layer name: {layer}", QMessageBox.Ok)
                    self.log(f"Excluded Layers input error: Invalid layer name {layer}")
                    return
                
        self.excludedLayers = valid_layers
        self.log(f"Excluded layers set to: {self.excludedLayers}")
        if type(self.substrateLayer) == int:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if substrate_name:
                self.availableSpace, self.allOtherPolygons = self.gds_design.determine_available_space(substrate_name, self.excludedLayers)
                self.log(f"Available space calculated.")
                self.log(f"All other polygons calculated.")

    def calculateLayerArea(self):
        currentLayer = self.layersComboBox.currentText()
        if currentLayer:
            layerName = currentLayer.split(':')[1].strip()
            try:
                area = self.gds_design.calculate_area_for_layer(layerName)
                self.layerAreaEdit.setText(f"{area} mm^2")
                self.log(f"Layer Area for {layerName}: {area} mm^2")
            except Exception as e:
                QMessageBox.critical(self, "Calculation Error", f"Error calculating area for layer {layerName}: {str(e)}", QMessageBox.Ok)
                self.log(f"Error calculating area for layer {layerName}: {str(e)}")
        else:
            QMessageBox.warning(self, "Selection Error", "No layer selected from the dropdown menu.", QMessageBox.Ok)

    def log(self, message):
        if self.verbose:
            print(message)

    def createCheckStateHandler(self, state):
        sender = self.sender()
        name = sender.text()
        self.log(f"{name} {'selected' if state == Qt.Checked else 'unselected'}")
    
    def selectSubstrateLayer(self):
        # Output: sets self.substrateLayer and sets available space and all other polygons
        currentLayer = self.layersComboBox.currentText()
        if currentLayer:
            layerNumber = int(currentLayer.split(':')[0])
            if layerNumber in self.excludedLayers:
                QMessageBox.critical(self, "Layer Error", "Cannot set the substrate layer to an excluded layer.", QMessageBox.Ok)
                self.log(f"Substrate layer selection error: Cannot set to excluded layer {layerNumber}")
                return
            
            # Initialize available space
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == layerNumber:
                    substrate_name = name
            if substrate_name:
                try:
                    self.availableSpace, self.allOtherPolygons = self.gds_design.determine_available_space(substrate_name, self.excludedLayers)
                    self.log(f"Available space calculated.")
                    self.log(f"All other polygons calculated.")

                    self.substrateLayer = layerNumber
                    self.log(f"Substrate layer set to: {self.substrateLayer}")
                    QMessageBox.information(self, "Substrate Layer Selected", f"Substrate layer set to: {self.substrateLayer}", QMessageBox.Ok)
                except ValueError:
                    QMessageBox.critical(self, "Layer Error", "Substrate layer does not exist in the design. First add substrate shape to the design and then re-select as substrate layer.", QMessageBox.Ok)
                    self.log(f"Substrate layer selection error: Layer {self.substrateLayer} does not exist in the design.")
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
        self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons)))
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
            self.redoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons)))
            self.gds_design, log_entries, self.availableSpace, self.allOtherPolygons = self.undoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()
        else:
            QMessageBox.critical(self, "Edit Error", "No undo history is currently stored", QMessageBox.Ok)

    def redo(self):
        if self.redoStack:
            self.log("Adding snapshot to undo stack and reverting to previous state")
            self.undoStack.append((deepcopy(self.gds_design), self.readLogEntries(), deepcopy(self.availableSpace), deepcopy(self.allOtherPolygons)))
            self.gds_design, log_entries, self.availableSpace, self.allOtherPolygons = self.redoStack.pop()
            self.writeLogEntries(log_entries)
            self.writeToGDS()
        else:
            QMessageBox.critical(self, "Edit Error", "No redo history is currently stored", QMessageBox.Ok)

    def selectInputFile(self):
        # Output: sets self.inputFileName, self.outputFileName, self.logFileName, self.gds_design, self.layerData, and updates layersComboBox and customTestCellComboBox
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

                # Populate the cell combo box with cell names
                self.cellComboBox.clear()
                self.cellComboBox.addItems(self.gds_design.cells.keys())
                self.log(f"Cell combo box populated with cells: {list(self.gds_design.cells.keys())}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                self.log("File selection error: Not a .gds file")
    
    def selectOtherGDSFile(self):
        # Output: sets self.customFileName and self.custom_design, updates customTestCellComboBox
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Other .gds File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.lower().endswith('.gds'):
                self.customFileName = fileName
                self.custom_design = GDSDesign(filename=fileName)
                self.log(f"Custom design loaded from: {fileName}")
                QMessageBox.information(self, "File Selected", f"Custom design loaded from: {fileName}", QMessageBox.Ok)
                
                if self.customFileName != self.inputFileName:
                    for cell in self.gds_design.lib.cells:
                        if cell in self.custom_design.lib.cells:
                            idstr = uuid.uuid4().hex[:8]
                            self.custom_design.lib.rename_cell(self.custom_design.lib.cells[cell], f"{cell}_custom_{idstr}", update_references=True)
                            self.log(f'Duplicate cell found. Renaming cell {cell} to {cell}_custom_{idstr}')

                # Populate the custom test cell combo box with cell names
                self.customTestCellComboBox.clear()
                self.customTestCellComboBox.addItems(self.custom_design.lib.cells.keys())
                self.log(f"Custom Test Structure cell names: {list(self.custom_design.lib.cells.keys())}")
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                self.log("File selection error: Not a .gds file")

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
                self.log(f"Polygon Points read: {self.polygon_points}")
            else:
                raise ValueError("File does not contain valid (x, y) coordinates.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error reading file: {str(e)}", QMessageBox.Ok)
            self.log(f"Error reading polygon points file: {str(e)}")

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
        # Output: sets self.outputFileName and renames log file if needed
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

    def storeParameterValue(self, comboBox, valueEdit, name):
        # Output: updates the defaultParams dictionary for the specific test structure and parameter
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
                retval = self.addMLAAlignmentMark(**params)
            elif testStructureName == "Resistance Test":
                retval = self.addResistanceTest(**params)
            elif testStructureName == "Trace Test":
                retval = self.addTraceTest(**params)
            elif testStructureName == "Interlayer Via Test":
                retval = self.addInterlayerViaTest(**params)
            elif testStructureName == "Electronics Via Test":
                retval = self.addElectronicsViaTest(**params)
            elif testStructureName == "Short Test":
                retval = self.addShortTest(**params)
            elif testStructureName == "Custom Test Structure":
                retval = self.addCustomTestStructure(**params)
            elif testStructureName == "Rectangle":
                retval = self.addRectangle(**params)
            elif testStructureName == "Circle":
                retval = self.addCircle(**params)
            elif testStructureName == "Text":
                retval = self.addText(**params)
            elif testStructureName == "Polygon":
                retval = self.addPolygon(**params)
            elif testStructureName == "Path":
                retval = self.addPath(**params)
            elif testStructureName == "Escape Routing":
                retval = self.addEscapeRouting(**params)
            
            if retval:
                # Write the design
                self.writeToGDS()
                # Update the available space
                self.updateAvailableSpace()

    def updateAvailableSpace(self):
        if type(self.substrateLayer) == int:
            substrate_name = None
            for number, name in self.layerData:
                if int(number) == self.substrateLayer:
                    substrate_name = name
            if substrate_name:
                self.availableSpace, self.allOtherPolygons = self.gds_design.update_available_space(substrate_name, self.availableSpace, self.allOtherPolygons, self.excludedLayers)
                self.log(f"Available space updated.")
                self.log(f"All other polygons updated.")

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

    def addEscapeRouting(self, Cell_Name, Layer, Center, Copies_X, Copies_Y, Spacing_X, Spacing_Y, Trace_Width, Pad_Diameter, Orientation):
        if Orientation is None:
            QMessageBox.critical(self, "Orientation Error", "Please enter an orientation for the escape routing.", QMessageBox.Ok)
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
                return False
            
            try:
                self.gds_design.add_regular_array_escape_one_sided(
                    trace_cell_name=Cell_Name,
                    center=Center,
                    layer_name=Layer,
                    pitch_x=float(Spacing_X),
                    pitch_y=float(Spacing_Y),
                    array_size_x=int(Copies_X),
                    array_size_y=int(Copies_Y),
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y,
                    escape_negative=escape_negative
                )
                self.log(f"One-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding one-sided escape: {str(e)}", QMessageBox.Ok)
                self.log(f"One-sided escape placement error: {str(e)}")
                return False
            
        elif split[0].strip() == '2':
            if split[1].strip() == 'x':
                escape_y = False
            elif split[1].strip() == 'y':
                escape_y = True
            else:
                QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
                return False

            try:
                self.gds_design.add_regular_array_escape_two_sided(
                    trace_cell_name=Cell_Name,
                    center=Center,
                    layer_name=Layer,
                    pitch_x=float(Spacing_X),
                    pitch_y=float(Spacing_Y),
                    array_size_x=int(Copies_X),
                    array_size_y=int(Copies_Y),
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y
                )
                self.log(f"Two-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding two-sided escape: {str(e)}", QMessageBox.Ok)
                self.log(f"Two-sided escape placement error: {str(e)}")
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
                return False
            
            try:
                self.gds_design.add_regular_array_escape_three_sided(
                    trace_cell_name=Cell_Name,
                    center=Center,
                    layer_name=Layer,
                    pitch_x=float(Spacing_X),
                    pitch_y=float(Spacing_Y),
                    array_size_x=int(Copies_X),
                    array_size_y=int(Copies_Y),
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter),
                    escape_y=escape_y,
                    escape_negative=escape_negative
                )
                self.log(f"Three-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding three-sided escape: {str(e)}", QMessageBox.Ok)
                self.log(f"Three-sided escape placement error: {str(e)}")
                return False
        elif split[0].strip() == '4':
            try:
                self.gds_design.add_regular_array_escape_four_sided(
                    trace_cell_name=Cell_Name,
                    center=Center,
                    layer_name=Layer,
                    pitch_x=float(Spacing_X),
                    pitch_y=float(Spacing_Y),
                    array_size_x=int(Copies_X),
                    array_size_y=int(Copies_Y),
                    trace_width=float(Trace_Width),
                    pad_diameter=float(Pad_Diameter)
                )
                self.log(f"Four-sided escape added to {Cell_Name} on layer {Layer} at center {Center}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding four-sided escape: {str(e)}", QMessageBox.Ok)
                self.log(f"Four-sided escape placement error: {str(e)}")
                return False
        else:
            QMessageBox.critical(self, "Orientation Error", "Invalid orientation. Please enter a valid orientation.", QMessageBox.Ok)
            return False

    def addMLAAlignmentMark(self, Layer, Center, Outer_Rect_Width, Outer_Rect_Height, Interior_Width, Interior_X_Extent, Interior_Y_Extent, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding MLA Alignment Mark: {str(e)}", QMessageBox.Ok)
                self.log(f"MLA Alignment Mark placement error: {str(e)}")
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
                self.log(f"MLA Alignment Mark placement error: {str(e)}")
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
                self.log("MLA Alignment Mark placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the MLA Alignment Mark. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("MLA Alignment Mark placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
            "Layer": Layer,
            "Center": Center,
            "Outer Rect Width": Outer_Rect_Width,
            "Outer Rect Height": Outer_Rect_Height,
            "Interior Width": Interior_Width,
            "Interior X Extent": Interior_X_Extent,
            "Interior Y Extent": Interior_Y_Extent
        }
        self.logTestStructure("MLA Alignment Mark", params)  # Log the test structure details
        self.log(f"MLA Alignment Mark added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addResistanceTest(self, Layer, Center, Probe_Pad_Width, Probe_Pad_Height, Probe_Pad_Spacing, Plug_Width, Plug_Height, Trace_Width, Trace_Spacing, Switchbacks, X_Extent, Text_Height, Text, Add_Interlayer_Short, Layer_Name_Short, Short_Text, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Resistance Test: {str(e)}", QMessageBox.Ok)
                self.log(f"Resistance Test placement error: {str(e)}")
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
                self.log(f"Resistance Test placement error: {str(e)}")
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
                self.log("Resistance Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Resistance Test. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("Resistance Test placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
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
        self.log(f"Resistance Test added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addTraceTest(self, Layer, Center, Text, Line_Width, Line_Height, Num_Lines, Line_Spacing, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Trace Test: {str(e)}", QMessageBox.Ok)
                self.log(f"Trace Test placement error: {str(e)}")
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
                self.log(f"Trace Test placement error: {str(e)}")
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
                self.log("Trace Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Trace Test. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("Trace Test placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
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
        self.log(f"Trace Test added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addInterlayerViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rectangle_Spacing, Layer_1_Rectangle_Width, Layer_1_Rectangle_Height, Layer_2_Rectangle_Width, Layer_2_Rectangle_Height, Via_Width, Via_Height, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Interlayer Via Test: {str(e)}", QMessageBox.Ok)
                self.log(f"Interlayer Via Test placement error: {str(e)}")
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
                self.log(f"Interlayer Via Test placement error: {str(e)}")
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
                self.log("Interlayer Via Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Interlayer Via Test. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("Interlayer Via Test placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
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
        self.log(f"Interlayer Via Test added to {top_cell_name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")
        return True
    
    def addRectangle(self, Layer, Center, Width, Height, Lower_Left, Upper_Right, Rotation):
        top_cell_name = self.gds_design.top_cell_names[0]
        if (not Width or not Height or not Center) and (not Lower_Left or not Upper_Right):
            QMessageBox.critical(self, "Input Error", "Please enter either width and height or lower left and upper right coordinates for the rectangle.", QMessageBox.Ok)
            self.log("Rectangle add error: No dimensions provided")
            return False
        try:
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
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Rectangle: {str(e)}", QMessageBox.Ok)
            self.log(f"Rectangle placement error: {str(e)}")
            return False
        params = {
            "Layer": Layer,
            "Center": Center,
            "Width": Width,
            "Height": Height,
            "Lower Left": Lower_Left,
            "Upper Right": Upper_Right,
            "Rotation": Rotation
        }
        self.logTestStructure("Rectangle", params)  # Log the test structure details
        self.log(f"Rectangle added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addCircle(self, Layer, Center, Diameter):
        if not Diameter:
            QMessageBox.critical(self, "Input Error", "Please enter a diameter for the circle.", QMessageBox.Ok)
            self.log("Circle add error: No diameter provided")
            return False
        top_cell_name = self.gds_design.top_cell_names[0]
        try:
            self.gds_design.add_circle_as_polygon(
                cell_name=top_cell_name,
                center=Center,
                radius=float(Diameter)/2,
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Circle: {str(e)}", QMessageBox.Ok)
            self.log(f"Circle placement error: {str(e)}")
            return False
        params = {
            "Layer": Layer,
            "Center": Center,
            "Diameter": Diameter
        }
        self.logTestStructure("Circle", params)  # Log the test structure details
        self.log(f"Circle added to {top_cell_name} on layer {Layer} at center {Center}")
        return True
    
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
        try:
            self.gds_design.add_text(
                cell_name=top_cell_name,
                text=Text,
                layer_name=Layer,
                position=(rotated_x, rotated_y),
                height=float(Height),
                angle=float(Rotation)
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Text: {str(e)}", QMessageBox.Ok)
            self.log(f"Text placement error: {str(e)}")
            return False
        params = {
            "Layer": Layer,
            "Center": Center,
            "Text": Text,
            "Height": Height,
            "Rotation": Rotation
        }
        self.logTestStructure("Text", params)  # Log the test structure details
        self.log(f"Text added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addPolygon(self, Layer):
        Points = self.polygon_points
        if len(Points) < 3:
            QMessageBox.critical(self, "Input Error", "Please select a valid polygon points file.", QMessageBox.Ok)
            self.log("Polygon add error: Invalid points provided")
            return False
        top_cell_name = self.gds_design.top_cell_names[0]
        try:
            self.gds_design.add_polygon(
                cell_name=top_cell_name,
                points=Points,
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Polygon: {str(e)}", QMessageBox.Ok)
            self.log(f"Polygon placement error: {str(e)}")
            return False
        params = {
            "Layer": Layer,
            "Points": Points
        }
        self.logTestStructure("Polygon", params)  # Log the test structure details
        self.log(f"Polygon added to {top_cell_name} on layer {Layer}")
        return True

    def addPath(self, Layer, Width):
        Points = self.path_points
        if len(Points) < 2:
            QMessageBox.critical(self, "Input Error", "Please select a valid path points file.", QMessageBox.Ok)
            self.log("Path add error: No points provided")
            return False
        if not Width:
            QMessageBox.critical(self, "Input Error", "Please enter a width for the path.", QMessageBox.Ok)
            self.log("Path add error: No width provided")
            return False
        top_cell_name = self.gds_design.top_cell_names[0]
        try:
            self.gds_design.add_path_as_polygon(
                cell_name=top_cell_name,
                points=Points,
                width=float(Width),
                layer_name=Layer
            )
        except Exception as e:
            QMessageBox.critical(self, "Placement Error", f"Error adding Path: {str(e)}", QMessageBox.Ok)
            self.log(f"Path placement error: {str(e)}")
            return False
        params = {
            "Layer": Layer,
            "Points": Points,
            "Width": Width
        }
        self.logTestStructure("Path", params)  # Log the test structure details
        self.log(f"Path added to {top_cell_name} on layer {Layer}")
        return True

    def addElectronicsViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rect_Width, Layer_1_Rect_Height, Layer_2_Rect_Width, Layer_2_Rect_Height, Layer_2_Rect_Spacing, Via_Width, Via_Height, Via_Spacing, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Electronics Via Test: {str(e)}", QMessageBox.Ok)
                self.log(f"Electronics Via Test placement error: {str(e)}")
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
                self.log(f"Electronics Via Test placement error: {str(e)}")
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
                self.log("Electronics Via Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Electronics Via Test. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("Electronics Via Test placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
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
        self.log(f"Electronics Via Test added to {top_cell_name} with layers {Layer_Number_1}, {Layer_Number_2}, {Via_Layer} at center {Center}")
        return True

    def addShortTest(self, Layer, Center, Text, Rect_Width, Trace_Width, Num_Lines, Group_Spacing, Num_Groups, Num_Lines_Vert, Text_Height, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        if type(Center) == tuple:
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "Placement Error", f"Error adding Short Test: {str(e)}", QMessageBox.Ok)
                self.log(f"Short Test placement error: {str(e)}")
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
                self.log(f"Short Test placement error: {str(e)}")
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
                self.log("Short Test placement error: Substrate layer not set")
                return False
            available_space = self.availableSpace
            try:
                Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
            except ValueError:
                QMessageBox.critical(self, "Placement Error", "No space available for the Short Test. You may need to exclude a layer?", QMessageBox.Ok)
                self.log("Short Test placement error: No space available")
                return False
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
        else:
            # Show error message that either Automatic Placement must be true or the Center position is specified
            QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
            return False
        params = {
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
        self.log(f"Short Test added to {top_cell_name} on layer {Layer} at center {Center}")
        return True

    def addCustomTestStructure(self, Center, Magnification, Rotation, X_Reflection, Array, Copies_X, Copies_Y, Spacing_X, Spacing_Y, Automatic_Placement):
        top_cell_name = self.gds_design.top_cell_names[0]
        # If the custom cell is from another file, add it to the current design
        if self.custom_design is not None:
            if self.customTestCellName not in self.gds_design.lib.cells:
                self.gds_design.lib.add(self.custom_design.lib.cells[self.customTestCellName],
                                    overwrite_duplicate=True, include_dependencies=True, update_references=False)

        if self.customTestCellName:
            if not Array:
                if type(Center) == tuple:
                    try:
                        self.gds_design.add_cell_reference(
                            parent_cell_name=top_cell_name,
                            child_cell_name=self.customTestCellName,
                            origin=Center,
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure: {str(e)}", QMessageBox.Ok)
                        self.log(f"Custom Test Structure placement error: {str(e)}")
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
                        self.log(f"Custom Test Structure placement error: {str(e)}")
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
                        self.log("Custom Test Structure placement error: Substrate layer not set")
                        return False
                    available_space = self.availableSpace
                    try:
                        Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
                    except ValueError:
                        QMessageBox.critical(self, "Placement Error", "No space available for the Custom Test Structure. You may need to exclude a layer?", QMessageBox.Ok)
                        self.log("Custom Test Structure placement error: No space available")
                        return False
                    self.gds_design.add_cell_reference(
                        parent_cell_name=top_cell_name,
                        child_cell_name=self.customTestCellName,
                        origin=Center,
                        magnification=float(Magnification),
                        rotation=float(Rotation),
                        x_reflection=X_Reflection
                    )
                else:
                    # Show error message that either Automatic Placement must be true or the Center position is specified
                    QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
                    return False
                params = {
                    "Cell Name": self.customTestCellName,
                    "Center": Center,
                    "Magnification": Magnification,
                    "Rotation": Rotation,
                    "X Reflection": X_Reflection
                }
                self.logTestStructure("Custom Test Structure", params)  # Log the test structure details
                self.log(f"Custom Test Structure '{self.customTestCellName}' added to {top_cell_name} at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}")
                
                return True
            else:
                if type(Center) == tuple:
                    try:
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
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure Array: {str(e)}", QMessageBox.Ok)
                        self.log(f"Custom Test Structure Array placement error: {str(e)}")
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
                            spacing_x=float(Spacing_X),
                            spacing_y=float(Spacing_Y),
                            origin=(0,0),
                            magnification=float(Magnification),
                            rotation=float(Rotation),
                            x_reflection=X_Reflection
                        )
                    except Exception as e:
                        QMessageBox.critical(self, "Placement Error", f"Error adding Custom Test Structure Array: {str(e)}", QMessageBox.Ok)
                        self.log(f"Custom Test Structure Array placement error: {str(e)}")
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
                        self.log("Custom Test Structure placement error: Substrate layer not set")
                        return False
                    available_space = self.availableSpace
                    try:
                        Center = self.gds_design.find_position_for_rectangle(available_space, cell_width, cell_height, cell_offset)
                    except ValueError:
                        QMessageBox.critical(self, "Placement Error", "No space available for the Custom Test Structure. You may need to exclude a layer?", QMessageBox.Ok)
                        self.log("Custom Test Structure placement error: No space available")
                        return False
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
                else:
                    # Show error message that either Automatic Placement must be true or the Center position is specified
                    QMessageBox.critical(self, "Placement Error", "Please specify the center position or set Automatic Placement to True.", QMessageBox.Ok)
                    return False
                params = {
                    "Cell Name": self.customTestCellName,
                    "Center": Center,
                    "Magnification": Magnification,
                    "Rotation": Rotation,
                    "X Reflection": X_Reflection,
                    "Copies X": Copies_X,
                    "Copies Y": Copies_Y,
                    "Spacing X": Spacing_X,
                    "Spacing Y": Spacing_Y
                }
                self.logTestStructure("Custom Test Structure Array", params)  # Log the test structure details
                self.log(f"Custom Test Structure '{self.customTestCellName}' added to {top_cell_name} as an array at center {Center} with magnification {Magnification}, rotation {Rotation}, x_reflection {X_Reflection}, copies x {Copies_X}, copies y {Copies_Y}, spacing x {Spacing_X}, spacing y {Spacing_Y}")
                return True
            
    def handleCustomTestCellName(self):
        self.customTestCellName = self.customTestCellComboBox.currentText()
        self.log(f"Custom Test Structure Cell Name set to: {self.customTestCellName}")
        self.checkCustomTestCell()

    def checkCustomTestCell(self):
        if self.customTestCellName:
            if self.custom_design is not None:
                if self.customTestCellName in self.custom_design.lib.cells:
                    self.log(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
                else:
                    QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)
            else:
                if self.customTestCellName in self.gds_design.lib.cells:
                    self.log(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
                else:
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
        if self.gds_design is None:
            QMessageBox.critical(self, "Design Error", "No design loaded to define a new layer.", QMessageBox.Ok)
            self.log("Layer definition error: No design loaded")
            return
        if number and name:
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
