import gdspy
import numpy as np
from shapely.geometry import box, MultiPolygon, Polygon, Point
from shapely.affinity import translate
from shapely.ops import unary_union
from shapely.strtree import STRtree
import matplotlib.pyplot as plt
import klayout.db as kdb

TEXT_SPACING_FACTOR = 0.3

class GDSDesign:
    def __init__(self, lib_name='default_lib', filename=None, top_cell_names=['TopCell'], bounds=[-np.inf, np.inf, -np.inf, np.inf], unit=1e-6, precision=1e-9,
                 default_netID=0, default_feature_size=None, default_spacing=None):
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
                self.define_layer(f"{layer}", layer, min_feature_size=default_feature_size, 
                                  min_spacing=default_spacing)

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
    
    def delete_cell(self, cell_name):
        """
        Delete a cell from the GDS library and the internal cell dictionary.

        Args:
        - cell_name (str): Name of the cell to delete.
        """
        if cell_name not in self.cells and cell_name not in self.lib.cells:
            raise ValueError(f"Error: Cell '{cell_name}' does not exist.")
        
        # Remove the cell from the internal dictionary
        if cell_name in self.cells:
            del self.cells[cell_name]
        
        # Remove the cell from the GDS library
        if cell_name in self.lib.cells:
            self.lib.remove(cell_name)
        else:
            raise ValueError(f"Error: Cell '{cell_name}' not found in the GDS library.")
        
    def calculate_cell_size(self, cell_name):
        """
        Calculate the bounding box size of a cell based on its polygons.

        Args:
        - cell_name (str): Name of the cell to calculate the size for.

        Returns:
        - (width, height): Tuple representing the width and height of the cell.
        """
        cell = self.check_cell_exists(cell_name)
        
        # Initialize the bounding box
        min_x, min_y = np.inf, np.inf
        max_x, max_y = -np.inf, -np.inf
        
        for poly in cell.get_polygons():
            points = np.array(poly)
            min_x = min(min_x, np.amin(points[:, 0]))
            max_x = max(max_x, np.amax(points[:, 0]))
            min_y = min(min_y, np.amin(points[:, 1]))
            max_y = max(max_y, np.amax(points[:, 1]))
        
        offset = ((max_x + min_x) / 2, (max_y + min_y) / 2)
        width = max_x - min_x
        height = max_y - min_y

        return width, height, offset

    def add_MLA_alignment_mark(self, cell_name, layer_name, center, rect_width=500, rect_height=20, width_interior=5,
                               extent_x_interior=50, extent_y_interior=50, datatype=0, netID=0, add_text=False, text_height=250,
                               text_angle=0, text_position=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(rect_width, (int, float)), "Error: Rectangle width must be a number."
        assert isinstance(rect_height, (int, float)), "Error: Rectangle height must be a number."
        assert isinstance(width_interior, (int, float)), "Error: Interior cross width must be a number."
        assert isinstance(extent_x_interior, (int, float)), "Error: Interior cross extent along x-axis must be a number."
        assert isinstance(extent_y_interior, (int, float)), "Error: Interior cross extent along y-axis must be a number."
        assert isinstance(datatype, int), "Error: Datatype must be an integer."
        assert isinstance(netID, int), "Error: Net ID must be an integer."
        assert isinstance(add_text, bool), "Error: Add text must be a boolean."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        
        # Check that geometry is valid
        assert rect_width > width_interior, "Error: The width of the rectangle must be greater than the thickness of the interior cross."
        assert rect_height > width_interior, "Error: The height of the rectangle must be greater than the thickness of the interior cross."

        # Check that cell and layer exist
        cell = self.check_cell_exists(cell_name)
        layer_number = self.get_layer_number(layer_name)

        # Calculate the coordinates for the horizontal and vertical parts of the cross
        horizontal_lower_left = (center[0] - extent_x_interior / 2, center[1] - width_interior / 2)
        horizontal_upper_right = (center[0] + extent_x_interior / 2, center[1] + width_interior / 2)
        vertical_lower_left = (center[0] - width_interior / 2, center[1] - extent_y_interior / 2)
        vertical_upper_right = (center[0] + width_interior / 2, center[1] + extent_y_interior / 2)

        # Create rectangles for the cross
        horizontal_rect = gdspy.Rectangle(horizontal_lower_left, horizontal_upper_right, layer=layer_number, datatype=datatype)
        vertical_rect = gdspy.Rectangle(vertical_lower_left, vertical_upper_right, layer=layer_number, datatype=datatype)

        # Add the rectangles to the cell
        self.add_component(cell, cell_name, horizontal_rect, netID, layer_number)
        self.add_component(cell, cell_name, vertical_rect, netID, layer_number)

        outer_L_lower_left = (center[0] - extent_x_interior / 2 - rect_width, center[1] - rect_height / 2)
        outer_L_upper_right = (center[0] - extent_x_interior / 2, center[1] + rect_height / 2)
        outer_R_lower_left = (center[0] + extent_x_interior / 2, center[1] - rect_height / 2)
        outer_R_upper_right = (center[0] + extent_x_interior / 2 + rect_width, center[1] + rect_height / 2)
        outer_T_lower_left = (center[0] - rect_height / 2, center[1] + extent_y_interior / 2)
        outer_T_upper_right = (center[0] + rect_height / 2, center[1] + extent_y_interior / 2 + rect_width)
        outer_B_lower_left = (center[0] - rect_height / 2, center[1] - extent_y_interior / 2 - rect_width)
        outer_B_upper_right = (center[0] + rect_height / 2, center[1] - extent_y_interior / 2)

        outer_L = gdspy.Rectangle(outer_L_lower_left, outer_L_upper_right, layer=layer_number, datatype=datatype)
        outer_R = gdspy.Rectangle(outer_R_lower_left, outer_R_upper_right, layer=layer_number, datatype=datatype)
        outer_T = gdspy.Rectangle(outer_T_lower_left, outer_T_upper_right, layer=layer_number, datatype=datatype)
        outer_B = gdspy.Rectangle(outer_B_lower_left, outer_B_upper_right, layer=layer_number, datatype=datatype)

        self.add_component(cell, cell_name, outer_L, netID, layer_number)
        self.add_component(cell, cell_name, outer_R, netID, layer_number)
        self.add_component(cell, cell_name, outer_T, netID, layer_number)
        self.add_component(cell, cell_name, outer_B, netID, layer_number)

        if add_text:
            text = f"{center}"
            if text_position is None:
                text_position = (center[0] - rect_width/2-len(text)*text_height*TEXT_SPACING_FACTOR, center[1] + rect_width/2)
            self.add_text(cell_name, text, layer_name, text_position, text_height, text_angle)

    def add_resistance_test_structure(self, cell_name, layer_name, center, probe_pad_width=1000, probe_pad_height=1000,
                                      probe_pad_spacing=3000, plug_width=200, plug_height=200, trace_width=5,
                                      trace_spacing=50, switchbacks=18, x_extent=100, text_height=250, text=None,
                                      text_angle=90, text_position=None, add_interlayer_short=False,
                                      short_text=None, layer_name_short=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(probe_pad_width, (int, float)), "Error: Probe pad width must be a number."
        assert isinstance(probe_pad_height, (int, float)), "Error: Probe pad height must be a number."
        assert isinstance(probe_pad_spacing, (int, float)), "Error: Probe pad spacing must be a number."
        assert isinstance(plug_width, (int, float)), "Error: Plug width must be a number."
        assert isinstance(plug_height, (int, float)), "Error: Plug height must be a number."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(trace_spacing, (int, float)), "Error: Trace spacing must be a number."
        assert isinstance(switchbacks, int), "Error: Number of switchbacks must be an integer."
        assert isinstance(x_extent, (int, float)), "Error: X extent must be a number."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        if text is not None:
            assert isinstance(text, str), "Error: Text must be a string."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        assert isinstance(add_interlayer_short, bool), "Error: Add interlayer short must be a boolean."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        if short_text is not None:
            assert isinstance(short_text, str), "Error: Short text must be a string."
        if layer_name_short is not None:
            assert isinstance(layer_name_short, str), "Error: Layer name for the short must be a string."
        
        # Check that the geometry is valid
        margin = (probe_pad_spacing - probe_pad_height - trace_width - trace_spacing * (2 * switchbacks - 1))/2
        assert margin > trace_spacing, f"Error: Not enough space for the switchbacks. Margin is {margin} and trace spacing is {trace_spacing}."

        # Add probe pads and plugs
        self.add_rectangle(cell_name, layer_name, center=(center[0], center[1]-probe_pad_spacing/2), width=probe_pad_width, height=probe_pad_height)
        self.add_rectangle(cell_name, layer_name, center=(center[0], center[1]+probe_pad_spacing/2), width=probe_pad_width, height=probe_pad_height)
        self.add_rectangle(cell_name, layer_name, center=(center[0]-plug_width/2-probe_pad_width/2, center[1]-probe_pad_spacing/2), width=plug_width, height=plug_height)
        self.add_rectangle(cell_name, layer_name, center=(center[0]-plug_width/2-probe_pad_width/2, center[1]+probe_pad_spacing/2), width=plug_width, height=plug_height)

        # The first segments of the traces are fixed
        path_points = []
        distance = 0
        path_points.append((center[0]-plug_width-probe_pad_width/2, center[1]-probe_pad_spacing/2))
        path_points.append((center[0]-plug_width-probe_pad_width/2-x_extent, center[1]-probe_pad_spacing/2))
        distance += x_extent
        path_points.append((center[0]-plug_width-probe_pad_width/2-x_extent, center[1]-probe_pad_spacing/2+probe_pad_height/2))
        distance += probe_pad_height/2

        current_x = center[0]-plug_width-probe_pad_width/2-x_extent
        current_y = center[1]-probe_pad_spacing/2+probe_pad_height/2+margin+trace_width/2

        path_points.append((current_x, current_y))
        distance += margin + trace_width/2
        for i in range(switchbacks):
            current_x += x_extent + plug_width + probe_pad_width
            path_points.append((current_x, current_y))
            current_y += trace_spacing
            path_points.append((current_x, current_y))
            current_x -= x_extent + plug_width + probe_pad_width
            path_points.append((current_x, current_y))
            current_y += trace_spacing
            path_points.append((current_x, current_y))

            distance += 2 * (trace_spacing + x_extent + plug_width + probe_pad_width)

        path_points.append((center[0]-plug_width-probe_pad_width/2-x_extent, center[1]+probe_pad_spacing/2))
        distance += center[1]+probe_pad_spacing/2 - current_y
        path_points.append((center[0]-plug_width-probe_pad_width/2, center[1]+probe_pad_spacing/2))
        distance += x_extent
        self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)
        if text is None:
            text = f"RESISTANCE {distance/1000}MM TRACE WIDTH {trace_width}UM"
        else:
            text += f" RESISTANCE {distance/1000}MM TRACE WIDTH {trace_width}UM"

        if text_position is None:
            text_position = (center[0]+probe_pad_width/2+1.5*text_height, center[1]-len(text)*text_height*TEXT_SPACING_FACTOR)    
        self.add_text(cell_name, text, layer_name, text_position, text_height, text_angle)

        if add_interlayer_short:
            assert layer_name_short is not None, "Error: Layer name for the short must be specified."
            if short_text is None:
                short_text = "INTERLAYER SHORT"
            else:
                short_text += " INTERLAYER SHORT"
            # 0.75 is an arbitrary factor to place the short in a nice spot
            self.add_rectangle(cell_name, layer_name_short, center=(center[0]-probe_pad_width/2, center[1]+probe_pad_height*0.75), 
                               width=probe_pad_width, height=probe_pad_height)
            self.add_rectangle(cell_name, layer_name_short, center=(center[0]-probe_pad_width/2, center[1]-probe_pad_height*0.75), 
                               width=probe_pad_width, height=probe_pad_height)
            self.add_text(cell_name, short_text, layer_name_short, (center[0]-probe_pad_width/2-len(short_text)*text_height*TEXT_SPACING_FACTOR, center[1]), text_height, 0)

    def add_line_test_structure(self, cell_name, layer_name, center, text, line_width=800, line_height=80, num_lines=4, line_spacing=80,
                                text_height=250, text_angle=0, text_position=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(line_width, (int, float)), "Error: Line width must be a number."
        assert isinstance(line_height, (int, float)), "Error: Line height must be a number."
        assert isinstance(num_lines, int), "Error: Number of lines must be an integer."
        assert isinstance(line_spacing, (int, float)), "Error: Line spacing must be a number."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        assert isinstance(text, str), "Error: Text must be a string."

        rect_center = (center[0], center[1]+(num_lines-1)*line_spacing)
        for i in range(num_lines):
            self.add_rectangle(cell_name, layer_name, center=rect_center, width=line_width, height=line_height)
            rect_center = (rect_center[0], rect_center[1]-2*line_spacing)
        
        if text_position is None:
            text_position = (center[0]-len(text)*text_height*TEXT_SPACING_FACTOR, center[1]+(num_lines-1)*line_spacing+text_height)
        self.add_text(cell_name, text, layer_name, text_position, text_height, text_angle)

    def add_p_via_test_structure(self, cell_name, layer_name_1, layer_name_2, via_layer, center, text, layer1_rect_spacing=150,
                                 layer1_rect_width=700, layer1_rect_height=250, layer2_rect_width=600, layer2_rect_height=550,
                                 via_width=7, via_height=7, text_height=250, text_angle=90, text_position=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(layer1_rect_spacing, (int, float)), "Error: Layer 1 rectangle spacing must be a number."
        assert isinstance(layer1_rect_width, (int, float)), "Error: Layer 1 rectangle width must be a number."
        assert isinstance(layer1_rect_height, (int, float)), "Error: Layer 1 rectangle height must be a number."
        assert isinstance(layer2_rect_width, (int, float)), "Error: Layer 2 rectangle width must be a number."
        assert isinstance(layer2_rect_height, (int, float)), "Error: Layer 2 rectangle height must be a number."
        assert isinstance(via_width, (int, float)), "Error: Via width must be a number."
        assert isinstance(via_height, (int, float)), "Error: Via height must be a number."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        assert isinstance(text, str), "Error: Text must be a string."

        # Add rectangles for the first layer
        self.add_rectangle(cell_name, layer_name_1, center=(center[0], center[1]+layer1_rect_spacing/2+layer1_rect_height/2), width=layer1_rect_width, height=layer1_rect_height)
        self.add_rectangle(cell_name, layer_name_1, center=(center[0], center[1]-layer1_rect_spacing/2-layer1_rect_height/2), width=layer1_rect_width, height=layer1_rect_height)
        
        # Add rectangle for the second layer
        self.add_rectangle(cell_name, layer_name_2, center=(center[0], center[1]), width=layer2_rect_width, height=layer2_rect_height)

        # Add vias
        self.add_rectangle(cell_name, via_layer, center=(center[0], center[1]+layer1_rect_spacing/2+layer1_rect_height/2), width=via_width, height=via_height)
        self.add_rectangle(cell_name, via_layer, center=(center[0], center[1]-layer1_rect_spacing/2-layer1_rect_height/2), width=via_width, height=via_height)

        if text_position is None:
            text_position = (center[0]-layer1_rect_width/2 - text_height, center[1] - len(text)*text_height*TEXT_SPACING_FACTOR)
        self.add_text(cell_name, text, layer_name_1, text_position, text_height, text_angle)

    def add_electronics_via_test_structure(self, cell_name, layer_name_1, layer_name_2, via_layer, center, text,
                                           layer_1_rect_width=1550, layer_1_rect_height=700, layer_2_rect_width=600,
                                           layer_2_rect_height=600, layer_2_rect_spacing=250, via_width=7, via_height=7, via_spacing=10,
                                           text_height=250, text_angle=0, text_position=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(layer_1_rect_width, (int, float)), "Error: Layer 1 rectangle width must be a number."
        assert isinstance(layer_1_rect_height, (int, float)), "Error: Layer 1 rectangle height must be a number."
        assert isinstance(layer_2_rect_width, (int, float)), "Error: Layer 2 rectangle width must be a number."
        assert isinstance(layer_2_rect_height, (int, float)), "Error: Layer 2 rectangle height must be a number."
        assert isinstance(layer_2_rect_spacing, (int, float)), "Error: Layer 2 rectangle spacing must be a number."
        assert isinstance(via_width, (int, float)), "Error: Via width must be a number."
        assert isinstance(via_height, (int, float)), "Error: Via height must be a number."
        assert isinstance(via_spacing, (int, float)), "Error: Via spacing must be a number."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        assert isinstance(text, str), "Error: Text must be a string."

        # Add rectangle for the first layer
        self.add_rectangle(cell_name, layer_name_1, center=(center[0], center[1]), width=layer_1_rect_width, height=layer_1_rect_height)

        # Add rectangles for the second layer
        self.add_rectangle(cell_name, layer_name_2, center=(center[0]-layer_2_rect_spacing/2-layer_2_rect_width/2, center[1]), width=layer_2_rect_width, height=layer_2_rect_height)
        self.add_rectangle(cell_name, layer_name_2, center=(center[0]+layer_2_rect_spacing/2+layer_2_rect_width/2, center[1]), width=layer_2_rect_width, height=layer_2_rect_height)        

        # Add vias
        self.add_rectangle(cell_name, via_layer, center=(center[0]-layer_2_rect_spacing/2-via_spacing-via_width/2, center[1]), width=via_width, height=via_height)
        self.add_rectangle(cell_name, via_layer, center=(center[0]+layer_2_rect_spacing/2+via_spacing+via_width/2, center[1]), width=via_width, height=via_height)

        if text_position is None:
            text_position = (center[0]-len(text)*text_height*TEXT_SPACING_FACTOR, center[1] + layer_2_rect_height/2 + text_height)
        self.add_text(cell_name, text, via_layer, text_position, text_height, text_angle)

    def add_short_test_structure(self, cell_name, layer_name, center, text, rect_width=1300,
                                 trace_width=5, num_lines=5, group_spacing=130, num_groups=6, num_lines_vert=100,
                                 text_height=250, text_angle=90, text_position=None):
        # Check that types are valid
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(rect_width, (int, float)), "Error: Rectangle width must be a number."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(num_lines, int), "Error: Number of lines must be an integer."
        assert isinstance(group_spacing, (int, float)), "Error: Group spacing must be a number."
        assert isinstance(num_groups, int), "Error: Number of groups must be an integer."
        assert isinstance(num_lines_vert, int), "Error: Number of vertical lines must be an integer."
        assert isinstance(text_height, (int, float)), "Error: Text height must be a number."
        assert isinstance(text_angle, (int, float)), "Error: Text angle must be a number."
        if text_position is not None:
            assert isinstance(text_position, tuple), "Error: Text position must be a tuple."
        assert isinstance(text, str), "Error: Text must be a string."

        group_height = (4*num_lines - 1)*trace_width + group_spacing + 2*trace_width
        rect_height = group_height*num_groups+trace_width*(num_groups-1)
        rect_spacing = (4*num_lines_vert - 1)*trace_width + 2*trace_width

        # Add rectangles
        self.add_rectangle(cell_name, layer_name, center=(center[0]-rect_spacing/2-rect_width/2, center[1]), width=rect_width, height=rect_height)
        self.add_rectangle(cell_name, layer_name, center=(center[0]+rect_spacing/2+rect_width/2, center[1]), width=rect_width, height=rect_height)

        center1 = center[1]+rect_height/2-trace_width/2
        center2 = center[1]+rect_height/2-trace_width/2-2*trace_width
        for j in range(num_groups):
            for i in range(num_lines):
                self.add_rectangle(cell_name, layer_name, center=(center[0]-trace_width, center1), width=rect_spacing, height=trace_width)
                center1 -= 4*trace_width

                self.add_rectangle(cell_name, layer_name, center=(center[0]+trace_width, center2), width=rect_spacing, height=trace_width)
                center2 -= 4*trace_width

            center3 = center[0]-rect_spacing/2+trace_width+trace_width/2
            center4 = center[0]-rect_spacing/2+trace_width+trace_width/2 + 2*trace_width
            for k in range(num_lines_vert):
                self.add_rectangle(cell_name, layer_name, center=(center3, center1-group_spacing/2+2*trace_width), width=trace_width, height=group_spacing+trace_width)
                center3 += 4*trace_width

                self.add_rectangle(cell_name, layer_name, center=(center4, center1-group_spacing/2), width=trace_width, height=group_spacing+trace_width)
                center4 += 4*trace_width
            
            center1 -= group_spacing
            center2 -= group_spacing

            self.add_rectangle(cell_name, layer_name, center=(center[0]-trace_width, center1), width=rect_spacing, height=trace_width)

            center1 -= 2*trace_width
            center2 -= 2*trace_width

        if text_position is None:
            text_position = (center[0]-rect_spacing/2-rect_width-text_height, center[1] - len(text)*text_height*TEXT_SPACING_FACTOR)
        self.add_text(cell_name, text, layer_name, text_position, text_height, text_angle)

    def add_MLA_alignment_cell(self, box1_layer, box2_layer, cross1_layer, cross2_layer,
                               box_width=2000, box_height=2000, cell_name="MLA_Alignment"):
        # Check that types are valid
        assert isinstance(box_width, (int, float)), "Error: Box width must be a number."
        assert isinstance(box_height, (int, float)), "Error: Box height must be a number."
        assert isinstance(cell_name, str), "Error: Cell name must be a string."
        
        cell = self.add_cell(cell_name)
        self.add_rectangle(cell_name, box1_layer, center=(0, 0), width=box_width, height=box_height)
        self.add_rectangle(cell_name, box2_layer, center=(0, 0), width=box_width, height=box_height)
        self.add_MLA_alignment_mark(cell_name, cross1_layer, center=(-box_width/2, -box_width/2))
        self.add_MLA_alignment_mark(cell_name, cross1_layer, center=(box_width/2, box_width/2))
        self.add_MLA_alignment_mark(cell_name, cross2_layer, center=(0, 0))
                
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
        # If the layer number is already assigned to a different layer, update the layer name to the new name
        existing_layer_numbers = [props['number'] for props in self.layers.values()]
        if layer_number in existing_layer_numbers:
            existing_layer_name = list(self.layers.keys())[existing_layer_numbers.index(layer_number)]
            if layer_name != existing_layer_name:
                print(f"Warning: Layer number {layer_number} is already assigned to layer '{existing_layer_name}'. Updating layer name to '{layer_name}'.")
                self.layers[layer_name] = self.layers.pop(existing_layer_name)

        # Validate DRC parameters
        if min_feature_size is not None and min_feature_size <= 0:
            raise ValueError("Minimum feature size must be positive.")
        if min_spacing is not None and min_spacing <= 0:
            raise ValueError("Minimum spacing must be positive.")
        
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
                      rotation=0, netID=0):
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
        if center is None and rotation != 0:
            center = ((lower_left[0] + upper_right[0]) / 2, (lower_left[1] + upper_right[1]) / 2)
        rectangle.rotate(rotation, center=center)
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

    def add_text(self, cell_name, text, layer_name, position, height, angle=0, datatype=0, netID=0):
        layer_number = self.get_layer_number(layer_name)
        cell = self.check_cell_exists(cell_name)
        
        # Create the text object using KLayout
        layout = kdb.Layout()
        layout.dbu = 1e-3  # 0.001 microns per layout unit
        top_cell = layout.create_cell("TOP")
        
        # Set the layer
        layer_info = kdb.LayerInfo(1, 0)  # Layer 1 with datatype 0
        layer_index = layout.layer(layer_info)

        # Create the text
        text_shape = kdb.TextGenerator.default_generator().text(text, layout.dbu/height)

        # Prepare transformation matrix
        angle_rad = np.deg2rad(angle)
        rotation_matrix = np.array([
            [np.cos(angle_rad), -np.sin(angle_rad)],
            [np.sin(angle_rad), np.cos(angle_rad)]
        ])
        translation_vector = np.array(position)
        
        top_cell.shapes(layer_index).insert(text_shape)

        # Extract polygons from the text shape and convert to gdspy polygons
        for polygon in text_shape.each():
            points = []
            for edge in polygon.each_edge():
                point = np.array([edge.x1 * layout.dbu, edge.y1 * layout.dbu])
                rotated_point = rotation_matrix.dot(point)
                transformed_point = rotated_point + translation_vector
                points.append(tuple(transformed_point))
            gdspy_polygon = gdspy.Polygon(points, layer=layer_number, datatype=datatype)
            self.add_component(cell, cell_name, gdspy_polygon, netID, layer_number)

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
        # IMPORTANT: Need to iterate until no more intersections are found
        while True:
            merged_polygons = cluster_intersecting_polygons(shapely_polygons)
            if len(merged_polygons) == len(shapely_polygons):
                break
            shapely_polygons = merged_polygons

        # Efficiently check for spacing violations between merged polygons
        if len(merged_polygons) < 2:
            return  # If there is less than two polygons, no minimum spacing issues can occur

        tree = STRtree(merged_polygons)

        for i, poly1 in enumerate(merged_polygons):
            idxs, dists = tree.query_nearest(poly1, exclusive=True, return_distance=True)
            distance = min(dists)
            j = idxs[np.argmin(dists)]
            if distance < min_spacing:
                plt.figure(figsize=(8, 8))
                plt.plot(merged_polygons[i].exterior.xy[0], merged_polygons[i].exterior.xy[1], label='Polygon 1')
                plt.plot(merged_polygons[j].exterior.xy[0], merged_polygons[j].exterior.xy[1], label='Polygon 2')
                plt.legend()
                plt.show()
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

    def determine_available_space(self, substrate_layer_name):
        """
        Determine the available space in the design based on the substrate layer.

        Args:
        - substrate_layer_name (str): The name of the substrate layer.

        Returns:
        - available_space (shapely.geometry.MultiPolygon): The available space as a MultiPolygon.
        """
        substrate_layer_number = self.get_layer_number(substrate_layer_name)
        substrate_polygons = []

        # Get polygons from the substrate layer in top cells
        for top_cell_name in self.top_cell_names:
            cell = self.check_cell_exists(top_cell_name)
            polygons_by_spec = cell.get_polygons(by_spec=True)
            for (lay, dat), polys in polygons_by_spec.items():
                if lay == substrate_layer_number:
                    substrate_polygons.extend(polys)
        
        if not substrate_polygons:
            raise ValueError(f"No polygons found in the substrate layer '{substrate_layer_name}'.")

        # Create a union of all substrate polygons
        substrate_union = unary_union([Polygon(poly) for poly in substrate_polygons])

        # Get polygons from all other layers in top cells
        all_other_polygons = []
        for top_cell_name in self.top_cell_names:
            cell = self.check_cell_exists(top_cell_name)
            polygons_by_spec = cell.get_polygons(by_spec=True)
            for (lay, dat), polys in polygons_by_spec.items():
                if lay != substrate_layer_number:
                    all_other_polygons.extend(polys)
        
        # Create a union of all other polygons
        all_other_union = unary_union([Polygon(poly) for poly in all_other_polygons])

        # Subtract the occupied space from the substrate
        available_space = substrate_union.difference(all_other_union)
        return available_space
    
    def find_position_for_rectangle(self, available_space, width, height, offset, step_size=100, buffer=100):
        width = width + 2 * buffer
        height = height + 2 * buffer

        # Check if either the width or height is larger than the bounding box of the available space
        minx, miny, maxx, maxy = available_space.bounds
        if width > maxx - minx or height > maxy - miny:
            raise ValueError("Rectangle dimensions exceed the available space.")

        rectangle = Polygon([
            (-width / 2, -height / 2),
            (width / 2, -height / 2),
            (width / 2, height / 2),
            (-width / 2, height / 2)
        ])

        # Use R-tree for fast spatial indexing
        polygons = [geom for geom in available_space.geoms if geom.is_valid]
        spatial_index = STRtree(polygons)

        # Create a bounding box for the rectangle to use in the spatial index query
        rect_bbox = Polygon([
            (-width / 2 + offset[0], -height / 2 + offset[1]),
            (width / 2 + offset[0], -height / 2 + offset[1]),
            (width / 2 + offset[0], height / 2 + offset[1]),
            (-width / 2 + offset[0], height / 2 + offset[1])
        ])

        # Query the spatial index for polygons that intersect with the rectangle bounding box
        candidate_polygons = spatial_index.query(rect_bbox)

        for idx in candidate_polygons:
            minx, miny, maxx, maxy = polygons[idx].bounds
            x_positions = np.arange(minx, maxx, step_size)
            y_positions = np.arange(miny, maxy, step_size)

            for x, y in np.nditer(np.meshgrid(x_positions, y_positions)):
                print(f"Trying point ({x}, {y})")
                translated_rectangle = translate(rectangle, xoff=x + offset[0], yoff=y + offset[1])
                
                if polygons[idx].contains(translated_rectangle):
                    print(f"Rectangle fits at ({x}, {y})")
                    return (x, y)
                print("Rectangle does not fit.")

        raise ValueError("No available space found.")

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
            intersecting_indices = tree.query(poly, predicate='intersects')
            cluster = []
            for idx in intersecting_indices:
                if idx != i:
                    neighbor = polygons[idx]  # Directly reference the polygon using its index
                    if neighbor.intersects(poly) and idx not in visited:
                        visited.add(idx)  # Mark this index as processed
                        cluster.append(neighbor)

            visited.add(i)  # Mark the original polygon as processed
            cluster.append(poly)  # Add the original polygon to the cluster
            clusters.append(unary_union(cluster))
    
    return clusters

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
