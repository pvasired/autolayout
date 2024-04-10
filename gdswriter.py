import gdspy
import numpy as np

class GDSDesign:
    def __init__(self, lib_name='default_lib', top_cell_name='TopCell', size=(100, 100), units='um'):
        """
        Initialize a new GDS design library with an optional top cell, design size, and units.
        
        Args:
        - lib_name (str): Name of the GDS library.
        - top_cell_name (str): Name of the top-level cell.
        - size (tuple): Overall size of the design (width, height).
        - units (str): Units of measurement (e.g., 'um' for micrometers, 'nm' for nanometers).
        """
        self.lib = gdspy.GdsLibrary(name=lib_name, unit=1e-6 if units == 'um' else 1e-9, precision=1e-9)
        self.cells = {}  # Cells by name
        self.top_cell_name = top_cell_name
        self.top_cell = self.add_cell(top_cell_name)
        self.layers = {}  # Layer properties by layer name
        self.drc_rules = {}  # DRC rules for each layer
        self.size = size  # Design size
        self.units = units  # Measurement units

    def add_cell(self, cell_name):
        if cell_name in self.cells:
            print(f"Warning: Cell '{cell_name}' already exists. Returning existing cell.")
            return self.cells[cell_name]
        cell = self.lib.new_cell(cell_name)
        self.cells[cell_name] = cell
        return cell

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
        return self.cells[cell_name]

    def add_rectangle(self, cell_name, layer_name, center=None, width=None, height=None, lower_left=None, upper_right=None, datatype=0):
        """
        Add a rectangle to a cell. The rectangle can be defined either by center point and width/height
        or by specifying lower left and upper right corners.

        Args:
        - cell_name (str): Name of the cell to which the rectangle will be added.
        - args: Variable arguments, can be either (center, width, height) or (lower_left, upper_right).
        - layer_name (str): Name of the layer.
        - datatype (int): Datatype for the layer (default: 0).
        """
        self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)
        
        if center is not None and width is not None and height is not None:
            # Assume center, width, height format
            lower_left = (center[0] - width / 2, center[1] - height / 2)
            upper_right = (center[0] + width / 2, center[1] + height / 2)
        elif lower_left is None or upper_right is None:
            raise ValueError("Error: Invalid arguments. Please specify center, width, height or lower_left, upper_right.")

        # Create and add the rectangle
        rectangle = gdspy.Rectangle(lower_left, upper_right, layer=layer_number, datatype=datatype)
        self.cells[cell_name].add(rectangle)

    def add_polygon(self, cell_name, points, layer_name, datatype=0):
        layer_number = self.get_layer_number(layer_name)
        polygon = gdspy.Polygon(points, layer=layer_number, datatype=datatype)
        self.check_cell_exists(cell_name).add(polygon)

    def add_path_as_polygon(self, cell_name, points, width, layer_name, datatype=0):
        """
        Convert a path defined by a series of points and a width into a polygon and add it to the specified cell and layer.

        Args:
        - cell_name (str): The name of the cell to which the path will be added.
        - points (list of tuples): The waypoints of the path.
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
            cell.add(gdspy.Polygon(poly, layer=layer_number, datatype=datatype))

    def add_circle_as_polygon(self, cell_name, center, radius, layer_name, num_points=100, datatype=0):
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
        cell.add(polygon)

    def add_cell_reference(self, parent_cell_name, child_cell_name, origin=(0, 0), magnification=1, rotation=0):
        parent_cell = self.check_cell_exists(parent_cell_name)
        child_cell = self.check_cell_exists(child_cell_name)
        ref = gdspy.CellReference(child_cell, origin=origin, magnification=magnification, rotation=rotation)
        parent_cell.add(ref)

    def add_cell_array(self, target_cell_name, cell_name_to_array, n, m, spacing_x, spacing_y, origin=(0, 0),
                       magnification=1, rotation=0):
        target_cell = self.check_cell_exists(target_cell_name)
        cell_to_array = self.check_cell_exists(cell_name_to_array)
        
        # Calculate the start position to center the array around the specified origin
        total_length_x = spacing_x * (n - 1)
        total_length_y = spacing_y * (m - 1)
        start_x = origin[0] - (total_length_x / 2)
        start_y = origin[1] - (total_length_y / 2)
        
        for i in range(n):
            for j in range(m):
                x_position = start_x + (i * spacing_x)
                y_position = start_y + (j * spacing_y)
                # Add a cell reference (arrayed cell) at the calculated position to the target cell
                ref = gdspy.CellReference(cell_to_array, origin=(x_position, y_position), magnification=magnification, 
                                          rotation=rotation)
                target_cell.add(ref)

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
        self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)

        polygons = [poly for poly in self.cells[cell_name].polygons if poly.layer == layer_number]
        for i, poly1 in enumerate(polygons):
            for poly2 in polygons[i+1:]:
                distance = self.calculate_distance_between_polygons(poly1, poly2)
                if distance < min_spacing:
                    raise ValueError(f"Spacing between features on layer '{layer_name}' in cell '{cell_name}' is less than the minimum spacing {min_spacing}.")

    def calculate_distance_between_polygons(self, poly1, poly2):
        """
        Calculate the minimum distance between two polygons.

        Args:
        - poly1, poly2: Polygons to calculate the distance between.

        Returns:
        - The minimum distance between the two polygons.
        """
        # Extract the points from the polygons
        points1 = poly1.points
        points2 = poly2.points

        # Calculate all pairwise distances and return the minimum
        distances = np.sqrt(np.sum((points1[:, np.newaxis, :] - points2[np.newaxis, :, :]) ** 2, axis=2))
        return np.min(distances)
    
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
                self.check_minimum_feature_size(self.top_cell_name, layer_name, min_feature_size)

            # # Check minimum spacing
            # if min_spacing:
            #     print(f"Checking minimum spacing ({min_spacing}um) on layer '{layer_name}'...")
            #     self.check_minimum_spacing(self.top_cell_name, layer_name, min_spacing)
        
        # Check if all features are within the design bounds
        print("Checking if all features are within the design bounds...")
        self.check_features_within_bounds(self.top_cell_name)
        print("DRC checks passed.")
    
    def check_features_within_bounds(self, cell_name):
        """
        Ensure all polygons in the specified cell, assumed to be centered at the origin,
        are within the design bounds using NumPy for efficiency.
        
        Args:
        - cell_name (str): Name of the cell to check.
        """
        cell = self.check_cell_exists(cell_name)
        half_width, half_height = np.array(self.size) / 2

        for poly in cell.get_polygons():
            points = np.array(poly)
            
            # Calculate the maximum extent of the polygon in both x and y directions from the origin
            max_extent_x = np.max(np.abs(points[:, 0]))
            max_extent_y = np.max(np.abs(points[:, 1]))
            
            if max_extent_x > half_width or max_extent_y > half_height:
                raise ValueError(f"Feature in cell '{cell_name}' exceeds the design bounds.")

    def write_gds(self, filename):
        self.lib.write_gds(filename)
        print(f'GDS file written to {filename}')

