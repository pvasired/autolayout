import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np
import gdsfactory as gf
import gdsfactory.routing as routing

array_size_x = 16
array_size_y = 16
pitch_x = 60
pitch_y = 60
escape_extent = 50
trace_width = 1.4
layer_number = 1
pad_diameter = 5
routing_angle = 45
center = (500, -500)
filename = "autorouting_test-output.gds"

def get_rotation_matrix(angle):
    angle = angle * np.pi / 180
    return np.array([
        [np.cos(angle), -np.sin(angle)],
        [np.sin(angle), np.cos(angle)]
        ])

# Initialize the GDS design
design = gdswriter.GDSDesign()

# Define layers
design.define_layer("Metal", layer_number)
design.define_layer("Test", 2)

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=pad_diameter/2, layer_name="Metal", num_points=100)

array_cell_name = "Electrode Array"
design.add_cell(array_cell_name)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array(array_cell_name, circle_cell_name1, copies_x=array_size_x, copies_y=array_size_y, spacing_x=pitch_x, spacing_y=pitch_y, origin=(0, 0))

# pad_cell_name = "Pad"
# design.add_cell(pad_cell_name)
# design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)

# pad_array_cell_name = "Pad Array"
# pad_spacing = 200
# pad_y = 10000
# design.add_cell(pad_array_cell_name)
# design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size**2/2), spacing_x=pad_spacing, spacing_y=0, origin=(0, pad_y))
# pad_ports_x = np.linspace(-(int(array_size**2/2)-1)/2*pad_spacing, (int(array_size**2/2)-1)/2*pad_spacing, int(array_size**2/2))
# pad_ports_top = np.vstack((pad_ports_x, np.ones(int(array_size**2/2))*pad_y)).T
# pad_ports_top[:, 0] = pad_ports_top[:, 0] + center[0]
# pad_ports_top[:, 1] = pad_ports_top[:, 1] + center[1]

# design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size**2/2), spacing_x=pad_spacing, spacing_y=0, origin=(0, -pad_y))
# pad_ports_bottom = np.vstack((pad_ports_x, np.ones(int(array_size**2/2))*-pad_y)).T
# pad_ports_bottom[:, 0] = pad_ports_bottom[:, 0] + center[0]
# pad_ports_bottom[:, 1] = pad_ports_bottom[:, 1] + center[1]

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

grid, ports = design.add_regular_array_escape_four_sided("Trace", layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle)

rotation = 0
design.add_cell_reference(array_cell_name, "Trace", origin=(0,0))
design.add_cell_reference("TopCell", array_cell_name, origin=center, rotation=rotation)
# design.add_cell_reference("TopCell", pad_array_cell_name, origin=center)

ports = (get_rotation_matrix(rotation) @ ports.T).T
grid = (get_rotation_matrix(rotation) @ grid.T).T

ports[:, 0] = ports[:, 0] + center[0]
ports[:, 1] = ports[:, 1] + center[1]
grid[:, 0] = grid[:, 0] + center[0]
grid[:, 1] = grid[:, 1] + center[1]

for i in range(ports.shape[0]):
    design.add_path_as_polygon("TopCell", [ports[i], grid[i]], 1, layer_name="Test")

# Write to a GDS file
design.write_gds(filename)

# gdspath = gf.read.import_gds(filename)
# cross_section = gf.cross_section.cross_section(width=trace_width, layer=(layer_number, 0))
# for i in range(len(ports_stack)):
#     gdspath.add_port(name=f"Electrode {i}", layer=(layer_number,0), width=trace_width, orientation=orientation_stack[i], center=ports_stack[i], cross_section=cross_section)

# for i in range(len(pad_ports_top)):
#     gdspath.add_port(name=f"Top Pad {i}", layer=(layer_number,0), width=trace_width, orientation=270, center=pad_ports_top[i], cross_section=cross_section)

# gdspath.pprint_ports()
# routing.route_bundle(gdspath, ports1=[gdspath.ports[f"Electrode {i}"] for i in [255, 254, 253, 252, 251, 250, 249, 248, 247]], 
#                      ports2=[gdspath.ports[f"Top Pad {i}"] for i in [0, 1, 2, 3, 4, 5, 6, 7, 8]], cross_section=cross_section)
# gdspath.write_gds(filename)
# import pdb; pdb.set_trace()