import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np
import gdsfactory as gf
import gdsfactory.routing as routing

array_size_x = 16
array_size_y = 16
pitch_x = 30
pitch_y = 30
escape_extent = 50
trace_width = 1.9
layer_number = 1
pad_diameter = 5
routing_angle = 45
center = (500, 1000)
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

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=pad_diameter/2, layer_name="Metal", num_points=100)

array_cell_name = "Electrode Array"
design.add_cell(array_cell_name)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array(array_cell_name, circle_cell_name1, copies_x=array_size_x, copies_y=array_size_y, spacing_x=pitch_x, spacing_y=pitch_y, origin=(0, 0))

pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)

pad_array_cell_name = "Pad Array"
pad_spacing = 200
pad_y = 10000
design.add_cell(pad_array_cell_name)
design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size_x*array_size_y/2), spacing_x=pad_spacing, spacing_y=0, origin=(0, pad_y))
pad_ports_x = np.linspace(-(int(array_size_x*array_size_y/2)-1)/2*pad_spacing, (int(array_size_x*array_size_y/2)-1)/2*pad_spacing, int(array_size_x*array_size_y/2))
pad_ports_top = np.vstack((pad_ports_x, np.ones(int(array_size_x*array_size_y/2))*pad_y)).T
pad_orientations_top = np.ones(len(pad_ports_top)) * 270

design.add_cell_array(pad_array_cell_name, pad_cell_name, copies_y=1, copies_x=int(array_size_x*array_size_y/2), spacing_x=pad_spacing, spacing_y=0, origin=(0, -pad_y))
pad_ports_bottom = np.vstack((pad_ports_x, np.ones(int(array_size_x*array_size_y/2))*-pad_y)).T
pad_orientations_bottom = np.ones(len(pad_ports_bottom)) * 90

pad_ports = np.vstack((pad_ports_top, pad_ports_bottom))
pad_orientations = np.concatenate((pad_orientations_top, pad_orientations_bottom))

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

grid, ports = design.add_regular_array_escape_four_sided("Trace", layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle)

rotation = 0
design.add_cell_reference(array_cell_name, "Trace", origin=(0,0))
design.add_cell_reference("TopCell", array_cell_name, origin=center, rotation=rotation)
design.add_cell_reference("TopCell", pad_array_cell_name, origin=center)

ports = (get_rotation_matrix(rotation) @ ports.T).T
grid = (get_rotation_matrix(rotation) @ grid.T).T

pad_ports = (get_rotation_matrix(rotation) @ pad_ports.T).T

ports[:, 0] = ports[:, 0] + center[0]
ports[:, 1] = ports[:, 1] + center[1]
grid[:, 0] = grid[:, 0] + center[0]
grid[:, 1] = grid[:, 1] + center[1]
pad_ports[:, 0] = pad_ports[:, 0] + center[0]
pad_ports[:, 1] = pad_ports[:, 1] + center[1]

# Write to a GDS file
design.write_gds(filename)

left_inds = np.where(ports[:, 0] == ports[:, 0].min())[0]
left_inds = left_inds[np.argsort(ports[left_inds][:, 1])]
left_orientations = np.ones(len(left_inds)) * 180

top_inds = np.where(ports[:, 1] == ports[:, 1].max())[0]
top_inds = top_inds[np.argsort(ports[top_inds][:, 0])]
top_orientations = np.ones(len(top_inds)) * 90

sorted_inds = np.concatenate((left_inds, top_inds))
orientations = np.concatenate((left_orientations, top_orientations))

gdspath = gf.read.import_gds(filename)
cross_section = gf.cross_section.cross_section(width=trace_width, layer=(layer_number, 0))

for i in range(len(pad_ports)):
    gdspath.add_port(name=f"Top Pad {i}", layer=(layer_number,0), width=trace_width, orientation=pad_orientations[i], center=pad_ports[i], cross_section=cross_section)

for i, idx in enumerate(sorted_inds):
    gdspath.add_port(name=f"Electrode {i}", layer=(layer_number,0), width=trace_width, orientation=orientations[i], 
                     center=ports[idx], cross_section=cross_section)

routing.route_bundle(gdspath, ports1=[gdspath.ports[f"Electrode {i}"] for i in range(len(sorted_inds))], 
                     ports2=[gdspath.ports[f"Top Pad {i}"] for i in range(len(sorted_inds))], cross_section=cross_section)

bottom_inds = np.where(ports[:, 1] == ports[:, 1].min())[0]
bottom_inds = bottom_inds[np.argsort(ports[bottom_inds][:, 0])]
bottom_orientations = np.ones(len(bottom_inds)) * 270

right_inds = np.where(ports[:, 0] == ports[:, 0].max())[0]
right_inds = right_inds[np.argsort(ports[right_inds][:, 1])]
right_orientations = np.ones(len(right_inds)) * 0

sorted_inds2 = np.concatenate((bottom_inds, right_inds))
orientations2 = np.concatenate((bottom_orientations, right_orientations))

for i, idx in enumerate(sorted_inds2):
    gdspath.add_port(name=f"Electrode {i + len(sorted_inds)}", layer=(layer_number,0), width=trace_width, orientation=orientations2[i], 
                     center=ports[idx], cross_section=cross_section)

gdspath.pprint_ports()

routing.route_bundle(gdspath, ports1=[gdspath.ports[f"Electrode {i}"] for i in range(len(sorted_inds), len(sorted_inds) + len(sorted_inds2))], 
                     ports2=[gdspath.ports[f"Top Pad {i}"] for i in range(len(sorted_inds), len(sorted_inds) + len(sorted_inds2))], cross_section=cross_section)

gdspath.write_gds(filename)