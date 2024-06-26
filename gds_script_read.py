import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(filename='example_design.gds', default_feature_size=1, default_spacing=5)

# Define layers 1-3
design.define_layer("P-MTL", 1, min_feature_size=1, min_spacing=5)
design.define_layer("P-N VIA", 2, min_feature_size=1, min_spacing=5)
design.define_layer("N-MTL", 3, min_feature_size=1, min_spacing=5)

# Create layers 5-8
design.define_layer("Layer5", 5, min_feature_size=1, min_spacing=5)
design.define_layer("Layer6", 6, min_feature_size=1, min_spacing=5)
design.define_layer("Layer7", 7, min_feature_size=1, min_spacing=5)
design.define_layer("Layer8", 8, min_feature_size=1, min_spacing=5)
design.add_MLA_alignment_cell("Layer5", "Layer6", "Layer7", "Layer8")

# Create layers 9-12
design.define_layer("N VIA", 9, min_feature_size=1, min_spacing=5)
design.define_layer("OUTLINE", 10, min_feature_size=1, min_spacing=5)
design.define_layer("MTL 3", 11, min_feature_size=1, min_spacing=5)

# Add MLA alignment cell to top layer
design.add_cell_reference("TopCell", "MLA_Alignment", origin=(43000, 0))
design.add_cell_reference("TopCell", "MLA_Alignment", origin=(-43000, 0))
design.add_cell_reference("TopCell", "MLA_Alignment", origin=(0, 43000))
design.add_cell_reference("TopCell", "MLA_Alignment", origin=(0, -43000))

# Create test structure suite cell
test_suite_name = "TestSuite"
design.add_cell(test_suite_name)
design.add_short_test_structure(test_suite_name, layer_name="P-MTL", center=(0, 1300), text="P-MTL SHORT", trace_width=5)
design.add_short_test_structure(test_suite_name, layer_name="N-MTL", center=(0, -1300), text="N-MTL SHORT", trace_width=11)
design.add_p_via_test_structure(test_suite_name, layer_name_1="P-MTL", layer_name_2="N-MTL", via_layer="P-N VIA", center=(-2000, 3500), text="P VIA RESISTANCE", text_height=100)
design.add_p_via_test_structure(test_suite_name, layer_name_1="P-MTL", layer_name_2="N-MTL", via_layer="P-N VIA", center=(-1000, 3500), text="P VIA RESISTANCE", text_height=100)
design.add_p_via_test_structure(test_suite_name, layer_name_1="P-MTL", layer_name_2="N-MTL", via_layer="P-N VIA", center=(0, 3500), text="P VIA RESISTANCE", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="N VIA", center=(-2000, 2500), text="N VIA ETCH DEPTH", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="P-N VIA", center=(-1000, 2500), text="P VIA ETCH DEPTH", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="P-N VIA", center=(2750, -1300), text="P VIA ETCH DEPTH", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="P-MTL", center=(0, 2500), text="P METAL TRACE", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="N-MTL", center=(1000, 2500), text="N METAL TRACE", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="OUTLINE", center=(2500, 2500), text="OUTLINE PLUS VIA ETCH", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="OUTLINE", center=(1650, 1300), text="OUTLINE PLUS VIA ETCH", text_height=100)
design.add_line_test_structure(test_suite_name, layer_name="MTL 3", center=(3750, 2500), text="METAL 3 TRACE", text_height=100)
design.add_electronics_via_test_structure(test_suite_name, layer_name_1="P-MTL", layer_name_2="MTL 3", via_layer="OUTLINE", center=(3000, 3500), 
                                          text="ELECTRONICS VIA RESISTANCE", text_height=100)
design.add_resistance_test_structure(test_suite_name, layer_name="N-MTL", center=(5000, 0), trace_width=5, switchbacks=30, trace_spacing=30,
                                     add_interlayer_short=True, layer_name_short="P-MTL", short_text="P-N INTERLAYER SHORT",
                                     text="N-MTL", text_height=100)
design.add_resistance_test_structure(test_suite_name, layer_name="P-MTL", center=(7000, 0), trace_width=5,
                                     text="P-MTL", text_height=100)
design.add_resistance_test_structure(test_suite_name, layer_name="MTL 3", center=(9000, 0), trace_width=5,
                                     text="METAL 3", text_height=100)

# Add test suite to top cell
design.add_cell_reference("TopCell", test_suite_name, origin=(25000, 32000))
design.add_cell_reference("TopCell", test_suite_name, origin=(-32000, 32000))
design.add_cell_reference("TopCell", test_suite_name, origin=(25000, -32000))
design.add_cell_reference("TopCell", test_suite_name, origin=(-32000, -32000))

# Run design rule checks
#design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design-output.gds")