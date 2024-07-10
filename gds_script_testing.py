import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np
import gdsfactory as gf
import gdsfactory.routing as routing

array_size = 16
pitch_x = 60
pitch_y = 30
escape_extent = 50
trace_width = 1.9
layer_number = 1
pad_diameter = 5
routing_angle = 45
center = (500, -500)
filename = "autorouting_test-output.gds"

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
design.add_cell_array(array_cell_name, circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch_x, spacing_y=pitch_y, origin=(0, 0))

pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)

pad_array_cell_name = "Pad Array"
design.add_cell(pad_array_cell_name)
design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size**2/2), spacing_x=200, spacing_y=0, origin=(0, 10000))
design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size**2/2), spacing_x=200, spacing_y=0, origin=(0, -10000))

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

grid, ports = design.add_regular_array_escape("Trace1", layer_name, pitch_x, pitch_y, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=True)
grid2, ports2 = design.add_regular_array_escape("Trace2", layer_name, pitch_y, pitch_x, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=False)
grid3, ports3 = design.add_regular_array_escape("Trace3", layer_name, pitch_x, pitch_y, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=False)

def get_rotation_matrix(angle):
    angle = angle * np.pi / 180
    return np.array([
        [np.cos(angle), -np.sin(angle)],
        [np.sin(angle), np.cos(angle)]
        ])

rot90 = get_rotation_matrix(90)
rot180 = get_rotation_matrix(180)
rot270 = get_rotation_matrix(270)

rotated_ports2 = (rot90 @ ports2.T).T
rotated_grid2 = (rot90 @ grid2.T).T

rotated_ports3 = (rot180 @ ports3.T).T
rotated_grid3 = (rot180 @ grid3.T).T

rotated_ports4 = (rot270 @ ports2.T).T
rotated_grid4 = (rot270 @ grid2.T).T

ports_stack = np.vstack((ports[np.where(~np.isnan(ports).all(axis=1))[0]],
                            rotated_ports2[np.where(~np.isnan(rotated_ports2).all(axis=1))[0]],
                            rotated_ports3[np.where(~np.isnan(rotated_ports3).all(axis=1))[0]],
                            rotated_ports4[np.where(~np.isnan(rotated_ports4).all(axis=1))[0]]))
grid_stack = np.vstack((grid[np.where(~np.isnan(ports).all(axis=1))[0]],
                            rotated_grid2[np.where(~np.isnan(rotated_ports2).all(axis=1))[0]],
                            rotated_grid3[np.where(~np.isnan(rotated_ports3).all(axis=1))[0]],
                            rotated_grid4[np.where(~np.isnan(rotated_ports4).all(axis=1))[0]]))

ports_stack[:, 0] = ports_stack[:, 0] + center[0]
ports_stack[:, 1] = ports_stack[:, 1] + center[1]
grid_stack[:, 0] = grid_stack[:, 0] + center[0]
grid_stack[:, 1] = grid_stack[:, 1] + center[1]

design.add_cell_reference(array_cell_name, "Trace1", origin=(0, 0))
design.add_cell_reference(array_cell_name, "Trace2", origin=(0, 0), rotation=90)
design.add_cell_reference(array_cell_name, "Trace3", origin=(0, 0), rotation=180)
design.add_cell_reference(array_cell_name, "Trace2", origin=(0, 0), rotation=270)

design.add_cell_reference("TopCell", array_cell_name, origin=center)
design.add_cell_reference("TopCell", pad_array_cell_name, origin=center)

for i in range(ports_stack.shape[0]):
    design.add_path_as_polygon("TopCell", [ports_stack[i], grid_stack[i]], 1, layer_name="Test")

# Write to a GDS file
design.write_gds(filename)

gdspath = gf.read.import_gds(filename)
import pdb; pdb.set_trace()