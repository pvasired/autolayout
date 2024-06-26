import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(bounds=[-16000, 16000, -16000, 16000], unit=1e-6)

# Define layers
design.define_layer("Metal", 1, min_feature_size=1, min_spacing=5)
design.define_layer("Metal2", 3, min_feature_size=1, min_spacing=5)
design.define_layer("Via", 2, min_feature_size=1, min_spacing=5)

# Add alignment crosses
alignment_cross_name = "AlignmentCross"
design.add_cell(alignment_cross_name)
design.add_MLA_alignment_mark("AlignmentCross", layer_name="Metal", center=(0, 0))

# Add resistance test structure
resistance_test_name = "ResTest"
design.add_cell(resistance_test_name)
design.add_resistance_test_structure("ResTest", layer_name="Metal", center=(0, 0), trace_width=5,
                                     add_interlayer_short=True, layer_name_short="Metal2")

# Add line test structure
line_test_name = "LineTest"
design.add_cell(line_test_name)
design.add_line_test_structure("LineTest", layer_name="Metal", center=(0, 0), text="P MTL TRACE")

p_via_test_name = "P_Via_Test"
design.add_cell(p_via_test_name)
design.add_p_via_test_structure("P_Via_Test", layer_name_1="Metal", layer_name_2="Metal2", via_layer="Via", center=(0, 0), text="P VIA RESISTANCE",
                                via_width=10, via_height=10)

electronics_via_test_name = "Electronics_Via_Test"
design.add_cell(electronics_via_test_name)
design.add_electronics_via_test_structure("Electronics_Via_Test", layer_name_1="Metal", layer_name_2="Metal2", via_layer="Via", center=(0, 0), text="ELECTRONICS VIA RESISTANCE")

short_test_name = "ShortTest"
design.add_cell(short_test_name)
design.add_short_test_structure("ShortTest", layer_name="Metal", center=(0, 0), text="P-MTL SHORT", trace_width=5)

# # Add test structures to top cell
design.add_cell_reference("TopCell", alignment_cross_name, origin=(350, 350))
design.add_cell_reference("TopCell", resistance_test_name, origin=(-1000, 0))
design.add_cell_reference("TopCell", line_test_name, origin=(3000, 0))
design.add_cell_reference("TopCell", p_via_test_name, origin=(0, 3000))
design.add_cell_reference("TopCell", electronics_via_test_name, origin=(0, -3000))
design.add_cell_reference("TopCell", short_test_name, origin=(-3000, 3000))

# Run design rule checks
#design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design.gds")