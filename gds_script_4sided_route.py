import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np
import gdsfactory as gf
import gdsfactory.routing as routing
from phidl import Device, Path
import phidl.routing as pr
import phidl.geometry as pg

array_size_x = 20
array_size_y = 19
pitch_x = 100
pitch_y = 100
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

pad_array_cell_name = "Pad Array"
pad_spacing = 200
pad_y = 10000
pad_x = center[0] - 10
center_pad = (pad_x, pad_y)
design.add_cell(pad_array_cell_name)
design.add_cell_array(pad_array_cell_name, circle_cell_name1, copies_x=array_size_x, copies_y=array_size_y, spacing_x=pad_spacing, spacing_y=pad_spacing, origin=(0, 0))
pad_grid, pad_ports, pad_orientations = design.add_regular_array_escape_four_sided("TopCell", center_pad, layer_name, pad_spacing, pad_spacing, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle)

grid, ports, orientations = design.add_regular_array_escape_four_sided("TopCell", center, layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle)
design.add_cell_reference("TopCell", array_cell_name, origin=center)
design.add_cell_reference("TopCell", pad_array_cell_name, origin=center_pad)

top_inds_elec = np.where(orientations == 90)[0]
top_inds_elec = top_inds_elec[np.argsort(ports[top_inds_elec][:, 0])]
left_inds_elec = np.where(orientations == 180)[0]
left_inds_elec = left_inds_elec[np.flip(np.argsort(ports[left_inds_elec][:, 1]))]
right_inds_elec = np.where(orientations == 0)[0]
right_inds_elec = right_inds_elec[np.flip(np.argsort(ports[right_inds_elec][:, 1]))]
bottom_inds_elec = np.where(orientations == 270)[0]
bottom_inds_elec = bottom_inds_elec[np.argsort(ports[bottom_inds_elec][:, 0])]

bottom_inds_pad = np.where(pad_orientations == 270)[0]
bottom_inds_pad = bottom_inds_pad[np.argsort(pad_ports[bottom_inds_pad][:, 0])]
left_inds_pad = np.where(pad_orientations == 180)[0]
left_inds_pad = left_inds_pad[np.argsort(pad_ports[left_inds_pad][:, 1])]
right_inds_pad = np.where(pad_orientations == 0)[0]
right_inds_pad = right_inds_pad[np.argsort(pad_ports[right_inds_pad][:, 1])]
top_inds_pad = np.where(pad_orientations == 90)[0]
top_inds_pad = top_inds_pad[np.argsort(pad_ports[top_inds_pad][:, 0])]

assert len(top_inds_elec) == len(bottom_inds_pad)
assert len(left_inds_elec) == len(left_inds_pad)
assert len(right_inds_elec) == len(right_inds_pad)
assert len(bottom_inds_elec) == len(top_inds_pad)

# Write to a GDS file
design.write_gds(filename)

D = pg.import_gds(filename)

top_inds_elec_left = top_inds_elec[np.where(ports[top_inds_elec][:, 0] - pad_ports[bottom_inds_pad][:, 0] >= 0)[0]]
top_inds_elec_left = top_inds_elec_left[np.argsort(ports[top_inds_elec_left][:, 0])]
top_inds_elec_right = np.setdiff1d(top_inds_elec, top_inds_elec_left)
top_inds_elec_right = top_inds_elec_right[np.flip(np.argsort(ports[top_inds_elec_right][:, 0]))]
bottom_inds_pad_right = np.flip(bottom_inds_pad)[:len(top_inds_elec_right)]

cnt = 0
additional_y = 0
for i, idx in enumerate(top_inds_elec_left):
    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports[idx][0], ports[idx][1]+additional_y), width=trace_width, orientation=orientations[idx])
    port2 = D.add_port(name=f"Pad {cnt}", midpoint=pad_ports[bottom_inds_pad[i]], width=trace_width, orientation=pad_orientations[bottom_inds_pad[i]])

    P = Path([ports[idx], port1.midpoint])
    path = P.extrude(trace_width, layer=layer_number)
    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
    if additional_y > 0:
        D.add_ref(path)
    additional_y += 2*trace_width
    cnt += 1

additional_y = 0
for i, idx in enumerate(top_inds_elec_right):
    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports[idx][0], ports[idx][1]+additional_y), width=trace_width, orientation=orientations[idx])
    port2 = D.add_port(name=f"Pad {cnt}", midpoint=pad_ports[bottom_inds_pad_right[i]], width=trace_width, orientation=pad_orientations[bottom_inds_pad_right[i]])

    P = Path([ports[idx], port1.midpoint])
    path = P.extrude(trace_width, layer=layer_number)
    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
    if additional_y > 0:
        D.add_ref(path)
    additional_y += 2*trace_width
    cnt += 1

additional_x = max(0, ports[left_inds_elec][:, 0].min() - pad_ports[left_inds_pad][:, 0].min())
xmin = np.inf
for i, idx in enumerate(left_inds_elec):
    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports[idx][0]-additional_x, ports[idx][1]), width=trace_width, orientation=orientations[idx])
    port2 = D.add_port(name=f"Pad {cnt}", midpoint=pad_ports[left_inds_pad[i]], width=trace_width, orientation=pad_orientations[left_inds_pad[i]])

    P = Path([ports[idx], port1.midpoint])
    path = P.extrude(trace_width, layer=layer_number)
    route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
    if route_path.xmin < xmin:
        xmin = route_path.xmin
    D.add_ref(route_path)
    D.add_ref(path)
    additional_x += 2*trace_width
    cnt += 1

additional_x = max(0, pad_ports[right_inds_pad][:, 0].max() - ports[right_inds_elec][:, 0].max())
for i, idx in enumerate(right_inds_elec):
    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports[idx][0]+additional_x, ports[idx][1]), width=trace_width, orientation=orientations[idx])
    port2 = D.add_port(name=f"Pad {cnt}", midpoint=pad_ports[right_inds_pad[i]], width=trace_width, orientation=pad_orientations[right_inds_pad[i]])

    P = Path([ports[idx], port1.midpoint])
    path = P.extrude(trace_width, layer=layer_number)
    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
    D.add_ref(path)
    additional_x += 2*trace_width
    cnt += 1

for i, idx in enumerate(bottom_inds_elec):
    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports[idx][0], ports[idx][1]), width=trace_width, orientation=orientations[idx])
    port2 = D.add_port(name=f"Pad {cnt}", midpoint=pad_ports[top_inds_pad[i]], width=trace_width, orientation=pad_orientations[top_inds_pad[i]])

    D.add_ref(pr.route_smooth(port1, port2, path_type='C', length1=10+2*i*trace_width, length2=10+2*i*trace_width, left1=xmin-ports[idx][0]-3*trace_width/2-2*i*trace_width, width=trace_width, layer=layer_number, radius=trace_width))
    cnt += 1

D.write_gds(filename, cellname="TopCell")