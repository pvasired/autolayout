<<<<<<< HEAD
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(filename='Test_Structures.GDS')

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
=======
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(filename='Test_Structures.GDS')

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
>>>>>>> dcc204cbed7cce4a3e34a37e29f00ed11a775138
design.write_gds("example_design-output.gds")