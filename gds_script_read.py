import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(filename='example_design.gds', default_feature_size=1, default_spacing=5)

short_test_name = "ShortTest2"
design.add_cell(short_test_name)
design.add_short_test_structure("ShortTest2", layer_name="Layer3", center=(0, 0), text="N-MTL SHORT", trace_width=12)

design.add_cell_reference("TopCell", short_test_name, origin=(-40350, 4350))

# Create layers 5-8
design.define_layer("Layer5", 5, min_feature_size=1, min_spacing=5)
design.define_layer("Layer6", 6, min_feature_size=1, min_spacing=5)
design.define_layer("Layer7", 7, min_feature_size=1, min_spacing=5)
design.define_layer("Layer8", 8, min_feature_size=1, min_spacing=5)
design.add_MLA_alignment_cell("Layer5", "Layer6", "Layer7", "Layer8")

# Add MLA alignment cell to top layer
design.add_cell_reference("TopCell", "MLA_Alignment", origin=(43000, 0))
# Run design rule checks
#design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design-output.gds")