import gdspy
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

class GDSDesign:
    def __init__(self, lib_name='default_lib', filename=None, top_cell_names=['TopCell'], bounds=[-np.inf, np.inf, -np.inf, np.inf], unit=1e-6, precision=1e-9,
                 default_netID=0, default_feature_size=5, default_spacing=5):
        """
        Initialize a new GDS design library with an optional top cell, design size, and units.
        
        Args:
        - lib_name (str): Name of the GDS library.
        - top_cell_name (str): Name of the top-level cell.
        - size (tuple): Overall size of the design (width, height).
        - unit (str): Units of measurement (e.g., 'um' for micrometers, 'nm' for nanometers).
        """
        if filename is None:
            self.lib = gdspy.GdsLibrary(name=lib_name, unit=unit, precision=precision)
            self.cells = {}  # Cells by name
            self.top_cell_names = top_cell_names
            for top_cell_name in top_cell_names:
                self.add_cell(top_cell_name)
            self.layers = {}  # Layer properties by layer name
            self.drc_rules = {}  # DRC rules for each layer
            self.bounds = bounds  # Design size
            self.unit = unit  # Measurement units
            self.precision = precision
        else:
            self.lib = gdspy.GdsLibrary(infile=filename)
            self.cells = {}  # Cells by name
            unique_layers = set()
            for cell_name in self.lib.cells.keys():
                if cell_name != '$$$CONTEXT_INFO$$$':
                    self.cells[cell_name] = {}
                    self.cells[cell_name]['cell'] = self.lib.cells[cell_name]
                    self.cells[cell_name]['polygons'] = []
                    self.cells[cell_name]['netIDs'] = []
                    polygons_by_spec = self.lib.cells[cell_name].get_polygons(by_spec=True)
                    for (lay, dat), polys in polygons_by_spec.items():
                        unique_layers.add(lay)
                        for poly in polys:
                            self.cells[cell_name]['polygons'].append(poly)
                            self.cells[cell_name]['netIDs'].append((lay, default_netID))

            top_cells = self.lib.top_level()
            self.top_cell_names = [cell.name for cell in top_cells if cell.name != '$$$CONTEXT_INFO$$$']
            self.layers = {}  # Layer properties by layer name
            self.drc_rules = {}  # DRC rules for each layer
            for layer in unique_layers:
                self.define_layer(f"Layer{layer}", layer, min_feature_size=default_feature_size, 
                                  min_spacing=default_spacing)   # TODO update with real values

            max_x, min_x, max_y, min_y = -np.inf, np.inf, -np.inf, np.inf
            for cell in top_cells:
                for poly in cell.get_polygons():
                    max_x = max(max_x, np.amax(poly[:, 0]))
                    min_x = min(min_x, np.amin(poly[:, 0]))
                    max_y = max(max_y, np.amax(poly[:, 1]))
                    min_y = min(min_y, np.amin(poly[:, 1]))
            
            self.bounds = [min_x, max_x, min_y, max_y]
            self.unit = self.lib.unit
            self.precision = self.lib.precision

    def add_cell(self, cell_name):
        if cell_name in self.cells:
            print(f"Warning: Cell '{cell_name}' already exists. Returning existing cell.")
            return self.cells[cell_name]['cell']
        cell = self.lib.new_cell(cell_name)
        self.cells[cell_name] = {}
        self.cells[cell_name]['cell'] = cell
        self.cells[cell_name]['polygons'] = []
        self.cells[cell_name]['netIDs'] = []
        return cell

    def add_component(self, cell, cell_name, component, netID, layer_number=None):
        # Check if component is a polygon or a CellReference
        if isinstance(component, gdspy.Polygon) or isinstance(component, gdspy.Rectangle) or isinstance(component, gdspy.Text):
            assert layer_number is not None, "Layer number must be specified for polygons."
            cell.add(component)
            self.cells[cell_name]['polygons'].append(component.polygons[0])
            self.cells[cell_name]['netIDs'].append((layer_number, netID))
        elif isinstance(component, gdspy.CellReference):
            cell.add(component)
            polygons_by_spec = component.get_polygons(by_spec=True)
            for (lay, dat), polys in polygons_by_spec.items():
                for poly in polys:
                    self.cells[cell_name]['polygons'].append(poly)
                    self.cells[cell_name]['netIDs'].append((lay, netID))
        else:
            raise ValueError(f"Error: Unsupported component type '{type(component)}'. Please use gdspy.Polygon or gdspy.CellReference.")

    def define_layer(self, layer_name, layer_number, description=None, min_feature_size=None, min_spacing=None):
        """
        Define a layer with a unique number, optional name, description, and DRC rules.
        This does not create a physical layer but registers the layer's properties and associated DRC rules.
        
        Args:
        - layer_name (str): Name of the layer.
        - layer_number (int): Unique number identifying the layer.
        - description (str, optional): Description of the layer.
        - min_feature_size (float, optional): Minimum feature size for the layer (in micrometers).
        - min_spacing (float, optional): Minimum spacing between features on the layer (in micrometers).
        """
        # Check for unique layer number
        for existing_layer_name, props in self.layers.items():
            if props['number'] == layer_number and layer_name != existing_layer_name:
                raise ValueError(f"Error: Layer number {layer_number} is already assigned to layer '{existing_layer_name}'. Layer numbers must be unique.")

        # Validate DRC parameters
        if min_feature_size is not None and min_feature_size <= 0:
            raise ValueError("Minimum feature size must be positive.")
        if min_spacing is not None and min_spacing <= 0:
            raise ValueError("Minimum spacing must be positive.")
        
        if layer_name in self.layers:
            print(f"Warning: Layer name '{layer_name}' already defined. Updating properties.")
        
        # Store layer properties
        self.layers[layer_name] = {'number': layer_number, 'description': description}

        # Store DRC rules for the layer
        self.drc_rules[layer_name] = {'min_feature_size': min_feature_size, 'min_spacing': min_spacing}

    def get_layer_number(self, layer_name):
        if layer_name not in self.layers:
            raise ValueError(f"Error: Layer name '{layer_name}' not defined. Please define layer first.")
        return self.layers[layer_name]['number']

    def check_cell_exists(self, cell_name):
        if cell_name not in self.cells:
            raise ValueError(f"Error: Cell '{cell_name}' does not exist. Please add it first.")
        return self.cells[cell_name]['cell']

    def add_rectangle(self, cell_name, layer_name, center=None, width=None, height=None, lower_left=None, upper_right=None, datatype=0,
                      netID=0):
        """
        Add a rectangle to a cell. The rectangle can be defined either by center point and width/height
        or by specifying lower left and upper right corners.

        Args:
        - cell_name (str): Name of the cell to which the rectangle will be added.
        - args: Variable arguments, can be either (center, width, height) or (lower_left, upper_right).
        - layer_name (str): Name of the layer.
        - datatype (int): Datatype for the layer (default: 0).
        """
        cell = self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)
        
        if center is not None and width is not None and height is not None:
            # Assume center, width, height format
            lower_left = (center[0] - width / 2, center[1] - height / 2)
            upper_right = (center[0] + width / 2, center[1] + height / 2)
        elif lower_left is None or upper_right is None:
            raise ValueError("Error: Invalid arguments. Please specify center, width, height or lower_left, upper_right.")

        # Create and add the rectangle
        rectangle = gdspy.Rectangle(lower_left, upper_right, layer=layer_number, datatype=datatype)
        self.add_component(cell, cell_name, rectangle, netID, layer_number)
    
    def add_alignment_cross(self, cell_name, layer_name, center, width, extent_x, extent_y, datatype=0, netID=0):
        """
        Add an alignment cross to the specified cell and layer.

        Args:
        - cell_name (str): The name of the cell to add the cross to.
        - layer_name (str): The name of the layer to add the cross to.
        - center (tuple): (x, y) coordinates for the center of the cross.
        - width (float): The width of the arms of the cross.
        - extent_x (float): The total length of the cross arm along the x-axis.
        - extent_y (float): The total length of the cross arm along the y-axis.
        - datatype (int): The datatype for the layer (default: 0).
        """
        cell = self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)

        # Calculate the coordinates for the horizontal and vertical parts of the cross
        horizontal_lower_left = (center[0] - extent_x / 2, center[1] - width / 2)
        horizontal_upper_right = (center[0] + extent_x / 2, center[1] + width / 2)
        vertical_lower_left = (center[0] - width / 2, center[1] - extent_y / 2)
        vertical_upper_right = (center[0] + width / 2, center[1] + extent_y / 2)

        # Create rectangles for the cross
        horizontal_rect = gdspy.Rectangle(horizontal_lower_left, horizontal_upper_right, layer=layer_number, datatype=datatype)
        vertical_rect = gdspy.Rectangle(vertical_lower_left, vertical_upper_right, layer=layer_number, datatype=datatype)

        # Add the rectangles to the cell
        self.add_component(cell, cell_name, horizontal_rect, netID, layer_number)
        self.add_component(cell, cell_name, vertical_rect, netID, layer_number)

    def add_text(self, cell_name, text, layer_name, position, height, angle=0, horizontal=True, datatype=0, netID=0):
        layer_number = self.get_layer_number(layer_name)
        cell = self.check_cell_exists(cell_name)
        text = gdspy.Text(text, height, position, horizontal=horizontal, angle=angle, layer=layer_number, datatype=datatype)
        self.add_component(cell, cell_name, text, netID, layer_number)

    def add_polygon(self, cell_name, points, layer_name, datatype=0, netID=0):
        layer_number = self.get_layer_number(layer_name)
        cell = self.check_cell_exists(cell_name)
        polygon = gdspy.Polygon(points, layer=layer_number, datatype=datatype)
        self.add_component(cell, cell_name, polygon, netID, layer_number)

    def add_path_as_polygon(self, cell_name, points, width, layer_name, datatype=0, netID=0):
        """
        Convert a path defined by a series of points and a width into a polygon and add it to the specified cell and layer.

        Args:
        - cell_name (str): The name of the cell to which the path will be added.
        - points (list of tuples): The waypoints of the path: points along the center of the path.
        - width (float): The width of the path.
        - layer_name (str): The name of the layer.
        - datatype (int): The datatype for the polygon.
        """
        # Ensure the layer exists and retrieve its number
        layer_number = self.get_layer_number(layer_name)

        # Ensure the cell exists
        cell = self.check_cell_exists(cell_name)

        # Create the path as a polygon
        path = gdspy.FlexPath(points, width, layer=layer_number, datatype=datatype)
        path_polygons = path.to_polygonset()  # Corrected method call here

        # Add the generated polygons to the cell
        for poly in path_polygons.polygons:
            path_polygon = gdspy.Polygon(poly, layer=layer_number, datatype=datatype)
            self.add_component(cell, cell_name, path_polygon, netID, layer_number)

    def add_circle_as_polygon(self, cell_name, center, radius, layer_name, num_points=100, datatype=0, netID=0):
        """
        Create a circle and immediately approximate it as a polygon with a specified number of points.
        The approximated circle (polygon) is then added to the specified cell and layer.

        Args:
        - cell_name (str): The name of the cell to which the circle will be added.
        - center (tuple): The (x, y) coordinates of the circle's center.
        - radius (float): The radius of the circle.
        - layer_name (str): The name of the layer.
        - num_points (int): The number of points to use for the circle approximation.
        - datatype (int): The datatype for the polygon.
        """
        # Ensure the layer exists and retrieve its number
        layer_number = self.get_layer_number(layer_name)

        # Ensure the cell exists
        cell = self.check_cell_exists(cell_name)

        # Calculate the points that approximate the circle
        angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
        x_points = center[0] + np.cos(angles) * radius
        y_points = center[1] + np.sin(angles) * radius
        points = np.vstack((x_points, y_points)).T  # Transpose to get an array of (x, y) points

        # Create and add the polygon to the specified cell and layer
        polygon = gdspy.Polygon(points, layer=layer_number, datatype=datatype)
        self.add_component(cell, cell_name, polygon, netID, layer_number)

    def add_cell_reference(self, parent_cell_name, child_cell_name, origin=(0, 0), magnification=1, rotation=0,
                            x_reflection=False, netID=0):
        parent_cell = self.check_cell_exists(parent_cell_name)
        child_cell = self.check_cell_exists(child_cell_name)
        ref = gdspy.CellReference(child_cell, origin=origin, magnification=magnification, rotation=rotation, x_reflection=x_reflection)
        self.add_component(parent_cell, parent_cell_name, ref, netID)

    def add_cell_array(self, target_cell_name, cell_name_to_array, copies_x, copies_y, spacing_x, spacing_y, origin=(0, 0),
                       magnification=1, rotation=0, x_reflection=False, netIDs=None):
        target_cell = self.check_cell_exists(target_cell_name)
        cell_to_array = self.check_cell_exists(cell_name_to_array)
        
        # Calculate the start position to center the array around the specified origin
        total_length_x = spacing_x * (copies_x - 1)
        total_length_y = spacing_y * (copies_y - 1)
        start_x = origin[0] - (total_length_x / 2)
        start_y = origin[1] - (total_length_y / 2)

        cnt = 0
        for i in range(copies_x):
            for j in range(copies_y):
                x_position = start_x + (i * spacing_x)
                y_position = start_y + (j * spacing_y)
                # Add a cell reference (arrayed cell) at the calculated position to the target cell
                ref = gdspy.CellReference(cell_to_array, origin=(x_position, y_position), magnification=magnification, 
                                          rotation=rotation, x_reflection=x_reflection)
                self.add_component(target_cell, target_cell_name, ref, netIDs[i][j] if netIDs is not None else cnt)
                cnt += 1

    def check_minimum_feature_size(self, cell_name, layer_name, min_size):
        # Assume `layer_number` is already determined from `layer_name`
        layer_number = self.get_layer_number(layer_name)
        
        # Ensure the cell exists
        cell = self.check_cell_exists(cell_name)

        # Get polygons by specification (layer and datatype)
        polygons_by_spec = cell.get_polygons(by_spec=True)

        # Filter for the specific layer (and possibly datatype if relevant)
        for (lay, dat), polys in polygons_by_spec.items():
            if lay == layer_number:
                for poly in polys:
                    # Now `poly` is a numpy array of points for one polygon
                    # Calculate the bounding box of the polygon
                    bbox = gdspy.Polygon(poly).get_bounding_box()
                    width = bbox[1][0] - bbox[0][0]
                    height = bbox[1][1] - bbox[0][1]
                    if width < min_size or height < min_size:
                        raise ValueError(f"Feature on layer '{layer_name}' in cell '{cell_name}' is smaller than the minimum size {min_size}.")

    def check_minimum_spacing(self, cell_name, layer_name, min_spacing):
        """
        Check if the spacing between all shapes on a specified layer in a cell meets the minimum spacing requirement.

        Args:
        - cell_name (str): Name of the cell to check.
        - layer_name (str): Name of the layer to check.
        - min_spacing (float): Minimum spacing between shapes.
        """
        cell = self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)

        # Get polygons by specification (layer and datatype)
        polygons_by_spec = cell.get_polygons(by_spec=True)

        # Filter for the specific layer (and possibly datatype if relevant)
        layer_polygons = []
        for (lay, dat), polys in polygons_by_spec.items():
            if lay == layer_number:
                for poly in polys:
                    layer_polygons.append(poly)
        
        # Convert gdspy polygons to shapely polygons
        shapely_polygons = [Polygon(poly) for poly in layer_polygons]

        # Cluster intersecting polygons
        merged_polygons = cluster_intersecting_polygons(shapely_polygons)

        # Efficiently check for spacing violations between merged polygons
        if len(merged_polygons) < 2:
            return  # If there is less than two polygons, no minimum spacing issues can occur

        # Calculate minimum spacing between merged polygons
        for i in range(len(merged_polygons)):
            for j in range(i + 1, len(merged_polygons)):
                distance = merged_polygons[i].distance(merged_polygons[j])
                if distance < min_spacing:
                    raise ValueError(f"Minimum spacing of {min_spacing}um not met; found spacing is {distance}um.")
    
    def run_drc_checks(self):
        """
        Run DRC checks for all layers in the top cell based on defined DRC rules and ensure
        all features are within the bounds of the design size.
        """
        for layer_name, rules in self.drc_rules.items():
            # Extract the DRC rules for the layer
            min_feature_size, min_spacing = rules['min_feature_size'], rules['min_spacing']

            # Check minimum feature size
            if min_feature_size:
                print(f"Checking minimum feature size ({min_feature_size}um) on layer '{layer_name}'...")
                for cell_name in self.top_cell_names:
                    self.check_minimum_feature_size(cell_name, layer_name, min_feature_size)

            # Check minimum spacing
            if min_spacing:
                print(f"Checking minimum spacing ({min_spacing}um) on layer '{layer_name}'...")
                for cell_name in self.top_cell_names:
                    self.check_minimum_spacing(cell_name, layer_name, min_spacing)
        
        # Check if all features are within the design bounds
        print("Checking if all features are within the design bounds...")
        for cell_name in self.top_cell_names:
            self.check_features_within_bounds(cell_name)
        print("DRC checks passed.")
    
    def check_features_within_bounds(self, cell_name):
        """
        Ensure all polygons in the specified cell, assumed to be centered at the origin,
        are within the design bounds using NumPy for efficiency.
        
        Args:
        - cell_name (str): Name of the cell to check.
        """
        cell = self.check_cell_exists(cell_name)

        for poly in cell.get_polygons():
            points = np.array(poly)
            
            # Calculate the maximum extent of the polygon in both x and y directions from the origin
            min_x = np.amin(points[:, 0])
            max_x = np.amax(points[:, 0])
            min_y = np.amin(points[:, 1])
            max_y = np.amax(points[:, 1])
            
            if min_x < self.bounds[0] or max_x > self.bounds[1] or min_y < self.bounds[2] or max_y > self.bounds[3]:
                raise ValueError(f"Feature in cell '{cell_name}' exceeds the design bounds.")

    def write_gds(self, filename):
        self.lib.write_gds(filename)
        print(f'GDS file written to {filename}')

def cluster_intersecting_polygons(polygons):
    """Groups intersecting polygons into clusters using an R-tree for efficient spatial indexing,
    ensuring isolated polygons are also included as individual clusters.
    
    Returns:
        List of clusters, where each cluster is a union of polygons that intersect with each other,
        including isolated polygons as individual clusters.
    """
    tree = STRtree(polygons)
    visited = set()  # Set to track processed polygons by index to avoid duplicates
    clusters = []

    # Iterate over the polygons using their index to manage direct references
    for i, poly in enumerate(polygons):
        if i not in visited:
            intersecting_indices = tree.query(poly)
            cluster = []
            found_neighbors = False

            for idx in intersecting_indices:
                neighbor = polygons[idx]  # Directly reference the polygon using its index
                if (neighbor.intersects(poly) or neighbor.touches(poly)) and idx not in visited:
                    visited.add(idx)  # Mark this index as processed
                    cluster.append(neighbor)
                    found_neighbors = True

            # Add the current polygon to the cluster if it has neighbors
            if found_neighbors:
                if i not in visited:
                    visited.add(i)
                    cluster.append(poly)
                clusters.append(cluster)
            else:
                # If no neighbors were found, treat this polygon as an isolated cluster
                visited.add(i)
                clusters.append([poly])  # Include isolated polygon as its own cluster

    return [unary_union(cluster) for cluster in clusters] # Merge clusters into single polygons

def create_hinged_path(start_point, angle, level_y, final_x):
    x0, y0 = start_point
    angle_radians = angle * np.pi / 180
    
    # If the angle is directly horizontal or the start y is already at level_y, adjust behavior
    if angle > 90 or y0 == level_y:
        # Directly horizontal or already at level_y
        raise ValueError('Improper Usage')
    
    # Calculate x where the path should level off
    # y = y0 + (x - x0) * tan(angle) --> x = x0 + (level_y - y0) / tan(angle)
    # Avoid division by zero if angle is 90 or 270 degrees
    if angle == 90:
        hinge_x = x0  # Vertical line case
    else:
        hinge_x = x0 + (level_y - y0) / np.tan(angle_radians)
    
    hinge_point = (hinge_x, level_y)
    
    # Points from start to hinge
    path_points = [start_point, hinge_point]
    
    # Continue horizontally from hinge point
    path_points.append((final_x, level_y))  # Extend horizontally for some length
    
    return path_points
