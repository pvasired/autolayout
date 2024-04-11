import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(size=(32000, 32000), units='um')

# Define layers
design.define_layer("Metal", 1, min_feature_size=1, min_spacing=1)
design.define_layer("Oxide", 2, min_feature_size=1, min_spacing=1)

# # Add some geometric shapes
# design.add_rectangle("TopCell", layer_name="Metal", lower_left=(10, 10), upper_right=(100, 50))
# design.add_circle_as_polygon("TopCell", center=(200, 200), radius=50, layer_name="Via", num_points=100)
# points = [(300, 300), (400, 400), (500, 300), (400, 200)]
# design.add_path_as_polygon("TopCell", points=points, width=10, layer_name="Metal")

# Parameters for circle creation
circle_diameter1 = 5  # Diameter for the larger circles in um
circle_diameter2 = 4   # Diameter for the smaller circles in um
circle_radius1 = circle_diameter1 / 2
circle_radius2 = circle_diameter2 / 2
array_size = 16  # Size of the arrays (16x16)
pitch = 30  # Pitch in um

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle10um"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=circle_radius1, layer_name="Metal", num_points=100)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array("TopCell", circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0))

# Create a cell with a single smaller circle for 'Via' layer
circle_cell_name2 = "Circle8um"
design.add_cell(circle_cell_name2)
design.add_circle_as_polygon(circle_cell_name2, center=(0, 0), radius=circle_radius2, layer_name="Oxide", num_points=100)

# Create an array of the smaller circle cell on 'Via' layer
design.add_cell_array("TopCell", circle_cell_name2, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0))

pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)
design.add_rectangle(pad_cell_name, layer_name="Oxide", center=(0, 0), width=100, height=1180)

design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, 16000-850))
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, -(16000-850)))

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design.gds")
