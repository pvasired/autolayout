import gdspy
import numpy as np

class GDSDesign:
    def __init__(self, lib_name='default_lib', top_cell_name='TopCell'):
        self.lib = gdspy.GdsLibrary(name=lib_name)
        self.cells = {}
        self.top_cell_name = top_cell_name
        self.top_cell = self.add_cell(top_cell_name)
        self.layers = {}
        # DRC rules for each layer: layer_name -> (min_feature_size, min_spacing)
        self.drc_rules = {}

    def add_cell(self, cell_name):
        if cell_name in self.cells:
            print(f"Warning: Cell '{cell_name}' already exists. Returning existing cell.")
            return self.cells[cell_name]
        cell = self.lib.new_cell(cell_name)
        self.cells[cell_name] = cell
        return cell

    def define_layer(self, layer_name, layer_number, description=None):
        if layer_name in self.layers:
            print(f"Warning: Layer name '{layer_name}' already defined. Updating properties.")
        self.layers[layer_name] = {'number': layer_number, 'description': description}

    def get_layer_number(self, layer_name):
        if layer_name not in self.layers:
            raise ValueError(f"Error: Layer name '{layer_name}' not defined. Please define layer first.")
        return self.layers[layer_name]['number']

    def check_cell_exists(self, cell_name):
        if cell_name not in self.cells:
            raise ValueError(f"Error: Cell '{cell_name}' does not exist. Please add it first.")
        return self.cells[cell_name]

    def add_rectangle(self, cell_name, *args, layer_name, datatype=0):
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

        if len(args) == 3:
            # Assume center, width, height format
            center, width, height = args
            lower_left = (center[0] - width / 2, center[1] - height / 2)
            upper_right = (center[0] + width / 2, center[1] + height / 2)
        elif len(args) == 2:
            # Assume lower_left, upper_right format
            lower_left, upper_right = args
        else:
            raise ValueError("Invalid arguments for rectangle. Provide either (center, width, height) or (lower_left, upper_right).")

        # Create and add the rectangle
        rectangle = gdspy.Rectangle(lower_left, upper_right, layer=layer_number, datatype=datatype)
        self.cells[cell_name].add(rectangle)

    def add_polygon(self, cell_name, points, layer_name, datatype=0):
        layer_number = self.get_layer_number(layer_name)
        polygon = gdspy.Polygon(points, layer=layer_number, datatype=datatype)
        self.check_cell_exists(cell_name).add(polygon)

    def add_path(self, cell_name, width, points, layer_name, datatype=0):
        layer_number = self.get_layer_number(layer_name)
        path = gdspy.FlexPath(points, width, layer=layer_number, datatype=datatype)
        self.check_cell_exists(cell_name).add(path)

    def add_circle(self, cell_name, center, radius, layer_name, datatype=0, tolerance=0.01):
        layer_number = self.get_layer_number(layer_name)
        circle = gdspy.Round(center, radius, tolerance=tolerance, layer=layer_number, datatype=datatype)
        self.check_cell_exists(cell_name).add(circle)

    def add_cell_reference(self, parent_cell_name, child_cell_name, origin=(0, 0), magnification=1, rotation=0):
        parent_cell = self.check_cell_exists(parent_cell_name)
        child_cell = self.check_cell_exists(child_cell_name)
        ref = gdspy.CellReference(child_cell, origin=origin, magnification=magnification, rotation=rotation)
        parent_cell.add(ref)

    def add_cell_array(self, target_cell_name, cell_name_to_array, n, m, spacing_x, spacing_y, origin=(0, 0)):
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
                ref = gdspy.CellReference(cell_to_array, origin=(x_position, y_position))
                target_cell.add(ref)

    def check_minimum_feature_size(self, cell_name, layer_name, min_size):
        """
        Check if all features on a specified layer in a cell meet the minimum feature size.

        Args:
        - cell_name (str): Name of the cell to check.
        - layer_name (str): Name of the layer to check.
        - min_size (float): Minimum feature size.
        """
        self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)

        for polygon in self.cells[cell_name].polygons:
            if polygon.layer == layer_number:
                bbox = polygon.get_bounding_box()
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
        Run DRC checks for all layers in the top cell based on defined DRC rules.
        """
        for layer_name, rules in self.drc_rules.items():
            min_feature_size, min_spacing = rules
            if min_feature_size:
                print(f"Checking minimum feature size ({min_feature_size}µm) on layer '{layer_name}'...")
                self.check_minimum_feature_size(self.top_cell_name, layer_name, min_feature_size)
            if min_spacing:
                print(f"Checking minimum spacing ({min_spacing}µm) on layer '{layer_name}'...")
                self.check_minimum_spacing(self.top_cell_name, layer_name, min_spacing)
        print("DRC checks completed.")

    def write_gds(self, filename):
        self.lib.write_gds(filename)
        print(f'GDS file written to {filename}')

