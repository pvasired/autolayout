import sys
import argparse
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit, QFileDialog, QMessageBox, QComboBox, QGridLayout
)
from PyQt5.QtCore import Qt
from gdswriter import GDSDesign  # Import the GDSDesign class

class MyApp(QWidget):
    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose
        self.inputFileName = ""
        self.outputFileName = ""
        self.customTestCellName = ""
        self.customSubstrateWidth = 0.0
        self.customSubstrateHeight = 0.0
        self.layerData = []  # To store layer numbers and names
        self.testStructureNames = [
            "MLA Alignment Mark", "Resistance Test", "Trace Test", 
            "Interlayer Via Test", "Electronics Via Test", "Short Test"
        ]
        self.parameters = {
            "MLA Alignment Mark": ["Par1", "Par2", "Par3"],
            "Resistance Test": ["Par1", "Par2", "Par3"],
            "Trace Test": ["Par1", "Par2", "Par3"],
            "Interlayer Via Test": ["Par1", "Par2", "Par3"],
            "Electronics Via Test": ["Par1", "Par2", "Par3"],
            "Short Test": ["Par1", "Par2", "Par3"]
        }
        self.testStructures = []  # Initialize testStructures here
        self.gds_design = None  # To store the GDSDesign instance
        self.initUI()

    def initUI(self):
        # Main Layout
        mainLayout = QVBoxLayout()

        # File selection layout
        fileLayout = QHBoxLayout()
        self.initFileButton = QPushButton('Select Input File')
        self.initFileButton.clicked.connect(self.selectInputFile)
        self.outFileField = QLineEdit()
        self.outFileField.setPlaceholderText('Output File')
        self.outFileField.editingFinished.connect(self.validateOutputFileName)
        fileLayout.addWidget(self.initFileButton)
        fileLayout.addWidget(self.outFileField)
        mainLayout.addLayout(fileLayout)

        # Test Structures layout
        testLayout = QVBoxLayout()
        testLabel = QLabel('Test Structures')
        testLayout.addWidget(testLabel)

        gridLayout = QGridLayout()
        row = 0
        for name in self.testStructureNames:
            testCheckBox = QCheckBox(name)
            testCheckBox.stateChanged.connect(lambda state, n=name: self.log(f"{n} {'selected' if state == Qt.Checked else 'unselected'}"))
            paramLabel = QLabel('Parameters')
            paramComboBox = QComboBox()
            paramComboBox.addItems(self.parameters[name])
            paramComboBox.currentTextChanged.connect(self.updateParameterValue)
            paramValueEdit = QLineEdit()
            paramValueEdit.setPlaceholderText('9999')
            paramValueEdit.setText('9999')
            paramValueEdit.editingFinished.connect(lambda cb=paramComboBox, edit=paramValueEdit, name=name: self.storeParameterValue(cb, edit, name))

            gridLayout.addWidget(testCheckBox, row, 0)
            gridLayout.addWidget(paramLabel, row, 1)
            gridLayout.addWidget(paramComboBox, row, 2)
            gridLayout.addWidget(paramValueEdit, row, 3)
            row += 1

            defaultParams = {param: '9999' for param in self.parameters[name]}
            self.testStructures.append((testCheckBox, paramComboBox, paramValueEdit, defaultParams))

        testLayout.addLayout(gridLayout)

        # Custom test structure layout
        customTestLayout = QHBoxLayout()
        self.customTestCheckBox = QCheckBox("Custom Test Structure")
        self.customTestCheckBox.stateChanged.connect(self.handleCustomTestStructure)
        self.customTestCellNameEdit = QLineEdit()
        self.customTestCellNameEdit.setPlaceholderText("Custom Test Structure Cell Name")
        self.customTestCellNameEdit.editingFinished.connect(self.handleCustomTestCellName)
        customTestLayout.addWidget(self.customTestCheckBox)
        customTestLayout.addWidget(self.customTestCellNameEdit)
        testLayout.addLayout(customTestLayout)

        mainLayout.addLayout(testLayout)

        # Substrate layout
        substrateLayout = QVBoxLayout()
        substrateLabel = QLabel('Substrate')
        self.checkbox4Inch = QCheckBox('4"')
        self.checkbox4Inch.stateChanged.connect(lambda state: self.log(f"4\" substrate {'selected' if state == Qt.Checked else 'unselected'}"))
        self.checkbox6Inch = QCheckBox('6"')
        self.checkbox6Inch.stateChanged.connect(lambda state: self.log(f"6\" substrate {'selected' if state == Qt.Checked else 'unselected'}"))
        self.customCheckbox = QCheckBox('Custom Size')
        self.customCheckbox.stateChanged.connect(self.toggleCustomSize)
        self.customSizeEdit = QLineEdit()
        self.customSizeEdit.setPlaceholderText('Width (mm) x Height (mm)')
        self.customSizeEdit.setEnabled(False)
        self.customSizeEdit.editingFinished.connect(self.handleCustomSizeChange)
        substrateLayout.addWidget(substrateLabel)
        substrateLayout.addWidget(self.checkbox4Inch)
        substrateLayout.addWidget(self.checkbox6Inch)
        substrateLayout.addWidget(self.customCheckbox)
        substrateLayout.addWidget(self.customSizeEdit)

        # Layers layout
        layersLayout = QVBoxLayout()
        layersLabel = QLabel('Layers')
        layersLayout.addWidget(layersLabel)

        self.layersComboBox = QComboBox()
        layersLayout.addWidget(self.layersComboBox)

        defineLayerLayout = QHBoxLayout()
        self.newLayerNumberEdit = QLineEdit()
        self.newLayerNumberEdit.setPlaceholderText('Layer Number')
        self.newLayerNameEdit = QLineEdit()
        self.newLayerNameEdit.setPlaceholderText('Layer Name')
        defineLayerButton = QPushButton('Define New Layer')
        defineLayerButton.clicked.connect(self.defineNewLayer)
        defineLayerLayout.addWidget(self.newLayerNumberEdit)
        defineLayerLayout.addWidget(self.newLayerNameEdit)
        defineLayerLayout.addWidget(defineLayerButton)
        layersLayout.addLayout(defineLayerLayout)

        substrateLayout.addLayout(layersLayout)

        # Write to GDS button
        writeButton = QPushButton('Write to GDS')
        writeButton.clicked.connect(self.uploadFile)
        substrateLayout.addWidget(writeButton)

        mainLayout.addLayout(substrateLayout)

        self.setLayout(mainLayout)
        self.setWindowTitle('Test Structure Automation GUI')
        self.show()

    def log(self, message):
        if self.verbose:
            print(message)

    def selectInputFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "GDS Files (*.gds);;All Files (*)", options=options)
        if fileName:
            if fileName.endswith('.gds'):
                self.inputFileName = fileName
                self.log(f"Input File: {self.inputFileName}")
                baseName = fileName.rsplit('.', 1)[0]
                self.outputFileName = f"{baseName}-output.gds"
                self.outFileField.setText(self.outputFileName)
                self.log(f"Output File automatically set to: {self.outputFileName}")

                # Load the GDS file using GDSDesign
                self.gds_design = GDSDesign(filename=self.inputFileName)
                self.layerData = [(str(layer['number']), layer_name) for layer_name, layer in self.gds_design.layers.items()]
                self.log(f"Layers read from file: {self.layerData}")
                self.updateLayersComboBox()
            else:
                QMessageBox.critical(self, "File Error", "Please select a .gds file.", QMessageBox.Ok)
                self.log("File selection error: Not a .gds file")

    def updateLayersComboBox(self):
        self.layersComboBox.clear()
        for number, name in self.layerData:
            self.layersComboBox.addItem(f"{number}: {name}")
        self.log("Layers dropdown updated")

    def validateOutputFileName(self):
        outputFileName = self.outFileField.text()
        if outputFileName.endswith('.gds'):
            self.outputFileName = outputFileName
            self.log(f"Output File set to: {self.outputFileName}")
        else:
            QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
            self.outFileField.setText(self.outputFileName)
            self.log("Output file validation error: Not a .gds file")

    def updateParameterValue(self, param):
        for _, comboBox, valueEdit, defaultParams in self.testStructures:
            if comboBox.currentText() == param:
                valueEdit.setText(defaultParams.get(param, ''))
                self.log(f"Parameter {param} selected, default value set")

    def storeParameterValue(self, comboBox, valueEdit, name):
        param = comboBox.currentText()
        value = valueEdit.text()
        for i, (checkBox, cb, edit, defaultParams) in enumerate(self.testStructures):
            if cb == comboBox:
                if param in defaultParams:
                    self.testStructures[i][3][param] = value
                    self.log(f"{name} {param} updated to {value}")

    def handleCustomTestStructure(self, state):
        if state == Qt.Checked:
            self.log("Custom Test Structure enabled")
        else:
            self.log("Custom Test Structure disabled")

    def handleCustomTestCellName(self):
        self.customTestCellName = self.customTestCellNameEdit.text()
        self.log(f"Custom Test Structure Cell Name set to: {self.customTestCellName}")

    def toggleCustomSize(self, state):
        if state == Qt.Checked:
            self.customSizeEdit.setEnabled(True)
            self.log("Custom Size enabled")
        else:
            self.customSizeEdit.setEnabled(False)
            self.log("Custom Size disabled")

    def handleCustomSizeChange(self):
        size_text = self.customSizeEdit.text()
        match = re.match(r'^\s*(\d*\.?\d*)\s*[xX]\s*(\d*\.?\d*)\s*$', size_text)
        if match:
            self.customSubstrateWidth = float(match.group(1))
            self.customSubstrateHeight = float(match.group(2))
            self.log(f"Custom Size set to: {self.customSubstrateWidth} mm x {self.customSubstrateHeight} mm")
        else:
            QMessageBox.critical(self, "Input Error", "Please enter size in 'Width (mm) x Height (mm)' format.", QMessageBox.Ok)
            self.log("Custom Size input error: Incorrect format")

    def uploadFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "Upload File", "", "All Files ();;Text Files (.txt)", options=options)
        if fileName:
            self.log(f"Uploaded File: {fileName}")

    def defineNewLayer(self):
        number = self.newLayerNumberEdit.text().strip()
        name = self.newLayerNameEdit.text().strip()
        if number and name:
            for i, (layer_number, layer_name) in enumerate(self.layerData):
                if layer_number == number:
                    old_name = self.layerData[i][1]
                    self.layerData[i] = (number, name)
                    self.updateLayersComboBox()
                    self.log(f"Layer {number} name updated from {old_name} to {name}")
                    print(f"Layer {number} name updated from {old_name} to {name}")
                    return
            self.layerData.append((number, name))
            self.updateLayersComboBox()
            self.log(f"New Layer added: {number} - {name}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the PyQt5 GUI application.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose mode')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    ex = MyApp(verbose=args.verbose)
    sys.exit(app.exec_())