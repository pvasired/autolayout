import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np

array_size = 16
pitch = 30
escape_extent = 50
trace_width = 1.9
layer_number = 1
pad_diameter = 5
effective_pitch = pitch - pad_diameter
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
design.add_cell_array("TopCell", circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=center)

trace_cell_name = "Trace"
design.add_cell(trace_cell_name)

for layer_name in design.layers:
    if design.layers[layer_name]['number'] == layer_number:
        break

# Route outermost layer

# Create the 2D grid using NumPy
x = np.linspace(-pitch*(array_size-1)/2, pitch*(array_size-1)/2, array_size)
y = np.linspace(-pitch*(array_size-1)/2, pitch*(array_size-1)/2, array_size)
xx, yy = np.meshgrid(x, y, indexing='ij')

# Stack the coordinates into a single 3D array
grid = np.stack((xx, yy), axis=-1)

# Create the path points for the outermost layer
for i in range(array_size-1):
    path_points = [(grid[i, 0, 0], grid[i, 0, 1]), (grid[i, 0, 0], grid[i, 0, 1] - escape_extent)]
    design.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)

for i in range(array_size-1):
    path_points = [(grid[-1, i, 0], grid[-1, i, 1]), (grid[-1, i, 0] + escape_extent, grid[-1, i, 1])]
    design.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)

for i in range(array_size-1):
    path_points = [(grid[-1-i, -1, 0], grid[-1, -1, 1]), (grid[-1-i, -1, 0], grid[-1, -1, 1] + escape_extent)]
    design.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)

for i in range(array_size-1):
    path_points = [(grid[0, -1-i, 0], grid[0, -1-i, 1]), (grid[0, -1-i, 0] - escape_extent, grid[0, -1-i, 1])]
    design.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)

if (array_size-1) % 2 != 0:
    for i in range(1, int((array_size-2)/2)):
        num_traces = np.arange(1, i+1)
        assert (2*len(num_traces)+1)*trace_width <= effective_pitch, "Not enough space for traces."
        available_length = effective_pitch - 3 * trace_width
        if len(num_traces) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[i][1], 45, effective_pitch/2 + pad_diameter/2, grid[i][1][1]-grid[i][0][1]+escape_extent, post_rotation=90, post_reflection=True)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        else:
            spacing = available_length / (len(num_traces) - 1)
            cnt = 0
            for j in num_traces:
                hinged_path = gdswriter.create_hinged_path(grid[i][j], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][1]-grid[i][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

    for i in range(int((array_size-2)/2)+1, array_size-2):
        num_traces = np.arange(1, array_size-1-i)
        assert (2*len(num_traces)+1)*trace_width <= effective_pitch, "Not enough space for traces."
        available_length = effective_pitch - 3 * trace_width
        if len(num_traces) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[i][1], 45, effective_pitch/2 + pad_diameter/2, grid[i][1][1]-grid[i][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        else:
            spacing = available_length / (len(num_traces) - 1)
            cnt = 0
            for j in num_traces:
                hinged_path = gdswriter.create_hinged_path(grid[i][j], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][1]-grid[i][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

    iter_inds_L = np.flip(-np.arange(-int((array_size-2)/2), 0, 2))
    iter_inds_R = np.setdiff1d(np.arange(1, int((array_size-2)/2)), iter_inds_L)
    assert (2*len(iter_inds_L)+1)*trace_width <= effective_pitch, "Not enough space for traces."
    assert (2*len(iter_inds_R)+1)*trace_width <= effective_pitch, "Not enough space for traces."

    if len(iter_inds_L) == 1:
        hinged_path = gdswriter.create_hinged_path(grid[int((array_size-2)/2)][iter_inds_L[0]], 45, effective_pitch/2 + pad_diameter/2, 
                                                grid[int((array_size-2)/2)][iter_inds_L[0]][1]-grid[int((array_size-2)/2)][0][1]+escape_extent, post_rotation=90, post_reflection=True)
        design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
    else:
        available_length = effective_pitch - 3 * trace_width
        spacing = available_length / (len(iter_inds_L) - 1)
        cnt = 0
        for i in iter_inds_L:
            hinged_path = gdswriter.create_hinged_path(grid[int((array_size-2)/2)][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                    grid[int((array_size-2)/2)][i][1]-grid[int((array_size-2)/2)][0][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=True)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
            cnt += 1

    if len(iter_inds_R) == 1:
        hinged_path = gdswriter.create_hinged_path(grid[int((array_size-2)/2)][iter_inds_R[0]], 45, effective_pitch/2 + pad_diameter/2, 
                                                   grid[int((array_size-2)/2)][iter_inds_R[0]][1]-grid[int((array_size-2)/2)][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
        design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
    else:
        available_length = effective_pitch - 3 * trace_width
        spacing = available_length / (len(iter_inds_R) - 1)
        cnt = 0
        for i in iter_inds_R:
            hinged_path = gdswriter.create_hinged_path(grid[int((array_size-2)/2)][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                    grid[int((array_size-2)/2)][i][1]-grid[int((array_size-2)/2)][0][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=False)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
            cnt += 1

else:
    for i in range(1, int((array_size-2)/2)):
        num_traces = np.arange(1, i+1)
        assert (2*len(num_traces)+1)*trace_width <= effective_pitch, "Not enough space for traces."
        available_length = effective_pitch - 3 * trace_width
        if len(num_traces) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[i][1], 45, effective_pitch/2 + pad_diameter/2, grid[i][1][1]-grid[i][0][1]+escape_extent, post_rotation=90, post_reflection=True)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        else:
            spacing = available_length / (len(num_traces) - 1)
            cnt = 0
            for j in num_traces:
                hinged_path = gdswriter.create_hinged_path(grid[i][j], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][1]-grid[i][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

    for i in range(int((array_size-2)/2)+2, array_size-2):
        num_traces = np.arange(1, array_size-1-i)
        assert (2*len(num_traces)+1)*trace_width <= effective_pitch, "Not enough space for traces."
        available_length = effective_pitch - 3 * trace_width
        if len(num_traces) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[i][1], 45, effective_pitch/2 + pad_diameter/2, grid[i][1][1]-grid[i][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        else:
            spacing = available_length / (len(num_traces) - 1)
            cnt = 0
            for j in num_traces:
                hinged_path = gdswriter.create_hinged_path(grid[i][j], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][1]-grid[i][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

    if array_size > 3:
        special_column = int((array_size-2)/2)
        iter_inds_L = np.flip(-np.arange(-special_column+1, 0, 2))
        iter_inds_L = np.append(iter_inds_L, special_column)
        assert (2*len(iter_inds_L)+1)*trace_width <= effective_pitch, "Not enough space for traces."

        if len(iter_inds_L) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[special_column][iter_inds_L[0]], 45, effective_pitch/2 + pad_diameter/2, 
                                                    grid[special_column][iter_inds_L[0]][1]-grid[special_column][0][1]+escape_extent, post_rotation=90, post_reflection=True)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        
        else:
            available_length = effective_pitch - 3 * trace_width
            spacing = available_length / (len(iter_inds_L) - 1)
            cnt = 0
            for i in iter_inds_L:
                hinged_path = gdswriter.create_hinged_path(grid[special_column][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                        grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                        post_rotation=90, post_reflection=True)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

        iter_inds_R = np.flip(-np.arange(-special_column, 0, 2))
        assert (2*len(iter_inds_R)+1)*trace_width <= effective_pitch, "Not enough space for traces."

        if len(iter_inds_R) == 1:
            hinged_path = gdswriter.create_hinged_path(grid[special_column+1][iter_inds_R[0]], 45, effective_pitch/2 + pad_diameter/2, 
                                                    grid[special_column+1][iter_inds_R[0]][1]-grid[special_column+1][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
        
        else:
            available_length = effective_pitch - 3 * trace_width
            spacing = available_length / (len(iter_inds_R) - 1)
            cnt = 0
            for i in iter_inds_R:
                hinged_path = gdswriter.create_hinged_path(grid[special_column+1][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                        grid[special_column+1][i][1]-grid[special_column+1][0][1]+escape_extent, 
                                                        post_rotation=-90, post_reflection=False)
                design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                cnt += 1

        remaining_inds_L = np.setdiff1d(np.arange(1, special_column), iter_inds_L)
        remaining_inds_R = np.setdiff1d(np.arange(1, special_column), iter_inds_R)
        num_traces_center = len(remaining_inds_L) + len(remaining_inds_R)
        assert (2*num_traces_center+1)*trace_width <= effective_pitch, "Not enough space for traces."

        available_length = effective_pitch - 3 * trace_width
        spacing = available_length / (num_traces_center - 1)
        cnt = 0
        for i in remaining_inds_L:
            hinged_path = gdswriter.create_hinged_path(grid[special_column][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                       grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
            cnt += 1

        cnt = 0
        for i in remaining_inds_R:
            hinged_path = gdswriter.create_hinged_path(grid[special_column+1][i], 45, cnt*spacing + 3*trace_width/2 + pad_diameter/2, 
                                                       grid[special_column+1][i][1]-grid[special_column+1][0][1]+escape_extent, post_rotation=90, post_reflection=True)
            design.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
            cnt += 1
        
        center_electrode_path = []
        center_electrode_path.append(center)
        center_electrode_path.append((center[0]+pitch/2, center[1]-pitch))
        center_electrode_path.append((center[0]+pitch*(array_size-1)/2-pitch/2, center[1]-pitch*(array_size-1)/2))
        center_electrode_path.append((center[0]+pitch*(array_size-1)/2-pitch/2, center[1]-pitch*(array_size-1)/2-escape_extent))
        design.add_path_as_polygon("TopCell", center_electrode_path, trace_width, layer_name)

design.add_cell_reference("TopCell", trace_cell_name, origin=center)
design.add_cell_reference("TopCell", trace_cell_name, origin=center, rotation=90)
design.add_cell_reference("TopCell", trace_cell_name, origin=center, rotation=180)
design.add_cell_reference("TopCell", trace_cell_name, origin=center, rotation=270)

# Write to a GDS file
design.write_gds("autorouting_test-output.gds")