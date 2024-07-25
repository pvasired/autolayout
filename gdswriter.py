import gdspy
import numpy as np
from shapely.geometry import box, MultiPolygon, Polygon, Point
from shapely.affinity import translate
from shapely.prepared import prep
from shapely.ops import unary_union
from shapely.strtree import STRtree
import matplotlib.pyplot as plt
import klayout.db as kdb
import geopandas as gpd
from phidl import Device, Path, CrossSection
import phidl.routing as pr
import phidl.geometry as pg
from copy import deepcopy
import math
import a_star

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
            self.filename = None
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
            self.filename = filename

    def add_cell(self, cell_name):
        if cell_name in self.cells or cell_name in self.lib.cells or cell_name in gdspy.current_library.cells:
            print(f"Warning: Cell '{cell_name}' already exists. Overwriting existing cell.")
            self.delete_cell(cell_name)
        cell = self.lib.new_cell(cell_name, overwrite_duplicate=True)
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
        if cell_name not in self.cells and cell_name not in self.lib.cells and cell_name not in gdspy.current_library.cells:
            raise ValueError(f"Error: Cell '{cell_name}' does not exist.")
        
        # Remove the cell from the internal dictionary
        if cell_name in self.cells:
            del self.cells[cell_name]
        # Remove the cell from the GDS library
        if cell_name in self.lib.cells:
            del self.lib.cells[cell_name]
            self.lib.remove(cell_name)
        if cell_name in gdspy.current_library.cells:
            del gdspy.current_library.cells[cell_name]
            gdspy.current_library.remove(cell_name)
        
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

    def add_circle_as_polygon(self, cell_name, center, radius, layer_name, num_points=5000, datatype=0, netID=0):
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
        parent_cell = self.lib.cells[parent_cell_name]
        child_cell = self.lib.cells[child_cell_name]
        ref = gdspy.CellReference(child_cell, origin=origin, magnification=magnification, rotation=rotation, x_reflection=x_reflection)
        self.add_component(parent_cell, parent_cell_name, ref, netID)

    def add_cell_array(self, target_cell_name, cell_name_to_array, copies_x, copies_y, spacing_x, spacing_y, origin=(0, 0),
                       magnification=1, rotation=0, x_reflection=False, netIDs=None):
        target_cell = self.lib.cells[target_cell_name]
        cell_to_array = self.lib.cells[cell_name_to_array]
        
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
    
    def add_regular_array_escape_two_sided(self, trace_cell_name, center, layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=50, routing_angle=45,
                                           escape_y=False):
        self.check_cell_exists(trace_cell_name)
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(pitch_x, (int, float)), "Error: Pitch in the x-direction must be a number."
        assert isinstance(pitch_y, (int, float)), "Error: Pitch in the y-direction must be a number."
        assert isinstance(array_size_x, int), "Error: Array size in the x-direction must be an integer."
        assert isinstance(array_size_y, int), "Error: Array size in the y-direction must be an integer."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(pad_diameter, (int, float)), "Error: Pad diameter must be a number."
        assert isinstance(escape_extent, (int, float)), "Error: Escape extent must be a number."
        assert isinstance(routing_angle, (int, float)), "Error: Routing angle must be a number."
        assert isinstance(escape_y, bool), "Error: Escape direction must be a boolean."

        effective_pitch_y = pitch_y - pad_diameter
        effective_pitch_x = pitch_x - pad_diameter
        # Create the 2D grid using NumPy
        x = np.linspace(-pitch_x*(array_size_x-1)/2, pitch_x*(array_size_x-1)/2, array_size_x)
        y = np.linspace(-pitch_y*(array_size_y-1)/2, pitch_y*(array_size_y-1)/2, array_size_y)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        # Stack the coordinates into a single 3D array
        grid = np.stack((xx, yy), axis=-1)
        ports = np.full_like(grid, np.nan)
        orientations = np.full((grid.shape[0], grid.shape[1], 1), np.nan)

        grid[:, :, 0] = grid[:, :, 0] + center[0]
        grid[:, :, 1] = grid[:, :, 1] + center[1]

        if not escape_y:
            for j in range(int(array_size_y/2)):
                available_length = effective_pitch_y - 3 * trace_width
                num_traces = int(array_size_x/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in range(int(array_size_x/2)):
                    hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][j] = np.array(hinged_path[-1])
                    orientations[i][j] = 180
                    cnt += 1

                available_length = effective_pitch_y - 3 * trace_width
                num_traces = array_size_x - int(array_size_x/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                for i in iter_inds:
                    hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][j] = np.array(hinged_path[-1])
                    orientations[i][j] = 0
                    cnt += 1

            for j in range(int(array_size_y/2), array_size_y):
                available_length = effective_pitch_y - 3 * trace_width
                num_traces = int(array_size_x/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in range(int(array_size_x/2)):
                    hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][j] = np.array(hinged_path[-1])
                    orientations[i][j] = 180
                    cnt += 1

                available_length = effective_pitch_y - 3 * trace_width
                num_traces = array_size_x - int(array_size_x/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                for i in iter_inds:
                    hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][j] = np.array(hinged_path[-1])
                    orientations[i][j] = 0
                    cnt += 1
        else:
            for j in range(int(array_size_x/2)):
                available_length = effective_pitch_x - 3 * trace_width
                num_traces = int(array_size_y/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in range(int(array_size_y/2)):
                    hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[j][i] = np.array(hinged_path[-1])
                    orientations[j][i] = 270
                    cnt += 1

            for j in range(int(array_size_x/2), array_size_x):
                available_length = effective_pitch_x - 3 * trace_width
                num_traces = int(array_size_y/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in range(int(array_size_y/2)):
                    hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[j][i] = np.array(hinged_path[-1])
                    orientations[j][i] = 270
                    cnt += 1

            for j in range(int(array_size_x/2)):
                available_length = effective_pitch_x - 3 * trace_width
                num_traces = array_size_y - int(array_size_y/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                for i in iter_inds:
                    hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[j][i] = np.array(hinged_path[-1])
                    orientations[j][i] = 90
                    cnt += 1

            for j in range(int(array_size_x/2), array_size_x):
                available_length = effective_pitch_x - 3 * trace_width
                num_traces = array_size_y - int(array_size_y/2)
                assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                spacing = available_length / (num_traces - 1)
                cnt = 0
                iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                for i in iter_inds:
                    hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[j][i] = np.array(hinged_path[-1])
                    orientations[j][i] = 90
                    cnt += 1

        return np.around(grid.reshape(array_size_x*array_size_y, 2), 3), np.around(ports.reshape(array_size_x*array_size_y, 2), 3), orientations.reshape(array_size_x*array_size_y)
    
    # The traces escape from the array on the positive and negative x directions and the positive y direction
    def add_regular_array_escape_three_sided(self, trace_cell_name, center, layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=50, routing_angle=45,
                                             escape_y=True, escape_negative=False):
        self.check_cell_exists(trace_cell_name)
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(pitch_x, (int, float)), "Error: Pitch in the x-direction must be a number."
        assert isinstance(pitch_y, (int, float)), "Error: Pitch in the y-direction must be a number."
        assert isinstance(array_size_x, int), "Error: Array size in the x-direction must be an integer."
        assert isinstance(array_size_y, int), "Error: Array size in the y-direction must be an integer."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(pad_diameter, (int, float)), "Error: Pad diameter must be a number."
        assert isinstance(escape_extent, (int, float)), "Error: Escape extent must be a number."
        assert isinstance(routing_angle, (int, float)), "Error: Routing angle must be a number."
        assert isinstance(escape_y, bool), "Error: Escape direction must be a boolean."
        assert isinstance(escape_negative, bool), "Error: Escape negative must be a boolean."

        effective_pitch_y = pitch_y - pad_diameter
        effective_pitch_x = pitch_x - pad_diameter
        # Create the 2D grid using NumPy
        x = np.linspace(-pitch_x*(array_size_x-1)/2, pitch_x*(array_size_x-1)/2, array_size_x)
        y = np.linspace(-pitch_y*(array_size_y-1)/2, pitch_y*(array_size_y-1)/2, array_size_y)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        # Stack the coordinates into a single 3D array
        grid = np.stack((xx, yy), axis=-1)
        ports = np.full_like(grid, np.nan)
        orientations = np.full((grid.shape[0], grid.shape[1], 1), np.nan)

        grid[:, :, 0] = grid[:, :, 0] + center[0]
        grid[:, :, 1] = grid[:, :, 1] + center[1]

        if escape_y:
            if not escape_negative:
                for j in range(int(array_size_y/2)):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_x/2)):
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=180, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 180
                        cnt += 1

                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=180, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 0
                        cnt += 1

                for j in range(int(array_size_x/2)):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y - int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 90
                        cnt += 1
                
                for j in range(int(array_size_x/2), array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y - int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=-90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 90
                        cnt += 1
            
            else:
                for j in range(int(array_size_x/2)):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_y/2)):
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 270
                        cnt += 1

                for j in range(int(array_size_x/2), array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_y/2)):
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 270
                        cnt += 1

                for j in range(int(array_size_y/2), array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_x/2)):
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=0, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 180
                        cnt += 1

                for j in range(int(array_size_y/2), array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=0, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 0
                        cnt += 1

        else:
            if not escape_negative:
                for j in range(int(array_size_x/2)):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_y/2)):
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 270
                        cnt += 1
                
                for j in range(int(array_size_x/2)):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y - int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 90
                        cnt += 1

                for j in range(int(array_size_y/2)):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=180, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 0
                        cnt += 1
                
                for j in range(int(array_size_y/2), array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_x/2), array_size_x))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=0, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 0
                        cnt += 1
            
            else:
                for j in range(int(array_size_y/2)):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_x/2)):
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=180, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 180
                        cnt += 1
                
                for j in range(int(array_size_y/2), array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x - int(array_size_x/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_x/2)):
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=0, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 180
                        cnt += 1

                for j in range(int(array_size_x/2), array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(int(array_size_y/2)):
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 270
                        cnt += 1
                
                for j in range(int(array_size_x/2), array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y - int(array_size_y/2)
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(int(array_size_y/2), array_size_y))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=-90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 90
                        cnt += 1
        
        return np.around(grid.reshape(array_size_x*array_size_y, 2), 3), np.around(ports.reshape(array_size_x*array_size_y, 2), 3), orientations.reshape(array_size_x*array_size_y)
    
    def add_regular_array_escape_one_sided(self, trace_cell_name, center, layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=50, routing_angle=45,
                                           escape_y=False, escape_negative=True):
        self.check_cell_exists(trace_cell_name)
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(pitch_x, (int, float)), "Error: Pitch in the x-direction must be a number."
        assert isinstance(pitch_y, (int, float)), "Error: Pitch in the y-direction must be a number."
        assert isinstance(array_size_x, int), "Error: Array size in the x-direction must be an integer."
        assert isinstance(array_size_y, int), "Error: Array size in the y-direction must be an integer."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(pad_diameter, (int, float)), "Error: Pad diameter must be a number."
        assert isinstance(escape_extent, (int, float)), "Error: Escape extent must be a number."
        assert isinstance(routing_angle, (int, float)), "Error: Routing angle must be a number."
        assert isinstance(escape_y, bool), "Error: Escape direction must be a boolean."
        assert isinstance(escape_negative, bool), "Error: Escape negative must be a boolean."

        effective_pitch_y = pitch_y - pad_diameter
        effective_pitch_x = pitch_x - pad_diameter
        # Create the 2D grid using NumPy
        x = np.linspace(-pitch_x*(array_size_x-1)/2, pitch_x*(array_size_x-1)/2, array_size_x)
        y = np.linspace(-pitch_y*(array_size_y-1)/2, pitch_y*(array_size_y-1)/2, array_size_y)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        # Stack the coordinates into a single 3D array
        grid = np.stack((xx, yy), axis=-1)
        ports = np.full_like(grid, np.nan)
        orientations = np.full((grid.shape[0], grid.shape[1], 1), np.nan)

        grid[:, :, 0] = grid[:, :, 0] + center[0]
        grid[:, :, 1] = grid[:, :, 1] + center[1]

        if not escape_y:
            if escape_negative:
                for j in range(array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(array_size_x):
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][j][0]-grid[0][j][0]+escape_extent, post_rotation=0, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 180
                        cnt += 1
            else:
                for j in range(array_size_y):
                    available_length = effective_pitch_y - 3 * trace_width
                    num_traces = array_size_x
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(array_size_x))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[i][j], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][j][0]-grid[i][j][0]+escape_extent, post_rotation=0, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[i][j] = np.array(hinged_path[-1])
                        orientations[i][j] = 0
                        cnt += 1
        else:
            if escape_negative:
                for j in range(array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    for i in range(array_size_y):
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][i][1]-grid[j][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 270
                        cnt += 1
            else:
                for j in range(array_size_x):
                    available_length = effective_pitch_x - 3 * trace_width
                    num_traces = array_size_y
                    assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    spacing = available_length / (num_traces - 1)
                    cnt = 0
                    iter_inds = np.flip(np.arange(array_size_y))
                    for i in iter_inds:
                        hinged_path = create_hinged_path(grid[j][i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[j][-1][1]-grid[j][i][1]+escape_extent, post_rotation=-90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[j][i] = np.array(hinged_path[-1])
                        orientations[j][i] = 90
                        cnt += 1
        
        return np.around(grid.reshape(array_size_x*array_size_y, 2), 3), np.around(ports.reshape(array_size_x*array_size_y, 2), 3), orientations.reshape(array_size_x*array_size_y)

    # The traces escape from all four sides of the array
    def add_regular_array_escape_four_sided(self, trace_cell_name, center, layer_name, pitch_x, pitch_y, array_size_x, array_size_y, trace_width, pad_diameter, escape_extent=50, routing_angle=45):
        self.check_cell_exists(trace_cell_name)
        assert isinstance(center, tuple), "Error: Center must be a tuple."
        assert isinstance(pitch_x, (int, float)), "Error: Pitch in the x-direction must be a number."
        assert isinstance(pitch_y, (int, float)), "Error: Pitch in the y-direction must be a number."
        assert isinstance(array_size_x, int), "Error: Array size in the x-direction must be an integer."
        assert isinstance(array_size_y, int), "Error: Array size in the y-direction must be an integer."
        assert isinstance(trace_width, (int, float)), "Error: Trace width must be a number."
        assert isinstance(pad_diameter, (int, float)), "Error: Pad diameter must be a number."
        assert isinstance(escape_extent, (int, float)), "Error: Escape extent must be a number."
        assert isinstance(routing_angle, (int, float)), "Error: Routing angle must be a number."

        effective_pitch_x = pitch_x - pad_diameter
        effective_pitch_y = pitch_y - pad_diameter
        # Assuming the array is centered at the origin, find the diagonal lines that connect the corners of the array 
        # and divide the array into four triangluar quadrants

        # Create the 2D grid using NumPy
        x = np.linspace(-pitch_x*(array_size_x-1)/2, pitch_x*(array_size_x-1)/2, array_size_x)
        y = np.linspace(-pitch_y*(array_size_y-1)/2, pitch_y*(array_size_y-1)/2, array_size_y)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        # Stack the coordinates into a single 3D array
        grid = np.stack((xx, yy), axis=-1)
        ports = np.full_like(grid, np.nan)
        orientations = np.full((grid.shape[0], grid.shape[1], 1), np.nan)

        m_pos = grid[0][0][1]/grid[0][0][0]
        m_neg = grid[-1][0][1]/grid[-1][0][0]

        # Initialize lists to hold indices of each triangular section
        bottom_triangle = []
        right_triangle = []
        top_triangle = []
        left_triangle = []

        # Iterate through the grid to determine the section for each point
        for i in range(array_size_x):
            for j in range(array_size_y):
                x_coord, y_coord = grid[i, j]
                if y_coord <= m_pos * x_coord and y_coord < m_neg * x_coord or (y_coord == 0 and x_coord == 0):
                    bottom_triangle.append((i, j))
                    orientations[i][j] = 270
                elif y_coord >= m_neg * x_coord and y_coord < m_pos * x_coord:
                    right_triangle.append((i, j))
                    orientations[i][j] = 0
                elif y_coord >= m_pos * x_coord and y_coord > m_neg * x_coord:
                    top_triangle.append((i, j))
                    orientations[i][j] = 90
                elif y_coord <= m_neg * x_coord and y_coord > m_pos * x_coord:
                    left_triangle.append((i, j))
                    orientations[i][j] = 180

        # Convert lists to arrays for easier manipulation if needed
        bottom_triangle = np.array(bottom_triangle)
        right_triangle = np.array(right_triangle)
        top_triangle = np.array(top_triangle)
        left_triangle = np.array(left_triangle)

        grid[:, :, 0] = grid[:, :, 0] + center[0]
        grid[:, :, 1] = grid[:, :, 1] + center[1]

        bottom_split = [bottom_triangle[bottom_triangle[:, 0] == value] for value in np.unique(bottom_triangle[:, 0])]
        available_length = effective_pitch_x - 3 * trace_width
        if array_size_x % 2 == 0:
            special_column = int(array_size_x/2)-1
        else:
            special_column = int(array_size_x/2)
        for split in bottom_split:
            cnt = 0
            for i in range(len(split)):
                # Bottom row vertical traces
                if split[i][1] == 0:
                    a, b = split[i]
                    path_points = [tuple(grid[a][b]), (grid[a][b][0], grid[a][b][1]-escape_extent)]
                    self.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)
                    ports[a][b] = np.array(path_points[-1])
                # Special case for only one trace in a column to route out
                elif split[i][1] == 1 and len(split) == 2:
                    assert round(3*trace_width, 3) <= effective_pitch_x, f"Not enough space for 1 trace with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    a, b = split[i]
                    if a < special_column:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[a][b][1]-grid[a][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                    elif a > int(array_size_x/2):
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[a][b][1]-grid[a][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                # General case for multiple traces in a column to route out
                else:
                    a, b = split[i]
                    if a < special_column:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][b][1]-grid[a][0][1]+escape_extent, post_rotation=90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
                    elif a > int(array_size_x/2):
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][b][1]-grid[a][0][1]+escape_extent, post_rotation=-90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
        
        # Handle the special columns for even x array sizes
        if array_size_x % 2 == 0:
            # Get the split where the first element is the special column
            special_split = bottom_triangle[bottom_triangle[:, 0] == special_column]
            left_route = np.arange(1, special_split[:, 1].max(), 2)
            if special_split[:, 1].max() not in left_route and special_split[:, 1].max() != 0:
                left_route = np.append(left_route, special_split[:, 1].max())
            left_route = np.sort(left_route)

            remaining_inds_L = np.setdiff1d(np.arange(1, special_split[:, 1].max()+1), left_route)
            num_traces = len(left_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in left_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, left_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][left_route[0]][1]-grid[special_column][0][1]+escape_extent, 
                                                post_rotation=90, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][left_route[0]] = np.array(hinged_path[-1])

            special_split = bottom_triangle[bottom_triangle[:, 0] == special_column+1]
            right_route = np.arange(1, special_split[:, 1].max(), 2)
            if special_split[:, 1].max() not in right_route and special_split[:, 1].max() != 0:
                right_route = np.append(right_route, special_split[:, 1].max())
            right_route = np.sort(right_route)

            remaining_inds_R = np.setdiff1d(np.arange(1, special_split[:, 1].max()+1), right_route)
            num_traces = len(right_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in right_route:
                    hinged_path = create_hinged_path(grid[special_column+1, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column+1][i][1]-grid[special_column+1][0][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column+1][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column+1, right_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column+1][right_route[0]][1]-grid[special_column+1][0][1]+escape_extent, 
                                                post_rotation=-90, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column+1][right_route[0]] = np.array(hinged_path[-1])
            
            num_traces = len(remaining_inds_L) + len(remaining_inds_R)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in remaining_inds_L:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
                
                cnt = 0
                for i in remaining_inds_R:
                    hinged_path = create_hinged_path(grid[special_column+1, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column+1][i][1]-grid[special_column+1][0][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column+1][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                for i in remaining_inds_L:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                for i in remaining_inds_R:
                    hinged_path = create_hinged_path(grid[special_column+1, i], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column+1][i][1]-grid[special_column+1][0][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column+1][i] = np.array(hinged_path[-1])

        # Handle the special columns for odd x array sizes
        else:
            special_split = bottom_triangle[bottom_triangle[:, 0] == special_column]
            left_route = np.arange(1, special_split[:, 1].max()+1, 2)
            right_route = np.setdiff1d(np.arange(1, special_split[:, 1].max()+1), left_route)

            num_traces = len(left_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in left_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, left_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][left_route[0]][1]-grid[special_column][0][1]+escape_extent, 
                                                post_rotation=90, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][left_route[0]] = np.array(hinged_path[-1])
            
            num_traces = len(right_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in right_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][i][1]-grid[special_column][0][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, right_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][right_route[0]][1]-grid[special_column][0][1]+escape_extent, 
                                                post_rotation=-90, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][right_route[0]] = np.array(hinged_path[-1])

        right_split = [right_triangle[right_triangle[:, 1] == value] for value in np.unique(right_triangle[:, 1])]
        available_length = effective_pitch_y - 3 * trace_width
        if array_size_y % 2 == 0:
            special_row = int(array_size_y/2)-1
        else:
            special_row = int(array_size_y/2)
        for split in right_split:
            split = split[np.flip(np.argsort(split[:, 0]))]
            cnt = 0
            for i in range(len(split)):
                # Right column horizontal traces
                if split[i][0] == array_size_x-1:
                    a, b = split[i]
                    path_points = [tuple(grid[a][b]), (grid[a][b][0]+escape_extent, grid[a][b][1])]
                    self.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)
                    ports[a][b] = np.array(path_points[-1])
                # Special case for only one trace in a column to route out
                elif split[i][0] == array_size_x-2 and len(split) == 2:
                    assert round(3*trace_width, 3) <= effective_pitch_y, f"Not enough space for 1 trace with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    a, b = split[i]
                    if b < special_row:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][b][0]-grid[a][b][0]+escape_extent, post_rotation=180, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                    elif b > int(array_size_y/2):
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][b][0]-grid[a][b][0]+escape_extent, post_rotation=0, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                # General case for multiple traces in a column to route out
                else:
                    a, b = split[i]
                    if b < special_row:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][b][0]-grid[a][b][0]+escape_extent, post_rotation=180, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
                    elif b > int(array_size_y/2):
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][b][0]-grid[a][b][0]+escape_extent, post_rotation=0, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
        
        # Handle the special rows for even y array sizes
        if array_size_y % 2 == 0:
            # Get the split where the first element is the special row
            special_split = right_triangle[right_triangle[:, 1] == special_row]
            bottom_route = -np.arange(-(array_size_x-2), -special_split[:, 0].min()+1, 2)
            
            if special_split[:, 0].min() not in bottom_route and special_split[:, 0].min() != array_size_x-1:
                bottom_route = np.append(bottom_route, special_split[:, 0].min())
            bottom_route = np.flip(np.sort(bottom_route))

            remaining_inds_B = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_x-2), -special_split[:, 0].min()+1)), bottom_route))
            num_traces = len(bottom_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in bottom_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row][0]-grid[i][special_row][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[bottom_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row][0]-grid[bottom_route[0]][special_row][0]+escape_extent, 
                                                post_rotation=180, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[bottom_route[0]][special_row] = np.array(hinged_path[-1])

            special_split = right_triangle[right_triangle[:, 1] == special_row+1]
            top_route = -np.arange(-(array_size_x-2), -special_split[:, 0].min()+1, 2)
            if special_split[:, 0].min() not in top_route and special_split[:, 0].min() != array_size_x-1:
                top_route = np.append(top_route, special_split[:, 0].min())
            top_route = np.flip(np.sort(top_route))

            remaining_inds_T = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_x-2), -special_split[:, 0].min()+1)), top_route))
            num_traces = len(top_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in top_route:
                    hinged_path = create_hinged_path(grid[i, special_row+1], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row+1][0]-grid[i][special_row+1][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row+1] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[top_route[0], special_row+1], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row+1][0]-grid[top_route[0]][special_row+1][0]+escape_extent, 
                                                post_rotation=0, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[top_route[0]][special_row+1] = np.array(hinged_path[-1])

            num_traces = len(remaining_inds_B) + len(remaining_inds_T)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in remaining_inds_B:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row][0]-grid[i][special_row][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
                cnt = 0
                for i in remaining_inds_T:
                    hinged_path = create_hinged_path(grid[i, special_row+1], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row+1][0]-grid[i][special_row+1][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row+1] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                for i in remaining_inds_B:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row][0]-grid[i][special_row][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                for i in remaining_inds_T:
                    hinged_path = create_hinged_path(grid[i, special_row+1], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row+1][0]-grid[i][special_row+1][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row+1] = np.array(hinged_path[-1])
                
        else:
            special_split = right_triangle[right_triangle[:, 1] == special_row]
            bottom_route = -np.arange(-(array_size_x-2), -special_split[:, 0].min()+1, 2)
            top_route = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_x-2), -special_split[:, 0].min()+1)), bottom_route))

            num_traces = len(bottom_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in bottom_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row][0]-grid[i][special_row][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[bottom_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row][0]-grid[bottom_route[0]][special_row][0]+escape_extent, 
                                                post_rotation=180, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[bottom_route[0]][special_row] = np.array(hinged_path[-1])

            num_traces = len(top_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in top_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[-1][special_row][0]-grid[i][special_row][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[top_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[-1][special_row][0]-grid[top_route[0]][special_row][0]+escape_extent, 
                                                post_rotation=0, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[top_route[0]][special_row] = np.array(hinged_path[-1])
        
        top_split = [top_triangle[top_triangle[:, 0] == value] for value in np.unique(top_triangle[:, 0])]
        available_length = effective_pitch_x - 3 * trace_width
        if array_size_x % 2 == 0:
            special_column = array_size_x - int(array_size_x/2)
        else:
            special_column = array_size_x - int(array_size_x/2) - 1
        for split in top_split:
            cnt = 0
            split = split[np.flip(np.argsort(split[:, 1]))]
            for i in range(len(split)):
                if split[i][1] == array_size_y-1:
                    a, b = split[i]
                    path_points = [tuple(grid[a][b]), (grid[a][b][0], grid[a][b][1]+escape_extent)]
                    self.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)
                    ports[a][b] = np.array(path_points[-1])
                # Special case for only one trace in a column to route out
                elif split[i][1] == array_size_y-2 and len(split) == 2:
                    assert round(3*trace_width, 3) <= effective_pitch_x, f"Not enough space for 1 trace with trace width {trace_width} and effective pitch {effective_pitch_x}."
                    a, b = split[i]
                    if a > special_column:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[a][-1][1]-grid[a][b][1]+escape_extent, post_rotation=-90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                    elif a < array_size_x - int(array_size_x/2) - 1:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[a][-1][1]-grid[a][b][1]+escape_extent, post_rotation=90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                # General case for multiple traces in a column to route out
                else:
                    a, b = split[i]
                    if a > special_column:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][-1][1]-grid[a][b][1]+escape_extent, post_rotation=-90, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
                    elif a < array_size_x - int(array_size_x/2) - 1:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][-1][1]-grid[a][b][1]+escape_extent, post_rotation=90, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
        
        # Handle the special columns for even x array sizes
        if array_size_x % 2 == 0:
            # Get the split where the first element is the special column
            special_split = top_triangle[top_triangle[:, 0] == special_column]
            left_route = -np.arange(-(array_size_y-2), -special_split[:, 1].min()+1, 2)
            if special_split[:, 1].min() not in left_route and special_split[:, 1].min() != array_size_y-1:
                left_route = np.append(left_route, special_split[:, 1].min())
            left_route = np.flip(np.sort(left_route))

            remaining_inds_L = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_y-2), -special_split[:, 1].min()+1)), left_route))
            num_traces = len(left_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in left_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][i][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, left_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][left_route[0]][1]+escape_extent, 
                                                post_rotation=-90, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][left_route[0]] = np.array(hinged_path[-1])

            special_split = top_triangle[top_triangle[:, 0] == special_column-1]
            right_route = -np.arange(-(array_size_y-2), -special_split[:, 1].min()+1, 2)
            if special_split[:, 1].min() not in right_route and special_split[:, 1].min() != array_size_y-1:
                right_route = np.append(right_route, special_split[:, 1].min())
            right_route = np.flip(np.sort(right_route))

            remaining_inds_R = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_y-2), -special_split[:, 1].min()+1)), right_route))
            num_traces = len(right_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in right_route:
                    hinged_path = create_hinged_path(grid[special_column-1, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column-1][-1][1]-grid[special_column-1][i][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column-1][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column-1, right_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column-1][-1][1]-grid[special_column-1][right_route[0]][1]+escape_extent, 
                                                post_rotation=90, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column-1][right_route[0]] = np.array(hinged_path[-1])

            num_traces = len(remaining_inds_L) + len(remaining_inds_R)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in remaining_inds_L:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][i][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
                cnt = 0
                for i in remaining_inds_R:
                    hinged_path = create_hinged_path(grid[special_column-1, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column-1][-1][1]-grid[special_column-1][i][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column-1][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                for i in remaining_inds_L:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][i][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                for i in remaining_inds_R:
                    hinged_path = create_hinged_path(grid[special_column-1, i], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column-1][-1][1]-grid[special_column-1][i][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column-1][i] = np.array(hinged_path[-1])
        
        # Handle the special columns for odd x array sizes
        else:
            special_split = top_triangle[top_triangle[:, 0] == special_column]
            left_route = -np.arange(-(array_size_y-2), -special_split[:, 1].min()+1, 2)
            right_route = np.flip(np.setdiff1d(np.flip(-np.arange(-(array_size_y-2), -special_split[:, 1].min()+1)), left_route))

            num_traces = len(left_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in left_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][i][1]+escape_extent, 
                                                    post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, left_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][left_route[0]][1]+escape_extent, 
                                                post_rotation=-90, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][left_route[0]] = np.array(hinged_path[-1])

            num_traces = len(right_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_x, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_x}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in right_route:
                    hinged_path = create_hinged_path(grid[special_column, i], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][i][1]+escape_extent, 
                                                    post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[special_column][i] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[special_column, right_route[0]], routing_angle, effective_pitch_x/2 + pad_diameter/2, grid[special_column][-1][1]-grid[special_column][right_route[0]][1]+escape_extent, 
                                                post_rotation=90, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[special_column][right_route[0]] = np.array(hinged_path[-1])

        left_split = [left_triangle[left_triangle[:, 1] == value] for value in np.unique(left_triangle[:, 1])]
        available_length = effective_pitch_y - 3 * trace_width
        if array_size_y % 2 == 0:
            special_row = array_size_y - int(array_size_y/2)
        else:
            special_row = array_size_y - int(array_size_y/2) - 1
        for split in left_split:
            cnt = 0
            split = split[np.argsort(split[:, 0])]
            for i in range(len(split)):
                if split[i][0] == 0:
                    a, b = split[i]
                    path_points = [tuple(grid[a][b]), (grid[a][b][0]-escape_extent, grid[a][b][1])]
                    self.add_path_as_polygon(trace_cell_name, path_points, trace_width, layer_name)
                    ports[a][b] = np.array(path_points[-1])
                # Special case for only one trace in a column to route out
                elif split[i][0] == 1 and len(split) == 2:
                    assert round(3*trace_width, 3) <= effective_pitch_y, f"Not enough space for 1 trace with trace width {trace_width} and effective pitch {effective_pitch_y}."
                    a, b = split[i]
                    if b > special_row:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[a][b][0]-grid[0][b][0]+escape_extent, post_rotation=0, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                    elif b < array_size_y - int(array_size_y/2) - 1:
                        hinged_path = create_hinged_path(grid[a,b], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[a][b][0]-grid[0][b][0]+escape_extent, post_rotation=180, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                # General case for multiple traces in a column to route out
                else:
                    a, b = split[i]
                    if b > special_row:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][b][0]-grid[0][b][0]+escape_extent, post_rotation=0, post_reflection=True)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
                    elif b < array_size_y - int(array_size_y/2) - 1:
                        num_traces = len(split)-1
                        assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
                        spacing = available_length / (num_traces - 1)
                        hinged_path = create_hinged_path(grid[a, b], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[a][b][0]-grid[0][b][0]+escape_extent, post_rotation=180, post_reflection=False)
                        self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                        ports[a][b] = np.array(hinged_path[-1])
                        cnt += 1
        
        # Handle the special rows for even y array sizes
        if array_size_y % 2 == 0:
            # Get the split where the first element is the special row
            special_split = left_triangle[left_triangle[:, 1] == special_row]
            bottom_route = np.arange(1, special_split[:, 0].max(), 2)
            if special_split[:, 0].max() not in bottom_route and special_split[:, 0].max() != 0:
                bottom_route = np.append(bottom_route, special_split[:, 0].max())
            bottom_route = np.sort(bottom_route)

            remaining_inds_B = np.setdiff1d(np.arange(1, special_split[:, 0].max()+1), bottom_route)
            num_traces = len(bottom_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in bottom_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[bottom_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[bottom_route[0]][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                post_rotation=0, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[bottom_route[0]][special_row] = np.array(hinged_path[-1])
            
            special_split = left_triangle[left_triangle[:, 1] == special_row-1]
            top_route = np.arange(1, special_split[:, 0].max(), 2)
            if special_split[:, 0].max() not in top_route and special_split[:, 0].max() != 0:
                top_route = np.append(top_route, special_split[:, 0].max())
            top_route = np.sort(top_route)

            remaining_inds_T = np.setdiff1d(np.arange(1, special_split[:, 0].max()+1), top_route)
            num_traces = len(top_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in top_route:
                    hinged_path = create_hinged_path(grid[i, special_row-1], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row-1][0]-grid[0][special_row-1][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row-1] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[top_route[0], special_row-1], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[top_route[0]][special_row-1][0]-grid[0][special_row-1][0]+escape_extent, 
                                                post_rotation=180, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[top_route[0]][special_row-1] = np.array(hinged_path[-1])
            
            num_traces = len(remaining_inds_B) + len(remaining_inds_T)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in remaining_inds_B:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
                cnt = 0
                for i in remaining_inds_T:
                    hinged_path = create_hinged_path(grid[i, special_row-1], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row-1][0]-grid[0][special_row-1][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row-1] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                for i in remaining_inds_B:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[i][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                for i in remaining_inds_T:
                    hinged_path = create_hinged_path(grid[i, special_row-1], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[i][special_row-1][0]-grid[0][special_row-1][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row-1] = np.array(hinged_path[-1])
        
        # Handle the special rows for odd y array sizes
        else:
            special_split = left_triangle[left_triangle[:, 1] == special_row]
            bottom_route = np.arange(1, special_split[:, 0].max()+1, 2)
            top_route = np.setdiff1d(np.arange(1, special_split[:, 0].max()+1), bottom_route)

            num_traces = len(bottom_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in bottom_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                    post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[bottom_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[bottom_route[0]][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                post_rotation=0, post_reflection=True)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[bottom_route[0]][special_row] = np.array(hinged_path[-1])
            
            num_traces = len(top_route)
            assert round((2*num_traces+1)*trace_width, 3) <= effective_pitch_y, f"Not enough space for {num_traces} traces with trace width {trace_width} and effective pitch {effective_pitch_y}."
            if num_traces > 1:
                spacing = available_length / (num_traces - 1)
                cnt = 0
                for i in top_route:
                    hinged_path = create_hinged_path(grid[i, special_row], routing_angle, cnt*spacing + 3*trace_width/2 + pad_diameter/2, grid[i][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                    post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                    ports[i][special_row] = np.array(hinged_path[-1])
                    cnt += 1
            elif num_traces == 1:
                hinged_path = create_hinged_path(grid[top_route[0], special_row], routing_angle, effective_pitch_y/2 + pad_diameter/2, grid[top_route[0]][special_row][0]-grid[0][special_row][0]+escape_extent, 
                                                post_rotation=180, post_reflection=False)
                self.add_path_as_polygon(trace_cell_name, hinged_path, trace_width, layer_name)
                ports[top_route[0]][special_row] = np.array(hinged_path[-1])
        
        return np.around(grid.reshape(array_size_x*array_size_y, 2), 3), np.around(ports.reshape(array_size_x*array_size_y, 2), 3), orientations.reshape(array_size_x*array_size_y)

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
    
    def calculate_area_for_layer(self, layer_name):
        """
        Calculate the total area of all polygons on a specified layer in the top cell.
        Returns the total area in mm^2.

        Args:
        - layer_name (str): Name of the layer to calculate the area for.
        """
        cell = self.check_cell_exists(self.top_cell_names[0])
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
        
        # Calculate the total area of the merged polygons
        area = 0
        for poly in merged_polygons:
            area += poly.area
        
        return area/1e6  # Convert from um^2 to mm^2

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

    def determine_available_space(self, substrate_layer_name, excluded_layers):
        """
        Determine the available space in the design based on the substrate layer.

        Args:
        - substrate_layer_name (str): The name of the substrate layer.

        Returns:
        - available_space (shapely.geometry.MultiPolygon): The available space as a MultiPolygon.
        """
        substrate_layer_number = self.get_layer_number(substrate_layer_name)
        substrate_polygons = []
        all_other_polygons = []

        # Get polygons from the substrate layer in top cells
        for top_cell_name in self.top_cell_names:
            cell = self.check_cell_exists(top_cell_name)
            polygons_by_spec = cell.get_polygons(by_spec=True)
            for (lay, dat), polys in polygons_by_spec.items():
                if lay == substrate_layer_number:
                    substrate_polygons.extend([Polygon(poly) for poly in polys])
                elif lay not in excluded_layers:
                    all_other_polygons.extend([Polygon(poly) for poly in polys])
        
        if not substrate_polygons:
            raise ValueError(f"No polygons found in the substrate layer '{substrate_layer_name}'.")

        # Convert lists of polygons to GeoDataFrames
        substrate_gdf = gpd.GeoDataFrame(geometry=substrate_polygons)
        all_other_gdf = gpd.GeoDataFrame(geometry=all_other_polygons)

        # Perform dissolve (union) operation
        substrate_union = substrate_gdf.dissolve().geometry[0]
        all_other_union = all_other_gdf.dissolve().geometry[0]

        # Subtract the occupied space from the substrate
        available_space = substrate_union.difference(all_other_union)

        return (available_space if isinstance(available_space, MultiPolygon) else MultiPolygon([available_space]), [geom for geom in all_other_polygons])

    def update_available_space(self, substrate_layer_name, old_available_space, all_other_polygons_unprepared, excluded_layers):
        """
        Update the available space after adding new features to the design.

        Args:
        - old_available_space (shapely.geometry.MultiPolygon): The original available space.
        
        Returns:
        - updated_available_space (shapely.geometry.MultiPolygon): The updated available space.
        """
        substrate_layer_number = self.get_layer_number(substrate_layer_name)
        all_other_polygons_index = STRtree(all_other_polygons_unprepared)

        new_polygons = []

        # Get polygons from all layers in top cells
        for top_cell_name in self.top_cell_names:
            cell = self.check_cell_exists(top_cell_name)
            polygons_by_spec = cell.get_polygons(by_spec=True)
            for (lay, dat), polys in polygons_by_spec.items():
                if lay != substrate_layer_number and lay not in excluded_layers:
                    for poly in polys:
                        polygon = Polygon(poly)
                        if not polygon.is_valid:
                            polygon = polygon.buffer(0)  # Attempt to fix invalid geometry
                        if polygon.is_valid:
                            # Use the STRtree index to find possible containing polygons
                            idx = all_other_polygons_index.query(polygon)
                            if any([all_other_polygons_unprepared[i].contains(polygon) or all_other_polygons_unprepared[i].equals(polygon) for i in idx]):
                                continue    
                            new_polygons.append(polygon)
                        else:
                            raise ValueError(f"Invalid geometry found in cell '{top_cell_name}' on layer '{lay}'.")
        
        if len(new_polygons) == 0:
            return old_available_space, all_other_polygons_unprepared

        new_other_gdf = gpd.GeoDataFrame(geometry=new_polygons)
        new_other_union = new_other_gdf.dissolve().geometry[0]
        updated_available_space = old_available_space.difference(new_other_union)

        return (updated_available_space if isinstance(updated_available_space, MultiPolygon) else MultiPolygon([updated_available_space]), all_other_polygons_unprepared + [geom for geom in new_polygons])
    
    def find_position_for_rectangle(self, available_space, width, height, offset, step_size=500, buffer=250):
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

        polygons = [prep(geom) for geom in available_space.geoms if geom.is_valid]
        polygons_orig = [geom for geom in available_space.geoms if geom.is_valid]

        for idx, polygon in enumerate(polygons):
            minx, miny, maxx, maxy = polygons_orig[idx].bounds
            x_positions = np.arange(minx, maxx, step_size)
            y_positions = np.arange(miny, maxy, step_size)

            # Generate meshgrid of points
            x_grid, y_grid = np.meshgrid(x_positions, y_positions)
            x_grid = np.round(x_grid.flatten()).astype(float)
            y_grid = np.round(y_grid.flatten()).astype(float)

            # Calculate distances from the origin
            distances = np.hypot(x_grid, y_grid)

            # Combine x, y, and distances for sorting
            points = np.unique(np.vstack((x_grid, y_grid, distances)).T, axis=0)

            # Sort points by distance
            points = points[np.argsort(points[:, 2])]

            for point in points:
                x, y = point[0], point[1]
                # Check if the rectangle would exceed the bounds: if so, skip this point
                if x + offset[0] - width / 2 < minx or x + offset[0] + width / 2 > maxx or y + offset[1] - height / 2 < miny or y + offset[1] + height / 2 > maxy:
                    continue
                print(f"Checking position ({x}, {y})")
                translated_rectangle = translate(rectangle, xoff=x + offset[0], yoff=y + offset[1])

                if polygon.contains(translated_rectangle):
                    print(f"Rectangle fits at ({x}, {y})")
                    return (x, y)
                print("Rectangle does not fit.")

        raise ValueError("No available space found.")
    
    def cable_tie_ports(self, cell_name, layer_name, ports_, orientations, trace_width, routing_angle=45, escape_extent=250):
        # TODO: escape extent is hardcoded but may not be large enough for all cases
        ports = deepcopy(ports_)
        assert np.all(orientations == orientations[0])
        assert isinstance(trace_width, (int, float))

        if orientations[0] == 90:
            ports = ports[np.argsort(ports[:, 0])]
            center_ind = math.ceil(len(ports)/2)-1

            iter_inds_L = np.flip(np.arange(center_ind+1))
            iter_inds_R = np.arange(center_ind+1, len(ports))
            max_y_L = (ports[center_ind][0] - 2*(len(iter_inds_L)-1)*trace_width - ports[iter_inds_L[-1]][0]) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_y_R = (ports[iter_inds_R[-1]][0] - (ports[center_ind][0] + 2*len(iter_inds_R)*trace_width)) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_y = max(max_y_L, max_y_R)

            wire_ports = []
            for i in range(len(iter_inds_L)):
                wire_ports.append((ports[center_ind][0]-2*i*trace_width, ports[:, 1].max()+max_y))
            for i in range(len(iter_inds_R)):
                wire_ports.append((ports[center_ind][0]+2*(i+1)*trace_width, ports[:, 1].max()+max_y))
            wire_ports = np.array(wire_ports)
            wire_ports = wire_ports[np.argsort(wire_ports[:, 0])]
            wire_orientations = np.full(len(wire_ports), 90)

            y_accumulated = 0
            for i, idx in enumerate(iter_inds_L):
                if i > 1:
                    p = ports[iter_inds_L[i-1]][0] - ports[iter_inds_L[i]][0]
                    y_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]+y_accumulated)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0], ports[idx][1]+y_accumulated), 
                                                    routing_angle, ports[center_ind][0]-2*i*trace_width-ports[idx][0], max_y-y_accumulated, post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0], ports[idx][1]+y_accumulated), trace_width/2, layer_name)
                elif i == 1:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[center_ind][0]-2*i*trace_width-ports[idx][0], max_y, post_rotation=-90, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)

                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]+max_y)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)
            
            y_accumulated = 0
            for i, idx in enumerate(iter_inds_R):
                if i == 0:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[idx][0]-(ports[center_ind][0]+2*(i+1)*trace_width), max_y, post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    p = ports[iter_inds_R[i]][0] - ports[iter_inds_R[i]-1][0]
                    y_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]+y_accumulated)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0], ports[idx][1]+y_accumulated), 
                                                        routing_angle, ports[idx][0]-(ports[center_ind][0]+2*(i+1)*trace_width), max_y-y_accumulated, post_rotation=90, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0], ports[idx][1]+y_accumulated), trace_width/2, layer_name)
        
        elif orientations[0] == 270:
            ports = ports[np.argsort(ports[:, 0])]
            center_ind = math.ceil(len(ports)/2)-1

            iter_inds_L = np.flip(np.arange(center_ind+1))
            iter_inds_R = np.arange(center_ind+1, len(ports))
            max_y_L = (ports[center_ind][0] - 2*(len(iter_inds_L)-1)*trace_width - ports[iter_inds_L[-1]][0]) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_y_R = (ports[iter_inds_R[-1]][0] - (ports[center_ind][0] + 2*len(iter_inds_R)*trace_width)) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_y = max(max_y_L, max_y_R)

            wire_ports = []
            for i in range(len(iter_inds_L)):
                wire_ports.append((ports[center_ind][0]-2*i*trace_width, ports[:, 1].min()-max_y))
            for i in range(len(iter_inds_R)):
                wire_ports.append((ports[center_ind][0]+2*(i+1)*trace_width, ports[:, 1].min()-max_y))
            wire_ports = np.array(wire_ports)
            wire_ports = wire_ports[np.argsort(wire_ports[:, 0])]
            wire_orientations = np.full(len(wire_ports), 270)

            y_accumulated = 0
            for i, idx in enumerate(iter_inds_L):
                if i > 1:
                    p = ports[iter_inds_L[i-1]][0] - ports[iter_inds_L[i]][0]
                    y_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]-y_accumulated)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0], ports[idx][1]-y_accumulated), 
                                                    routing_angle, ports[center_ind][0]-2*i*trace_width-ports[idx][0], max_y-y_accumulated, post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0], ports[idx][1]-y_accumulated), trace_width/2, layer_name)
                elif i == 1:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[center_ind][0]-2*i*trace_width-ports[idx][0], max_y, post_rotation=-90, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)

                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]-max_y)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)
                        
            y_accumulated = 0
            for i, idx in enumerate(iter_inds_R):
                if i == 0:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[idx][0]-(ports[center_ind][0]+2*(i+1)*trace_width), max_y, post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    p = ports[iter_inds_R[i]][0] - ports[iter_inds_R[i]-1][0]
                    y_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0], ports[idx][1]-y_accumulated)]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0], ports[idx][1]-y_accumulated), 
                                                        routing_angle, ports[idx][0]-(ports[center_ind][0]+2*(i+1)*trace_width), max_y-y_accumulated, post_rotation=90, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0], ports[idx][1]-y_accumulated), trace_width/2, layer_name)
        
        elif orientations[0] == 0:
            ports = ports[np.argsort(ports[:, 1])]
            center_ind = math.ceil(len(ports)/2)-1

            iter_inds_B = np.flip(np.arange(center_ind+1))
            iter_inds_T = np.arange(center_ind+1, len(ports))
            max_x_B = (ports[center_ind][1] - 2*(len(iter_inds_B)-1)*trace_width - ports[iter_inds_B[-1]][1]) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_x_T = (ports[iter_inds_T[-1]][1] - (ports[center_ind][1] + 2*len(iter_inds_T)*trace_width)) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_x = max(max_x_B, max_x_T)

            wire_ports = []
            for i in range(len(iter_inds_B)):
                wire_ports.append((ports[:, 0].max()+max_x, ports[center_ind][1]-2*i*trace_width))
            for i in range(len(iter_inds_T)):
                wire_ports.append((ports[:, 0].max()+max_x, ports[center_ind][1]+2*(i+1)*trace_width))
            wire_ports = np.array(wire_ports)
            wire_ports = wire_ports[np.argsort(wire_ports[:, 1])]
            wire_orientations = np.full(len(wire_ports), 0)

            x_accumulated = 0
            for i, idx in enumerate(iter_inds_B):
                if i > 1:
                    p = ports[iter_inds_B[i-1]][1] - ports[iter_inds_B[i]][1]
                    x_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0]+x_accumulated, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0]+x_accumulated, ports[idx][1]), 
                                                    routing_angle, ports[center_ind][1]-2*i*trace_width-ports[idx][1], max_x-x_accumulated, post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0]+x_accumulated, ports[idx][1]), trace_width/2, layer_name)
                elif i == 1:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[center_ind][1]-2*i*trace_width-ports[idx][1], max_x, post_rotation=0, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)

                    path_points = [ports[idx], (ports[idx][0]+max_x, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

            x_accumulated = 0
            for i, idx in enumerate(iter_inds_T):
                if i == 0:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[idx][1]-(ports[center_ind][1]+2*(i+1)*trace_width), max_x, post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    p = ports[iter_inds_T[i]][1] - ports[iter_inds_T[i]-1][1]
                    x_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0]+x_accumulated, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0]+x_accumulated, ports[idx][1]), 
                                                        routing_angle, ports[idx][1]-(ports[center_ind][1]+2*(i+1)*trace_width), max_x-x_accumulated, post_rotation=180, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0]+x_accumulated, ports[idx][1]), trace_width/2, layer_name)
        
        elif orientations[0] == 180:
            ports = ports[np.argsort(ports[:, 1])]
            center_ind = math.ceil(len(ports)/2)-1

            iter_inds_B = np.flip(np.arange(center_ind+1))
            iter_inds_T = np.arange(center_ind+1, len(ports))
            max_x_B = (ports[center_ind][1] - 2*(len(iter_inds_B)-1)*trace_width - ports[iter_inds_B[-1]][1]) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_x_T = (ports[iter_inds_T[-1]][1] - (ports[center_ind][1] + 2*len(iter_inds_T)*trace_width)) * np.tan(routing_angle*np.pi/180) + escape_extent
            max_x = max(max_x_B, max_x_T)

            wire_ports = []
            for i in range(len(iter_inds_B)):
                wire_ports.append((ports[:, 0].min()-max_x, ports[center_ind][1]-2*i*trace_width))
            for i in range(len(iter_inds_T)):
                wire_ports.append((ports[:, 0].min()-max_x, ports[center_ind][1]+2*(i+1)*trace_width))
            wire_ports = np.array(wire_ports)
            wire_ports = wire_ports[np.argsort(wire_ports[:, 1])]
            wire_orientations = np.full(len(wire_ports), 180)

            x_accumulated = 0
            for i, idx in enumerate(iter_inds_B):
                if i > 1:
                    p = ports[iter_inds_B[i-1]][1] - ports[iter_inds_B[i]][1]
                    x_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0]-x_accumulated, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0]-x_accumulated, ports[idx][1]), 
                                                    routing_angle, ports[center_ind][1]-2*i*trace_width-ports[idx][1], max_x-x_accumulated, post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0]-x_accumulated, ports[idx][1]), trace_width/2, layer_name)
                elif i == 1:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[center_ind][1]-2*i*trace_width-ports[idx][1], max_x, post_rotation=0, post_reflection=True)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)
                    
                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)

                    path_points = [ports[idx], (ports[idx][0]-max_x, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

            x_accumulated = 0
            for i, idx in enumerate(iter_inds_T):
                if i == 0:
                    hinged_path = create_hinged_path(ports[idx], routing_angle, ports[idx][1]-(ports[center_ind][1]+2*(i+1)*trace_width), max_x, post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, ports[idx], trace_width/2, layer_name)
                else:
                    p = ports[iter_inds_T[i]][1] - ports[iter_inds_T[i]-1][1]
                    x_accumulated += math.ceil(max(0, 2*trace_width/np.sin(routing_angle*np.pi/180) - p/np.tan(routing_angle*np.pi/180)))
                    path_points = [ports[idx], (ports[idx][0]-x_accumulated, ports[idx][1])]
                    self.add_path_as_polygon(cell_name, path_points, trace_width, layer_name)

                    hinged_path = create_hinged_path((ports[idx][0]-x_accumulated, ports[idx][1]), 
                                                        routing_angle, ports[idx][1]-(ports[center_ind][1]+2*(i+1)*trace_width), max_x-x_accumulated, post_rotation=180, post_reflection=False)
                    self.add_path_as_polygon(cell_name, hinged_path, trace_width, layer_name)

                    self.add_circle_as_polygon(cell_name, (ports[idx][0]-x_accumulated, ports[idx][1]), trace_width/2, layer_name)

        return wire_ports, wire_orientations

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

def create_hinged_path(start_point, angle, extension_y, extension_x, post_rotation=0, post_reflection=False):
    x0, y0 = (0, 0)
    angle_radians = angle * np.pi / 180
    post_rotation = post_rotation * np.pi / 180
    
    # If the angle is directly horizontal or the start y is already at level_y, adjust behavior
    if angle > 90:
        # Directly horizontal or already at level_y
        raise ValueError('Improper Usage')
    
    # Calculate x where the path should level off
    # y = y0 + (x - x0) * tan(angle) --> x = x0 + (level_y - y0) / tan(angle)
    # Avoid division by zero if angle is 90 or 270 degrees
    if angle == 90:
        hinge_x = x0  # Vertical line case
    else:
        hinge_x = extension_y / np.tan(angle_radians)

    assert extension_x >= hinge_x, "Improper Usage: extension_x must be greater than hinge_x"
    
    hinge_point = (hinge_x, extension_y)
    
    # Points from start to hinge
    path_points = [(x0, y0), hinge_point]

    # Continue horizontally from hinge point
    path_points.append((extension_x, extension_y))  # Extend horizontally for some length
    path_points = np.array(path_points)

    if post_reflection:
        path_points[:, 0] = -path_points[:, 0]

    rotation_matrix = np.array([
        [np.cos(post_rotation), -np.sin(post_rotation)],
        [np.sin(post_rotation), np.cos(post_rotation)]
    ])
    path_points = rotation_matrix.dot(path_points.T).T

    path_points[:, 0] += start_point[0]
    path_points[:, 1] += start_point[1]
    
    return path_points

def route_port_to_port(filename, cell_name, ports1_, orientations1_, ports2_, orientations2_, trace_width, layer_number,
                       bbox1_, bbox2_, top_cell_name="TopCell"):
    orientations1 = deepcopy(orientations1_)
    orientations2 = deepcopy(orientations2_)
    assert len(ports1_) == len(ports2_)
    assert np.all(orientations1 == orientations1[0])
    assert np.all(orientations2 == orientations2[0])
    assert isinstance(trace_width, (int, float))
    assert isinstance(layer_number, int)
    ports1 = deepcopy(ports1_)
    ports2 = deepcopy(ports2_)
    bbox1 = deepcopy(bbox1_)
    bbox2 = deepcopy(bbox2_)

    D = pg.import_gds(filename, cellname=cell_name)
    # Works, covers most cases
    cnt = 0
    if (orientations1[0] == 180 and orientations2[0] == 270) or (orientations1[0] == 270 and orientations2[0] == 180):
        if orientations1[0] == 270:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        if bbox1[1][1] < bbox2[0][1] - (2*len(ports1)+1) * trace_width:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.argsort(ports2[:, 0])]

            if ports1[:, 0].min() > ports2[:, 0].max():
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                    cnt += 1
            else:
                left_inds = np.where(ports1[:, 0] - ports2[:, 0] >= 0)[0]
                if len(left_inds) > 0:
                    left_ind_boundary = max_value_before_jump(left_inds)
                    left_inds = np.arange(left_ind_boundary+1)
                right_inds = np.setdiff1d(np.arange(len(ports1)), left_inds)
                right_inds = right_inds[np.flip(np.argsort(ports1[right_inds][:, 1]))]

                additional_y = (2*len(left_inds)+1) * trace_width
                xmin = np.inf
                for i, idx in enumerate(right_inds):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]-2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[-1-i][0], ports2[-1-i][1]-2*(len(right_inds)-i)*trace_width-additional_y), width=trace_width, orientation=orientations2[0])

                    route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                    D.add_ref(route_path)
                    if route_path.xmin < xmin:
                        xmin = route_path.xmin

                    P = Path([ports1[idx], port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[-1-i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
                
                current_x_shift = 2*cnt*trace_width
                current_y_shift = 2*(len(right_inds)-cnt)*trace_width+additional_y

                if len(left_inds) > 0:
                    remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] > xmin)[0]]
                    while True:
                        covered_len = len(remaining_inds_right)
                        remaining_inds_right = np.flip(left_inds[np.where(ports2[left_inds, 0] > xmin - (2*len(remaining_inds_right)+1)*trace_width - trace_width/2)[0]])
                        if len(remaining_inds_right) == covered_len:
                            break

                    left_inds = np.setdiff1d(left_inds, remaining_inds_right)

                    for i, idx in enumerate(remaining_inds_right):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]-2*i*trace_width-current_x_shift, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[-1-i-len(right_inds)][0], ports2[-1-i-len(right_inds)][1]-current_y_shift+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                        route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                        D.add_ref(route_path)

                        P = Path([ports1[idx], port1.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)

                        P = Path([ports2[-1-i-len(right_inds)], port2.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)
                        cnt += 1

                    for i, idx in enumerate(left_inds):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                        D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                        cnt += 1
        else:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.argsort(ports2[:, 0])]
            additional_y = max(0, bbox2[0][1] - bbox1[0][1] + 3*trace_width/2)

            if ports1[:, 0].max() < bbox2[0][0] - 3*trace_width/2:
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width-additional_y), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

            elif ports1[:, 0].min() > bbox2[1][0] + (2*len(ports1)+1)*trace_width:
                ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
                ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
                additional_x = (2*len(ports1)+1) * trace_width
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-additional_x+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
            
            else:
                additional_x = bbox1[0][0] - bbox2[0][0] + 3*trace_width/2
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-additional_x-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

    # Kind of works: requires that ports2 is above ports1 in y
    elif (orientations1[0] == 90 and orientations2[0] == 270) or (orientations1[0] == 270 and orientations2[0] == 90):
        if orientations1[0] == 270:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        assert bbox2[0][1] > bbox1[1][1] + (2*len(ports1)+1) * trace_width, "No space for routing"
        ports1 = ports1[np.argsort(ports1[:, 0])]
        ports2 = ports2[np.argsort(ports2[:, 0])]

        if ports1[:, 0].min() > ports2[:, 0].max():
            for i, port in enumerate(ports1):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]+2*i*trace_width), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([port, port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1

        elif ports1[:, 0].max() < ports2[:, 0].min():
            ports1 = ports1[np.flip(np.argsort(ports1[:, 0]))]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
            for i, port in enumerate(ports1):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]+2*i*trace_width), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([port, port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1
        
        else:
            left_inds = np.where(ports1[:, 0] >= ports2[:, 0])[0]
            if len(left_inds) > 0:
                left_ind_boundary = max_value_before_jump(left_inds)
                left_inds = np.arange(left_ind_boundary+1)
            right_inds = np.flip(np.setdiff1d(np.arange(len(ports1)), left_inds))
            additional_y = 0
            for i, idx in enumerate(left_inds):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]+additional_y), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([ports1[idx], port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1
                additional_y += 2*trace_width
            
            additional_y = 0
            for i, idx in enumerate(right_inds):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]+additional_y), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[-1-i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([ports1[idx], port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1
                additional_y += 2*trace_width

    # Works, covers most cases
    elif (orientations1[0] == 0 and orientations2[0] == 270) or (orientations1[0] == 270 and orientations2[0] == 0):
        if orientations1[0] == 270:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        if bbox1[1][1] < bbox2[0][1] - (2*len(ports1)+1) * trace_width:
            ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
            ports2 = ports2[np.argsort(ports2[:, 0])]

            if ports1[:, 0].max() < ports2[:, 0].min():
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                    cnt += 1
            else:
                left_inds = np.where(ports2[:, 0] - ports1[:, 0] >= 0)[0]
                if len(left_inds) > 0:
                    left_inds = np.arange(left_inds.min(), len(ports1))
                right_inds = np.setdiff1d(np.arange(len(ports1)), left_inds)

                additional_y = (2*len(left_inds)+1) * trace_width
                xmax = -np.inf
                for i, idx in enumerate(right_inds):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*(len(right_inds)-i)*trace_width-additional_y), width=trace_width, orientation=orientations2[0])

                    route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                    D.add_ref(route_path)
                    if route_path.xmax > xmax:
                        xmax = route_path.xmax

                    P = Path([ports1[idx], port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
                
                current_x_shift = 2*cnt*trace_width
                current_y_shift = 2*(len(right_inds)-cnt)*trace_width+additional_y

                if len(left_inds) > 0:
                    remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] < xmax)[0]]
                    while True:
                        covered_len = len(remaining_inds_right)
                        remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] < xmax + (2*len(remaining_inds_right)+1)*trace_width + trace_width/2)[0]]
                        if len(remaining_inds_right) == covered_len:
                            break

                    left_inds = np.flip(np.setdiff1d(left_inds, remaining_inds_right))

                    remaining_inds_right = remaining_inds_right
                    for i, idx in enumerate(remaining_inds_right):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width+current_x_shift, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i+len(right_inds)][0], ports2[i+len(right_inds)][1]-current_y_shift+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                        route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                        D.add_ref(route_path)

                        P = Path([ports1[idx], port1.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)

                        P = Path([ports2[i+len(right_inds)], port2.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)
                        cnt += 1

                    for i, idx in enumerate(left_inds):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[-1-i], width=trace_width, orientation=orientations2[0])

                        D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                        cnt += 1
        else:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
            additional_y = max(0, bbox2[0][1] - bbox1[0][1] + 3*trace_width/2)

            if ports1[:, 0].min() > bbox2[1][0] + 3*trace_width/2:
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width-additional_y), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

            elif ports1[:, 0].max() < bbox2[0][0] - (2*len(ports1)+1)*trace_width:
                ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
                ports2 = ports2[np.argsort(ports2[:, 0])]
                additional_x = (2*len(ports1)+1) * trace_width
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+additional_x-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
            
            else:
                additional_x = bbox2[1][0] - bbox1[1][0] + 3*trace_width/2
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+additional_x+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
    
    # Works, covers most cases
    elif (orientations1[0] == 180 and orientations2[0] == 90) or (orientations1[0] == 90 and orientations2[0] == 180):
        if orientations1[0] == 90:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        if bbox1[0][1] > bbox2[1][1] + (2*len(ports1)+1)*trace_width:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]

            if ports1[:, 0].min() > ports2[:, 0].max():
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                    cnt += 1
            else:
                left_inds = np.where(ports1[:, 0] - ports2[:, 0] >= 0)[0]
                if len(left_inds) > 0:
                    left_inds = np.arange(left_inds.min(), len(ports1))
                right_inds = np.setdiff1d(np.arange(len(ports1)), left_inds)
                right_inds = right_inds[np.argsort(ports1[right_inds][:, 1])]

                additional_y = (2*len(left_inds)+1) * trace_width
                xmin = np.inf
                for i, idx in enumerate(right_inds):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]-2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*(len(right_inds)-i)*trace_width+additional_y), width=trace_width, orientation=orientations2[0])

                    route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                    D.add_ref(route_path)
                    if route_path.xmin < xmin:
                        xmin = route_path.xmin

                    P = Path([ports1[idx], port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
                
                current_x_shift = 2*cnt*trace_width
                current_y_shift = 2*(len(right_inds)-cnt)*trace_width+additional_y

                if len(left_inds) > 0:
                    remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] > xmin)[0]]
                    while True:
                        covered_len = len(remaining_inds_right)
                        remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] > xmin - (2*len(remaining_inds_right)+1)*trace_width - trace_width/2)[0]]
                        if len(remaining_inds_right) == covered_len:
                            break

                    left_inds = np.flip(np.setdiff1d(left_inds, remaining_inds_right))

                    for i, idx in enumerate(remaining_inds_right):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]-2*i*trace_width-current_x_shift, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i+len(right_inds)][0], ports2[i+len(right_inds)][1]+current_y_shift-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                        route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                        D.add_ref(route_path)

                        P = Path([ports1[idx], port1.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)

                        P = Path([ports2[i+len(right_inds)], port2.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)
                        cnt += 1

                    for i, idx in enumerate(left_inds):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[-1-i], width=trace_width, orientation=orientations2[0])

                        D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                        cnt += 1
        else:
            ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
            ports2 = ports2[np.argsort(ports2[:, 0])]
            additional_y = max(0, bbox1[1][1] - bbox2[1][1] + 3*trace_width/2)

            if ports1[:, 0].max() < bbox2[0][0] - 3*trace_width/2:
                for i, port in enumerate(ports1):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width+additional_y), width=trace_width, orientation=orientations2[0])

                        D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                        P = Path([port, port1.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)

                        P = Path([ports2[i], port2.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)
                        cnt += 1

            elif ports1[:, 0].min() > bbox2[1][0] + (2*len(ports1)+1)*trace_width:
                ports1 = ports1[np.argsort(ports1[:, 1])]
                ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
                additional_x = (2*len(ports1)+1) * trace_width
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-additional_x+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
            
            else:
                additional_x = bbox1[0][0] - bbox2[0][0] + 3*trace_width/2
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]-additional_x-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
    
    # Works, covers most cases
    elif (orientations1[0] == 0 and orientations2[0] == 90) or (orientations1[0] == 90 and orientations2[0] == 0):
        if orientations1[0] == 90:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        if bbox1[0][1] > bbox2[1][1] + (2*len(ports1)+1)*trace_width:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.argsort(ports2[:, 0])]

            if ports1[:, 0].max() < ports2[:, 0].min():
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                    cnt += 1
            else:
                left_inds = np.where(ports2[:, 0] - ports1[:, 0] >= 0)[0]
                if len(left_inds) > 0:
                    left_inds = np.arange(left_inds.min(), len(ports1))
                right_inds = np.setdiff1d(np.arange(len(ports1)), left_inds)

                additional_y = (2*len(left_inds)+1) * trace_width
                xmax = -np.inf
                for i, idx in enumerate(right_inds):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[-i][1]+2*(len(right_inds)-i)*trace_width+additional_y), width=trace_width, orientation=orientations2[0])

                    route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                    D.add_ref(route_path)
                    if route_path.xmax > xmax:
                        xmax = route_path.xmax

                    P = Path([ports1[idx], port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1
                
                current_x_shift = 2*cnt*trace_width
                current_y_shift = 2*(len(right_inds)-cnt)*trace_width+additional_y

                if len(left_inds) > 0:
                    remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] < xmax)[0]]
                    while True:
                        covered_len = len(remaining_inds_right)
                        remaining_inds_right = left_inds[np.where(ports2[left_inds, 0] < xmax + (2*len(remaining_inds_right)+1)*trace_width + trace_width/2)[0]]
                        if len(remaining_inds_right) == covered_len:
                            break

                    left_inds = np.flip(np.setdiff1d(left_inds, remaining_inds_right))

                    for i, idx in enumerate(remaining_inds_right):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width+current_x_shift, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i+len(right_inds)][0], ports2[i+len(right_inds)][1]+current_y_shift-2*i*trace_width), width=trace_width, orientation=orientations2[0])

                        route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                        D.add_ref(route_path)

                        P = Path([ports1[idx], port1.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)

                        P = Path([ports2[i+len(right_inds)], port2.midpoint])
                        path = P.extrude(trace_width, layer=layer_number)
                        D.add_ref(path)
                        cnt += 1

                    for i, idx in enumerate(left_inds):
                        port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0], ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                        port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[-1-i], width=trace_width, orientation=orientations2[0])

                        D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))
                        cnt += 1
        else:
            ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
            additional_y = max(0, bbox1[1][1] - bbox2[1][1] + 3*trace_width/2)

            if ports1[:, 0].min() > bbox2[1][0] + 3*trace_width/2:
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width+additional_y), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

            elif ports1[:, 0].max() < bbox2[0][0] - (2*len(ports1)+1)*trace_width:
                ports1 = ports1[np.argsort(ports1[:, 1])]
                ports2 = ports2[np.argsort(ports2[:, 0])]
                additional_x = (2*len(ports1)+1) * trace_width
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+additional_x-2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

            else:
                additional_x = bbox2[1][0] - bbox1[1][0] + 3*trace_width/2
                for i, port in enumerate(ports1):
                    port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+additional_x+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                    port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width), width=trace_width, orientation=orientations2[0])

                    D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                    P = Path([port, port1.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)

                    P = Path([ports2[i], port2.midpoint])
                    path = P.extrude(trace_width, layer=layer_number)
                    D.add_ref(path)
                    cnt += 1

    # Kind of works: requires that ports1 is left of ports2 in x
    elif (orientations1[0] == 0 and orientations2[0] == 180) or (orientations1[0] == 180 and orientations2[0] == 0):
        if orientations1[0] == 180:
            ports1, ports2 = ports2, ports1
            orientations1, orientations2 = orientations2, orientations1
        assert bbox1[1][0] < bbox2[0][0] - (2*len(ports1)+1) * trace_width, "No space for routing"
        ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
        ports2 = ports2[np.flip(np.argsort(ports2[:, 1]))]

        if ports1[:, 1].max() < ports2[:, 1].min():
            for i, port in enumerate(ports1):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([port, port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1

        elif ports1[:, 1].min() > ports2[:, 1].max():
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.argsort(ports2[:, 1])]
            for i, port in enumerate(ports1):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0]+2*i*trace_width, port[1]), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=ports2[i], width=trace_width, orientation=orientations2[0])

                D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

                P = Path([port, port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)
                cnt += 1
        
        else:
            left_inds = np.where(ports1[:, 1] < ports2[:, 1])[0]
            if len(left_inds) > 0:
                left_ind_boundary = max_value_before_jump(left_inds)
                left_inds = np.arange(left_ind_boundary+1)
            right_inds = np.flip(np.setdiff1d(np.arange(len(ports1)), left_inds))

            for i, idx in enumerate(right_inds):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[-1-i][0], ports2[-1-i][1]), width=trace_width, orientation=orientations2[0])

                route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                D.add_ref(route_path)

                P = Path([ports1[idx], port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)

                cnt += 1
            
            for i, idx in enumerate(left_inds):
                port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(ports1[idx][0]+2*i*trace_width, ports1[idx][1]), width=trace_width, orientation=orientations1[0])
                port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]), width=trace_width, orientation=orientations2[0])

                route_path = pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width)
                D.add_ref(route_path)

                P = Path([ports1[idx], port1.midpoint])
                path = P.extrude(trace_width, layer=layer_number)
                D.add_ref(path)

                cnt += 1
    
    # Works in most scenarios and throws error if it won't
    elif orientations1[0] == orientations2[0] == 0:
        if ports1[:, 0].max() > ports2[:, 0].max():
            ports1, ports2 = ports2, ports1
            bbox1, bbox2 = bbox2, bbox1

        assert ports1[:, 1].max() < bbox2[0][1] - 3*trace_width/2 or ports1[:, 1].min() > bbox2[1][1] + 3*trace_width/2, "No space for routing"

        if ports1[:, 1].max() < ports2[:, 1].min():
            ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
            ports2 = ports2[np.argsort(ports2[:, 1])]
        else:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 1]))] 

        for i, port in enumerate(ports1):
            port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
            port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0]+2*i*trace_width, ports2[i][1]), width=trace_width, orientation=orientations2[0])

            D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

            P = Path([ports2[i], port2.midpoint])
            path = P.extrude(trace_width, layer=layer_number)
            D.add_ref(path)
            cnt += 1

    elif orientations1[0] == orientations2[0] == 90:
        if ports1[:, 1].max() > ports2[:, 1].max():
            ports1, ports2 = ports2, ports1
            bbox1, bbox2 = bbox2, bbox1

        assert ports1[:, 0].max() < bbox2[0][0] - 3*trace_width/2 or ports1[:, 0].min() > bbox2[1][0] + 3*trace_width/2, "No space for routing"

        if ports1[:, 0].max() < ports2[:, 0].min():
            ports1 = ports1[np.flip(np.argsort(ports1[:, 0]))]
            ports2 = ports2[np.argsort(ports2[:, 0])]
        else:
            ports1 = ports1[np.argsort(ports1[:, 0])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]

        for i, port in enumerate(ports1):
            port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
            port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]+2*i*trace_width), width=trace_width, orientation=orientations2[0])

            D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

            P = Path([ports2[i], port2.midpoint])
            path = P.extrude(trace_width, layer=layer_number)
            D.add_ref(path)
            cnt += 1
    
    elif orientations1[0] == orientations2[0] == 180:
        if ports1[:, 0].min() < ports2[:, 0].min():
            ports1, ports2 = ports2, ports1
            bbox1, bbox2 = bbox2, bbox1

        assert ports1[:, 1].max() < bbox2[0][1] - 3*trace_width/2 or ports1[:, 1].min() > bbox2[1][1] + 3*trace_width/2, "No space for routing"

        if ports1[:, 1].max() < ports2[:, 1].min():
            ports1 = ports1[np.flip(np.argsort(ports1[:, 1]))]
            ports2 = ports2[np.argsort(ports2[:, 1])]
        else:
            ports1 = ports1[np.argsort(ports1[:, 1])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 1]))]

        for i, port in enumerate(ports1):
            port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
            port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0]-2*i*trace_width, ports2[i][1]), width=trace_width, orientation=orientations2[0])

            D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

            P = Path([ports2[i], port2.midpoint])
            path = P.extrude(trace_width, layer=layer_number)
            D.add_ref(path)
            cnt += 1
    
    elif orientations1[0] == orientations2[0] == 270:
        if ports1[:, 1].min() < ports2[:, 1].min():
            ports1, ports2 = ports2, ports1
            bbox1, bbox2 = bbox2, bbox1

        assert ports1[:, 0].min() > bbox2[1][0] + 3*trace_width/2 or ports1[:, 0].max() < bbox2[0][0] - 3*trace_width/2, "No space for routing"

        if ports1[:, 0].min() > ports2[:, 0].max():
            ports1 = ports1[np.argsort(ports1[:, 0])]
            ports2 = ports2[np.flip(np.argsort(ports2[:, 0]))]
        else:
            ports1 = ports1[np.flip(np.argsort(ports1[:, 0]))]
            ports2 = ports2[np.argsort(ports2[:, 0])]

        for i, port in enumerate(ports1):
            port1 = D.add_port(name=f"Electrode {cnt}", midpoint=(port[0], port[1]), width=trace_width, orientation=orientations1[0])
            port2 = D.add_port(name=f"Pad {cnt}", midpoint=(ports2[i][0], ports2[i][1]-2*i*trace_width), width=trace_width, orientation=orientations2[0])

            D.add_ref(pr.route_smooth(port1, port2, width=trace_width, layer=layer_number, radius=trace_width))

            P = Path([ports2[i], port2.midpoint])
            path = P.extrude(trace_width, layer=layer_number)
            D.add_ref(path)
            cnt += 1
    else:
        raise ValueError("Invalid orientations for routing. Try changing orientations for ports")

    top_level_device = pg.import_gds(filename)
    if top_level_device.name != cell_name:
        for ref in top_level_device.references:
            if ref.ref_cell.name == cell_name:
                ref.ref_cell = D
        top_level_device.write_gds(filename, cellname=top_cell_name)
    else:
        D.write_gds(filename, cellname=top_cell_name)

def max_value_before_jump(arr):
    for i in range(1, len(arr)):
        if arr[i] - arr[i-1] > 1:
            return arr[i-1]
    return arr[-1]

def route_ports_a_star(filename, cell_name, ports1, orientations1, ports2, orientations2, trace_width, layer_number, 
                           bbox1, bbox2, top_cell_name="TopCell", show_animation=False):
    assert len(ports1) == len(ports2)
    assert np.all(orientations1 == orientations1[0])
    assert np.all(orientations2 == orientations2[0])
    assert isinstance(trace_width, (int, float))

    D = pg.import_gds(filename, cellname=cell_name)

    grid_spacing = (2*len(ports1)-1) * trace_width

    bbox1_grid_raw = np.array(bbox1) / grid_spacing
    bbox1_grid = np.where(bbox1_grid_raw > 0, np.ceil(bbox1_grid_raw), np.floor(bbox1_grid_raw)).astype(int)
    bbox2_grid_raw = np.array(bbox2) / grid_spacing
    bbox2_grid = np.where(bbox2_grid_raw > 0, np.ceil(bbox2_grid_raw), np.floor(bbox2_grid_raw)).astype(int)

    ports1_center = np.mean(ports1, axis=0)
    ports1_center_raw = ports1_center / grid_spacing
    ports1_center_grid = np.where(ports1_center_raw > 0, np.ceil(ports1_center_raw), np.floor(ports1_center_raw)).astype(int)
    if orientations1[0] == 0:
        ports1_center_grid[0] += 1
    elif orientations1[0] == 90:
        ports1_center_grid[1] += 1
    elif orientations1[0] == 180:
        ports1_center_grid[0] -= 1
    elif orientations1[0] == 270:
        ports1_center_grid[1] -= 1

    ports2_center = np.mean(ports2, axis=0)
    ports2_center_raw = ports2_center / grid_spacing
    ports2_center_grid = np.where(ports2_center_raw > 0, np.ceil(ports2_center_raw), np.floor(ports2_center_raw)).astype(int)
    if orientations2[0] == 0:
        ports2_center_grid[0] += 1
    elif orientations2[0] == 90:
        ports2_center_grid[1] += 1
    elif orientations2[0] == 180:
        ports2_center_grid[0] -= 1
    elif orientations2[0] == 270:
        ports2_center_grid[1] -= 1

    a_star_path = a_star.main(ports1_center_grid.tolist(), ports2_center_grid.tolist(), [bbox1_grid.tolist(), bbox2_grid.tolist()], 1,
                              show_animation=show_animation)
    if a_star_path is None:
        raise ValueError("No path found between ports")
    a_star_path = (np.array(a_star_path) * grid_spacing).astype(float)

    if orientations1[0] == 0 or orientations1[0] == 180:
        starting_y = a_star_path[0][1]
        for coord in a_star_path:
            if coord[1] == starting_y:
                coord[1] = ports1_center[1]
            else:
                break
        a_star_path = np.vstack((np.expand_dims(ports1_center, axis=0), a_star_path))
    
    elif orientations1[0] == 270 or orientations1[0] == 90:
        starting_x = a_star_path[0][0]
        for coord in a_star_path:
            if coord[0] == starting_x:
                coord[0] = ports1_center[0]
            else:
                break
        a_star_path = np.vstack((np.expand_dims(ports1_center, axis=0), a_star_path))

    if orientations2[0] == 180 or orientations2[0] == 0:
        ending_y = a_star_path[-1][1]
        for coord in a_star_path[::-1]:
            if coord[1] == ending_y:
                coord[1] = ports2_center[1]
            else:
                break
        a_star_path = np.vstack((a_star_path, np.expand_dims(ports2_center, axis=0)))
    
    elif orientations2[0] == 270 or orientations2[0] == 90:
        ending_x = a_star_path[-1][0]
        for coord in a_star_path[::-1]:
            if coord[0] == ending_x:
                coord[0] = ports2_center[0]
            else:
                break
        a_star_path = np.vstack((a_star_path, np.expand_dims(ports2_center, axis=0)))

    X = CrossSection()
    for i in range(len(ports1)):
        if len(ports1) % 2 == 0:
            multiplier = i - int(len(ports1)/2) + 0.5
        else:
            multiplier = i - int(len(ports1)/2)
        X.add(width=trace_width, offset=2*multiplier*trace_width, layer=layer_number)

    u, ind = np.unique(a_star_path, axis=0, return_index=True)
    a_star_path = u[np.argsort(ind)]

    P = Path(a_star_path)
    path = P.extrude(X)
    D.add_ref(path)

    top_level_device = pg.import_gds(filename)
    if top_level_device.name != cell_name:
        for ref in top_level_device.references:
            if ref.ref_cell.name == cell_name:
                ref.ref_cell = D
        top_level_device.write_gds(filename, cellname=top_cell_name)
    else:
        D.write_gds(filename, cellname=top_cell_name)

    return a_star_path