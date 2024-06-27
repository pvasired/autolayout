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
            "MLA Alignment Mark": ["Layer", "Center", "Outer Rect Width", "Outer Rect Height", "Interior Width", "Interior X Extent", "Interior Y Extent"],
            "Resistance Test": ["Layer", "Center", "Probe Pad Width", "Probe Pad Height", "Probe Pad Spacing", "Plug Width", "Plug Height", "Trace Width", "Trace Spacing", "Switchbacks", "X Extent", "Text Height", "Text", "Add Interlayer Short", "Layer Name Short", "Short Text"],
            "Trace Test": ["Layer", "Center", "Text", "Line Width", "Line Height", "Num Lines", "Line Spacing", "Text Height"],
            "Interlayer Via Test": ["Layer Number 1", "Layer Number 2", "Via Layer", "Center", "Text", "Layer 1 Rectangle Spacing", "Layer 1 Rectangle Width", "Layer 1 Rectangle Height", "Layer 2 Rectangle Width", "Layer 2 Rectangle Height", "Via Width", "Via Height", "Text Height"],
            "Electronics Via Test": ["Layer Number 1", "Layer Number 2", "Via Layer", "Center", "Text", "Layer 1 Rect Width", "Layer 1 Rect Height", "Layer 2 Rect Width", "Layer 2 Rect Height", "Layer 2 Rect Spacing", "Via Width", "Via Height", "Via Spacing", "Text Height"],
            "Short Test": ["Layer", "Center", "Text", "Rect Width", "Trace Width", "Num Lines", "Group Spacing", "Num Groups", "Num Lines Vert", "Text Height"]
        }
        self.defaultParams = {
            "MLA Alignment Mark": {
                "Layer": None,
                "Center": None,
                "Outer Rect Width": 500,
                "Outer Rect Height": 20,
                "Interior Width": 5,
                "Interior X Extent": 50,
                "Interior Y Extent": 50
            },
            "Resistance Test": {
                "Layer": None,
                "Center": None,
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
                "Text": None,
                "Add Interlayer Short": False,
                "Layer Name Short": None,
                "Short Text": None
            },
            "Trace Test": {
                "Layer": None,
                "Center": None,
                "Text": None,
                "Line Width": 800,
                "Line Height": 80,
                "Num Lines": 4,
                "Line Spacing": 80,
                "Text Height": 100
            },
            "Interlayer Via Test": {
                "Layer Number 1": None,
                "Layer Number 2": None,
                "Via Layer": None,
                "Center": None,
                "Text": None,
                "Layer 1 Rectangle Spacing": 150,
                "Layer 1 Rectangle Width": 700,
                "Layer 1 Rectangle Height": 250,
                "Layer 2 Rectangle Width": 600,
                "Layer 2 Rectangle Height": 550,
                "Via Width": 7,
                "Via Height": 7,
                "Text Height": 100
            },
            "Electronics Via Test": {
                "Layer Number 1": None,
                "Layer Number 2": None,
                "Via Layer": None,
                "Center": None,
                "Text": None,
                "Layer 1 Rect Width": 1550,
                "Layer 1 Rect Height": 700,
                "Layer 2 Rect Width": 600,
                "Layer 2 Rect Height": 600,
                "Layer 2 Rect Spacing": 250,
                "Via Width": 7,
                "Via Height": 7,
                "Via Spacing": 10,
                "Text Height": 100
            },
            "Short Test": {
                "Layer": None,
                "Center": None,
                "Text": None,
                "Rect Width": 1300,
                "Trace Width": 5,
                "Num Lines": 5,
                "Group Spacing": 130,
                "Num Groups": 6,
                "Num Lines Vert": 100,
                "Text Height": 100
            }
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
            testCheckBox.stateChanged.connect(self.createCheckStateHandler(name))
            paramLabel = QLabel('Parameters')
            paramComboBox = QComboBox()
            paramComboBox.addItems(self.parameters[name])
            paramComboBox.currentTextChanged.connect(self.createParamChangeHandler(name))
            paramValueEdit = QLineEdit()
            paramName = paramComboBox.currentText()
            if paramName in self.defaultParams[name]:
                paramValueEdit.setText(str(self.defaultParams[name][paramName]))
            paramValueEdit.editingFinished.connect(self.createParamStoreHandler(paramComboBox, paramValueEdit, name))
            addButton = QPushButton("Add to Design")
            addButton.clicked.connect(self.createAddToDesignHandler(name))

            gridLayout.addWidget(testCheckBox, row, 0)
            gridLayout.addWidget(paramLabel, row, 1)
            gridLayout.addWidget(paramComboBox, row, 2)
            gridLayout.addWidget(paramValueEdit, row, 3)
            gridLayout.addWidget(addButton, row, 4)
            row += 1

            defaultParams = self.defaultParams[name]
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
        writeButton.clicked.connect(self.writeToGDS)
        substrateLayout.addWidget(writeButton)

        mainLayout.addLayout(substrateLayout)

        self.setLayout(mainLayout)
        self.setWindowTitle('Test Structure Automation GUI')
        self.show()

    def log(self, message):
        if self.verbose:
            print(message)

    def createCheckStateHandler(self, name):
        return lambda state: self.log(f"{name} {'selected' if state == Qt.Checked else 'unselected'}")

    def createParamChangeHandler(self, name):
        return lambda param: self.updateParameterValue(param, name)

    def createParamStoreHandler(self, comboBox, valueEdit, name):
        return lambda: self.storeParameterValue(comboBox, valueEdit, name)

    def createAddToDesignHandler(self, name):
        return lambda: self.handleAddToDesign(name)

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
        if outputFileName.lower().endswith('.gds'):
            self.outputFileName = outputFileName
            self.log(f"Output File set to: {self.outputFileName}")
        else:
            QMessageBox.critical(self, "File Error", "Output file must be a .gds file.", QMessageBox.Ok)
            self.outFileField.setText(self.outputFileName)
            self.log("Output file validation error: Not a .gds file")

    def updateParameterValue(self, param, testStructureName):
        for _, comboBox, valueEdit, defaultParams in self.testStructures:
            if comboBox.currentText() == param:
                default_value = defaultParams.get(param, '')
                valueEdit.setText(str(default_value))
                self.log(f"{testStructureName} Parameter {param} selected, default value set to {default_value}")

    def storeParameterValue(self, comboBox, valueEdit, name):
        param = comboBox.currentText()
        value = valueEdit.text()
        if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer":
            value = self.validateLayer(value)
        elif param == "Center":
            value = self.validateCenter(value)
        for i, (checkBox, cb, edit, defaultParams) in enumerate(self.testStructures):
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
                    return name  # Return the layer name instead of number
        else:
            for number, name in self.layerData:
                if name == layer:
                    self.log(f"Layer name {layer} is valid")
                    return name
        self.log("Invalid layer")
        QMessageBox.critical(self, "Layer Error", "Invalid layer. Please select a valid layer.", QMessageBox.Ok)
        return None

    def validateCenter(self, center):
        self.log(f"Validating Center: {center}")
        if isinstance(center, tuple):
            return center
        center = center.replace("(", "").replace(")", "").replace(" ", "")
        try:
            x, y = map(float, center.split(','))
            self.log(f"Center is valid: ({x}, {y})")
            return (x, y)
        except ValueError:
            self.log("Invalid center")
            QMessageBox.critical(self, "Center Error", "Invalid center. Please enter a valid (x, y) coordinate.", QMessageBox.Ok)
            return None

    def handleAddToDesign(self, testStructureName):
        self.log(f"Adding {testStructureName} to design")
        if testStructureName == "MLA Alignment Mark":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addMLAAlignmentMark(**params)
        elif testStructureName == "Resistance Test":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addResistanceTest(**params)
        elif testStructureName == "Trace Test":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addTraceTest(**params)
        elif testStructureName == "Interlayer Via Test":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addInterlayerViaTest(**params)
        elif testStructureName == "Electronics Via Test":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addElectronicsViaTest(**params)
        elif testStructureName == "Short Test":
            params = self.getParameters(testStructureName)
            self.log(f"Parameters: {params}")
            if params:
                self.addShortTest(**params)

    def getParameters(self, testStructureName):
        params = {}
        for testCheckBox, comboBox, valueEdit, defaultParams in self.testStructures:
            if testCheckBox.text() == testStructureName:
                for param in self.parameters[testStructureName]:
                    value = defaultParams.get(param, valueEdit.text())
                    self.log(f"Getting parameter {param}: {value}")
                    if param == "Layer" or param == "Layer Number 1" or param == "Layer Number 2" or param == "Via Layer":
                        value = self.validateLayer(value)
                    elif param == "Center":
                        value = self.validateCenter(value)
                    elif type(value) == str:
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        elif value.lower() == 'none':
                            value = None
                    params[param.replace(" ", "_")] = value
        return params

    def addMLAAlignmentMark(self, Layer, Center, Outer_Rect_Width, Outer_Rect_Height, Interior_Width, Interior_X_Extent, Interior_Y_Extent):
        top_cell_name = self.gds_design.top_cell_names[0]
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

    def addResistanceTest(self, Layer, Center, Probe_Pad_Width, Probe_Pad_Height, Probe_Pad_Spacing, Plug_Width, Plug_Height, Trace_Width, Trace_Spacing, Switchbacks, X_Extent, Text_Height, Text, Add_Interlayer_Short, Layer_Name_Short, Short_Text):
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
            layer_name_short=self.validateLayer(Layer_Name_Short) if Layer_Name_Short else Layer_Name_Short
        )
        self.log(f"Resistance Test added to {top_cell_name} on layer {Layer} at center {Center}")

    def addTraceTest(self, Layer, Center, Text, Line_Width, Line_Height, Num_Lines, Line_Spacing, Text_Height):
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

    def addInterlayerViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rectangle_Spacing, Layer_1_Rectangle_Width, Layer_1_Rectangle_Height, Layer_2_Rectangle_Width, Layer_2_Rectangle_Height, Via_Width, Via_Height, Text_Height):
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

    def addElectronicsViaTest(self, Layer_Number_1, Layer_Number_2, Via_Layer, Center, Text, Layer_1_Rect_Width, Layer_1_Rect_Height, Layer_2_Rect_Width, Layer_2_Rect_Height, Layer_2_Rect_Spacing, Via_Width, Via_Height, Via_Spacing, Text_Height):
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

    def addShortTest(self, Layer, Center, Text, Rect_Width, Trace_Width, Num_Lines, Group_Spacing, Num_Groups, Num_Lines_Vert, Text_Height):
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

    def handleCustomTestStructure(self, state):
        if state == Qt.Checked:
            self.log("Custom Test Structure enabled")
            self.checkCustomTestCell()
        else:
            self.log("Custom Test Structure disabled")

    def handleCustomTestCellName(self):
        self.customTestCellName = self.customTestCellNameEdit.text()
        self.log(f"Custom Test Structure Cell Name set to: {self.customTestCellName}")
        self.checkCustomTestCell()

    def checkCustomTestCell(self):
        if self.customTestCellName:
            try:
                self.gds_design.check_cell_exists(self.customTestCellName)
                self.log(f"Custom Test Structure Cell '{self.customTestCellName}' found in design.")
            except ValueError:
                QMessageBox.critical(self, "Input Error", "The test structure cell you specified was not found in the .gds file.", QMessageBox.Ok)

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
    ex = MyApp(verbose=args.verbose)
    sys.exit(app.exec_())
