import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the GDS design
design = gdswriter.GDSDesign(size=(32000, 32000), units='um')

# Define layers
design.define_layer("Metal", 1, min_feature_size=1, min_spacing=1)
design.define_layer("Oxide", 2, min_feature_size=1, min_spacing=1)

# Parameters for circle creation
circle_diameter1 = 5  # Diameter for the larger circles in um
circle_diameter2 = 4.6   # Diameter for the smaller circles in um
circle_radius1 = circle_diameter1 / 2
circle_radius2 = circle_diameter2 / 2
array_size = 8  # Size of the arrays (16x16)
pitch = 30  # Pitch in um
routing_angle = 60
trace_width = 1.4
spacing_rout = (pitch - circle_diameter1 - (array_size*2-1)*trace_width)/2
assert spacing_rout > trace_width, "Trace width is too large for the given pitch"

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Electrode"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=circle_radius1, layer_name="Metal", num_points=100)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=circle_radius2, layer_name="Oxide", num_points=100)

# Create an array of the larger circle cell on 'Metal' layer
array_cell_name = "Electrode_Line"
design.add_cell(array_cell_name)
design.add_cell_array("Electrode_Line", circle_cell_name1, copies_x=array_size, copies_y=1, spacing_x=pitch, spacing_y=pitch,
                      origin=(0, 0))

start_x = -(array_size-1)*pitch/2
final_x_hinge = start_x + pitch*(array_size-1)+100
for i in range(array_size):
    y_val = pitch - circle_diameter1/2 - spacing_rout - i*trace_width*2 - trace_width/2
    hinge_points = gdswriter.create_hinged_path((start_x, 0), routing_angle, y_val, final_x_hinge)
    design.add_path_as_polygon("Electrode_Line", hinge_points, trace_width, "Metal")
    start_x += pitch

subunit_cell_name = "Array_subunit"
design.add_cell(subunit_cell_name)
design.add_cell_array(subunit_cell_name, array_cell_name, copies_x=1, copies_y=8, spacing_x=0, spacing_y=pitch, origin=(0, 0))

# design.add_cell_reference("TopCell", array_cell_name, 
#                       origin=(pitch/2+(array_size-1)*pitch/2, pitch/2+(array_size-1)*pitch/2))
# design.add_cell_reference("TopCell", array_cell_name, 
#                       origin=(-pitch/2-(array_size-1)*pitch/2, pitch/2+(array_size-1)*pitch/2), x_reflection=True)
# design.add_cell_reference("TopCell", array_cell_name,
#                       origin=(-pitch/2-(array_size-1)*pitch/2, -pitch/2-(array_size-1)*pitch/2), rotation=180)
# design.add_cell_reference("TopCell", array_cell_name, 
#                       origin=(pitch/2+(array_size-1)*pitch/2, -pitch/2-(array_size-1)*pitch/2), rotation=180, x_reflection=True)

# Create a cell with a single rectangle for 'Metal' layer and 'Oxide' layer
pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)
design.add_rectangle(pad_cell_name, layer_name="Oxide", center=(0, 0), width=100, height=1180)

# Create an array of the rectangle cell on 'Metal' layer and 'Oxide' layer
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, 16000-850))
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=128, spacing_x=200, spacing_y=0, origin=(0, -(16000-850)))

# Add alignment crosses
design.add_alignment_cross("TopCell", layer_name="Metal", center=(-350, -350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(-350, 350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(350, -350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(350, 350), width=10, extent_x=100, extent_y=100)

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design.gds")