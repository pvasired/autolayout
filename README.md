# autolayout
This is a helper tool for automating certain tedious steps in .gds design. In particular, this tool is designed to streamline design of micro-electrode arrays (MEAs). The main features of the tool are:

- Semi-automated routing between components on a design
- Escape routing for regular rectangular arrays of components
- Transferring cells from one design to another
- Addition of parametric test structures
- Automated and semi-automated placement of dies and dicing streets on a multi-project wafer

# Installation
## Dependencies
The code relies heavily on some fantastic open-source software, namely [gdspy] (https://github.com/heitzmann/gdspy), [shapely] (https://shapely.readthedocs.io/en/stable/), and [phidl] (https://github.com/amccaugh/phidl). For specific versions see `requirements.txt`
- Python (tested with version 3.11.9)
- see `requirements.txt` for other required packages and versions

## PyInstaller setup
The tool can be compiled into a .exe using PyInstaller. This is currently the recommended way of using the tool. To create the .exe, run the command:

`pyinstaller --onedir --collect-all ENVIRONMENT_NAME --name PROGRAM_NAME --icon=./favicon.ico --windowed --add-data "favicon.ico;." main.py`

where `ENVIRONMENT_NAME` is the name of the conda environment with the required packages and `PROGRAM_NAME` is what you want to call the output .exe.
