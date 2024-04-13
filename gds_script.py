import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter
import numpy as np
from shapely.geometry import Polygon
import a_star
import matplotlib.pyplot as plt
import math

def get_grid_aligned_boundary_points(polygon, grid_size, step=0.5):
    length = polygon.length
    points = []

    # Create points along the boundary at intervals of 'step'
    for dist in np.arange(0, length, step):
        point = polygon.boundary.interpolate(dist)
        # Round the coordinates to the nearest grid point
        rounded_point = (
            round(point.x / grid_size) * grid_size,
            round(point.y / grid_size) * grid_size
        )
        points.append(rounded_point)
    
    # Ensure the last point is included
    point = polygon.boundary.interpolate(length)
    rounded_point = (
        round(point.x / grid_size) * grid_size,
        round(point.y / grid_size) * grid_size
    )
    points.append(rounded_point)

    return points

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
array_size = 2  # Size of the arrays (16x16)
pitch = 30  # Pitch in um

# Create a cell with a single larger circle for 'Metal' layer
circle_cell_name1 = "Circle10um"
design.add_cell(circle_cell_name1)
design.add_circle_as_polygon(circle_cell_name1, center=(0, 0), radius=circle_radius1, layer_name="Metal", num_points=100)

# Create an array of the larger circle cell on 'Metal' layer
design.add_cell_array("TopCell", circle_cell_name1, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0),
                      netIDs=np.array([[1, 2], [3, 4]]))

# Create a cell with a single smaller circle for 'Via' layer
circle_cell_name2 = "Circle8um"
design.add_cell(circle_cell_name2)
design.add_circle_as_polygon(circle_cell_name2, center=(0, 0), radius=circle_radius2, layer_name="Oxide", num_points=100)

# Create an array of the smaller circle cell on 'Via' layer
design.add_cell_array("TopCell", circle_cell_name2, copies_x=array_size, copies_y=array_size, spacing_x=pitch, spacing_y=pitch, origin=(0, 0),
                      netIDs=np.array([[1, 2], [3, 4]]))

pad_cell_name = "Pad"
design.add_cell(pad_cell_name)
design.add_rectangle(pad_cell_name, layer_name="Metal", center=(0, 0), width=120, height=1200)
design.add_rectangle(pad_cell_name, layer_name="Oxide", center=(0, 0), width=100, height=1180)

design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=2, spacing_x=200, spacing_y=0, origin=(0, 1000),
                      netIDs=np.array([[1, 2]]).T)
design.add_cell_array("TopCell", pad_cell_name, copies_y=1, copies_x=2, spacing_x=200, spacing_y=0, origin=(0, -1000),
                      netIDs=np.array([[3, 4]]).T)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(-350, -350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(-350, 350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(350, -350), width=10, extent_x=100, extent_y=100)
design.add_alignment_cross("TopCell", layer_name="Metal", center=(350, 350), width=10, extent_x=100, extent_y=100)
#design.add_text("TopCell", text="A", layer_name="Metal", position=(0, 500), height=100)

# Run design rule checks
design.run_drc_checks()

# Write to a GDS file
design.write_gds("example_design.gds")

top_cell_polygons = np.array(design.cells['TopCell']['polygons'], dtype=object)
top_cell_netIDs = np.array(design.cells['TopCell']['netIDs'])

routing_layer = 1
trace_width = 2.0
grid_size = 1.0
show_animation = True

routing_inds = np.where((top_cell_netIDs[:, 1] != 0) & (top_cell_netIDs[:, 0] == routing_layer))[0]
uniqueIDs, inverse, counts = np.unique(top_cell_netIDs[routing_inds], axis=0, return_inverse=True, return_counts=True)
routing_filter = np.where(counts > 1)[0]

routing_groups = {}
for i in range(len(routing_filter)):
    routing_groups[i] = routing_inds[np.where(inverse == routing_filter[i])[0]]
    shapely_polygons = [Polygon(polygon) for polygon in top_cell_polygons[routing_groups[i]]]
    merged_polygons = gdswriter.cluster_intersecting_polygons(shapely_polygons)
    path_reqs = [(polygon.centroid.x, polygon.centroid.y) for polygon in merged_polygons]

    obstacles = np.setdiff1d(np.where(top_cell_netIDs[:, 0] == routing_layer)[0], routing_groups[i])
    shapely_obstacles = [Polygon(polygon) for polygon in top_cell_polygons[obstacles]]
    merged_obstacles = gdswriter.cluster_intersecting_polygons(shapely_obstacles)

    sx = path_reqs[0][0]
    sy = path_reqs[0][1]
    gx = path_reqs[1][0]
    gy = path_reqs[1][1]

    ox = []
    oy = []
    for obstacle in merged_obstacles:
        boundary_points = get_grid_aligned_boundary_points(obstacle, grid_size)
        ox.extend([point[0] for point in boundary_points])
        oy.extend([point[1] for point in boundary_points])

    if show_animation:  # pragma: no cover
        plt.plot(ox, oy, ".k")
        plt.plot(sx, sy, "og")
        plt.plot(gx, gy, "xb")
        plt.grid(True)
        plt.axis("equal")

    a_star = a_star.AStarPlanner(ox, oy, grid_size, trace_width)
    rx, ry = a_star.planning(sx, sy, gx, gy)

    if show_animation:  # pragma: no cover
        plt.plot(rx, ry, "-r")
        plt.pause(0.001)
        plt.show()

    import pdb; pdb.set_trace()

import pdb; pdb.set_trace()
