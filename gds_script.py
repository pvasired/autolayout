import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
import gdswriter

# Initialize the design with the GDSDesign class
design = gdswriter.GDSDesign()

# Define layers
design.define_layer('Metal1', 1)
design.define_layer('Oxide2', 2)

# Create a cell for a circle with a diameter of 10um
circle_10um_cell_name = 'Circle10umCell'
design.add_cell(circle_10um_cell_name)
# Add the circle to the cell; since the diameter is 10um, radius is 5um
design.add_circle(circle_10um_cell_name, (0, 0), 10, 'Metal1')

# Create a cell for a circle with a diameter of 8um
circle_8um_cell_name = 'Circle8umCell'
design.add_cell(circle_8um_cell_name)
# Add the circle to the cell; since the diameter is 8um, radius is 4um
design.add_circle(circle_8um_cell_name, (0, 0), 20, 'Oxide2')

# Array parameters
n, m = 16, 16  # Number of copies in x and y directions
pitch = 30  # Spacing between the centers of adjacent circles

# Create a 16x16 array of the 10um diameter circles on Metal1 layer
design.add_cell_array('TopCell', circle_10um_cell_name, n, m, pitch, pitch, origin=(0, 0))

# Create a 16x16 array of the 8um diameter circles on Oxide2 layer
design.add_cell_array('TopCell', circle_8um_cell_name, n, m, pitch, pitch, origin=(0, 0))

# Write the design to a GDS file
design.write_gds('two_circle_arrays.gds')
