import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np

array_size_x = 18
array_size_y = 18
pitch_x = 100
pitch_y = 200
escape_extent = 50
trace_width = 5
layer_number = 1
pad_diameter = 10
routing_angle = 45
center = (500, -500)
filename = "autorouting_test-output.gds"

# Initialize the GDS design
design = gdswriter.GDSDesign()

# Define layers
design.define_layer("Metal", layer_number)

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=pad_diameter/2, layer_name="Metal", num_points=100)

array_cell_name = "Electrode Array"
design.add_cell(array_cell_name)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array(array_cell_name, circle_cell_name1, copies_x=array_size_x, copies_y=array_size_y, spacing_x=pitch_x, spacing_y=pitch_y, origin=(0, 0))

pad_pitch_x = 100
pad_pitch_y = 100
pad_array_cell_name = "Pad Array"
design.add_cell(pad_array_cell_name)
center_pad = (-10000, 10000)
design.add_cell_array(pad_array_cell_name, circle_cell_name1, copies_x=array_size_x, copies_y=array_size_y, spacing_x=pad_pitch_x, spacing_y=pad_pitch_y, origin=(0, 0))
pad_grid, pad_ports, pad_orientations = design.add_regular_array_escape_four_sided(pad_array_cell_name, (0, 0), layer_name, pad_pitch_x, pad_pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle,
                                                                                  )

grid, ports, orientations = design.add_regular_array_escape_four_sided(array_cell_name, (0, 0), layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle,
                                                                    )
design.add_cell_reference("TopCell", array_cell_name, origin=center)
design.add_cell_reference("TopCell", pad_array_cell_name, origin=center_pad)

top_inds_elec = np.where(orientations == 90)[0]
top_inds_elec = top_inds_elec[np.argsort(ports[top_inds_elec][:, 0])]
left_inds_elec = np.where(orientations == 180)[0]
left_inds_elec = left_inds_elec[np.argsort(ports[left_inds_elec][:, 1])]
right_inds_elec = np.where(orientations == 0)[0]
right_inds_elec = right_inds_elec[np.flip(np.argsort(ports[right_inds_elec][:, 1]))]
bottom_inds_elec = np.where(orientations == 270)[0]
bottom_inds_elec = bottom_inds_elec[np.flip(np.argsort(ports[bottom_inds_elec][:, 0]))]

top_inds_pad = np.where(pad_orientations == 90)[0]
top_inds_pad = top_inds_pad[np.argsort(pad_ports[top_inds_pad][:, 0])]
left_inds_pad = np.where(pad_orientations == 180)[0]
left_inds_pad = left_inds_pad[np.argsort(pad_ports[left_inds_pad][:, 1])]
right_inds_pad = np.where(pad_orientations == 0)[0]
right_inds_pad = right_inds_pad[np.flip(np.argsort(pad_ports[right_inds_pad][:, 1]))]
bottom_inds_pad = np.where(pad_orientations == 270)[0]
bottom_inds_pad = bottom_inds_pad[np.flip(np.argsort(pad_ports[bottom_inds_pad][:, 0]))]

top_wire_ports, top_wire_orientations = design.cable_tie_ports(array_cell_name, layer_name, ports[top_inds_elec], orientations[top_inds_elec], trace_width)
left_wire_ports, left_wire_orientations = design.cable_tie_ports(array_cell_name, layer_name, ports[left_inds_elec], orientations[left_inds_elec], trace_width)
right_wire_ports, right_wire_orientations = design.cable_tie_ports(array_cell_name, layer_name, ports[right_inds_elec], orientations[right_inds_elec], trace_width)
bot_wire_ports, bot_wire_orientations = design.cable_tie_ports(array_cell_name, layer_name, ports[bottom_inds_elec], orientations[bottom_inds_elec], trace_width)

top_wire_ports_pad, top_wire_orientations_pad = design.cable_tie_ports(pad_array_cell_name, layer_name, pad_ports[top_inds_pad], pad_orientations[top_inds_pad], trace_width)
left_wire_ports_pad, left_wire_orientations_pad = design.cable_tie_ports(pad_array_cell_name, layer_name, pad_ports[left_inds_pad], pad_orientations[left_inds_pad], trace_width)
right_wire_ports_pad, right_wire_orientations_pad = design.cable_tie_ports(pad_array_cell_name, layer_name, pad_ports[right_inds_pad], pad_orientations[right_inds_pad], trace_width)
bot_wire_ports_pad, bot_wire_orientations_pad = design.cable_tie_ports(pad_array_cell_name, layer_name, pad_ports[bottom_inds_pad], pad_orientations[bottom_inds_pad], trace_width)

width, height, offset = design.calculate_cell_size(pad_array_cell_name)
offset = np.array(offset)
lower_left = offset + center_pad - np.array([width/2, height/2])
upper_right = offset + center_pad + np.array([width/2, height/2])
bbox2 = np.array([lower_left, upper_right])

width, height, offset = design.calculate_cell_size(array_cell_name)
offset = np.array(offset)
lower_left = offset + center - np.array([width/2, height/2])
upper_right = offset + center + np.array([width/2, height/2])
bbox1 = np.array([lower_left, upper_right])

design.write_gds(filename)

show_animation = False
obstacles = []

# Get polygons from the layer in top cells
layer_polygons = []
for top_cell_name in design.top_cell_names:
    cell = design.check_cell_exists(top_cell_name)
    polygons_by_spec = cell.get_polygons(by_spec=True)
    for (lay, dat), polys in polygons_by_spec.items():
        if lay == layer_number:
            for poly in polys:
                layer_polygons.append(poly)
                # Check if poly is in bbox1 or bbox2:
                if np.all(poly[:, 0] >= bbox1[0][0]) and np.all(poly[:, 0] <= bbox1[1][0]) and np.all(poly[:, 1] >= bbox1[0][1]) and np.all(poly[:, 1] <= bbox1[1][1]):
                    continue
                if np.all(poly[:, 0] >= bbox2[0][0]) and np.all(poly[:, 0] <= bbox2[1][0]) and np.all(poly[:, 1] >= bbox2[0][1]) and np.all(poly[:, 1] <= bbox2[1][1]):
                    continue
                obstacles.append(poly.tolist())

obstacles += gdswriter.route_ports_combined(filename, "TopCell", left_wire_ports+center, left_wire_orientations,
                               top_wire_ports_pad+center_pad, top_wire_orientations_pad, trace_width, layer_number, bbox1, bbox2,
                               show_animation=show_animation, obstacles=obstacles)
obstacles += gdswriter.route_ports_combined(filename, "TopCell", right_wire_ports+center, right_wire_orientations,
                                            right_wire_ports_pad+center_pad, right_wire_orientations_pad, trace_width, layer_number, bbox1, bbox2,
                                            show_animation=show_animation, obstacles=obstacles)
obstacles += gdswriter.route_ports_combined(filename, "TopCell", bot_wire_ports+center, bot_wire_orientations,
                                            bot_wire_ports_pad+center_pad, bot_wire_orientations_pad, trace_width, layer_number, bbox1, bbox2,
                                            show_animation=show_animation, obstacles=obstacles)


import pdb; pdb.set_trace()
