import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(filename='Test_Structures.GDS', default_feature_size=1, default_spacing=5)

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design-output.gds")