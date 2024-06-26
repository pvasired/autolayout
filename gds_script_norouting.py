import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(bounds=[-16000, 16000, -16000, 16000], unit=1e-6)

# Define layers
design.define_layer("Metal", 1, min_feature_size=1, min_spacing=5)
design.define_layer("Oxide", 2, min_feature_size=1, min_spacing=5)

# Parameters for circle creation
circle_diameter1 = 5  # Diameter for the larger circles in um
circle_diameter2 = 4.6   # Diameter for the smaller circles in um
circle_radius1 = circle_diameter1 / 2
circle_radius2 = circle_diameter2 / 2
array_size = 16  # Size of the arrays (16x16)
pitch = 30  # Pitch in um

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle5um"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=circle_radius1, layer_name="Metal", num_points=100)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array("TopCell", circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0))

# Create a cell with a single smaller circle for 'Oxide' layer
circle_cell_name2 = "Circle4um"
design.add_cell(circle_cell_name2)
design.add_circle_as_polygon(circle_cell_name2, center=(0, 0), radius=circle_radius2, layer_name="Oxide", num_points=100)

# Create an array of the smaller circle cell on 'Oxide' layer
design.add_cell_array("TopCell", circle_cell_name2, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0))

# Create a cell with a single rectangle for 'Metal' layer and 'Oxide' layer
pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)
design.add_rectangle(pad_cell_name, layer_name="Oxide", center=(0, 0), width=100, height=1180)

# Create an array of the rectangle cell on 'Metal' layer and 'Oxide' layer
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, 16000-850))
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, -(16000-850)))

# Add alignment crosses
alignment_cross_name = "AlignmentCross"
design.add_cell(alignment_cross_name)
design.add_MLA_alignment_mark("AlignmentCross", layer_name="Metal", center=(0, 0), add_text=True)

# Add resistance test structure
resistance_test_name = "ResTest"
design.add_cell(resistance_test_name)
design.add_resistance_test_structure("ResTest", layer_name="Metal", center=(0, 0),
                                     add_interlayer_short=True, layer_name_short="Oxide")

# Add line test structure
line_test_name = "LineTest"
design.add_cell(line_test_name)
design.add_line_test_structure("LineTest", layer_name="Metal", center=(0, 0), text="P MTL TRACE")

# Run design rule checks
#design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design.gds")