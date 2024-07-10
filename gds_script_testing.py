import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np

array_size = 16
pitch_x = 60
pitch_y = 30
escape_extent = 50
trace_width = 1.9
layer_number = 1
pad_diameter = 5
routing_angle = 45
center = (500, -500)

# Initialize the GDS design
design = gdswriter.GDSDesign()

# Define layers
design.define_layer("Metal", layer_number)

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=pad_diameter/2, layer_name="Metal", num_points=100)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array("TopCell", circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch_x, spacing_y=pitch_y, origin=center)

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

design.add_regular_array_escape("Trace1", layer_name, pitch_x, pitch_y, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=True)
design.add_regular_array_escape("Trace2", layer_name, pitch_y, pitch_x, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=False)
design.add_regular_array_escape("Trace3", layer_name, pitch_x, pitch_y, array_size, trace_width, pad_diameter, escape_extent=escape_extent, routing_angle=routing_angle, odd_extra_trace=False)

design.add_cell_reference("TopCell", "Trace1", origin=center)
design.add_cell_reference("TopCell", "Trace2", origin=center, rotation=90)
design.add_cell_reference("TopCell", "Trace3", origin=center, rotation=180)
design.add_cell_reference("TopCell", "Trace2", origin=center, rotation=270)

# Write to a GDS file
design.write_gds("autorouting_test-output.gds")