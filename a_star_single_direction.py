import numpy as np
import matplotlib.pyplot as plt
import math
from shapely.geometry import Polygon, Point
from shapely.prepared import prep
import random

class Node:
    """node with properties of g, h, coordinate and parent node"""

    def __init__(self, G=0, H=0, coordinate=None, parent=None):
        self.G = G
        self.H = H
        self.F = G + H
        self.parent = parent
        self.coordinate = coordinate

    def reset_f(self):
        self.F = self.G + self.H


def hcost(node_coordinate, goal):
    dx = abs(node_coordinate[0] - goal[0])
    dy = abs(node_coordinate[1] - goal[1])
    hcost = dx + dy
    return hcost


def gcost(fixed_node, update_node_coordinate):
    dx = abs(fixed_node.coordinate[0] - update_node_coordinate[0])
    dy = abs(fixed_node.coordinate[1] - update_node_coordinate[1])
    # cost is 1 for horizontal or vertical movement, sqrt(2) for diagonal
    if dx == 1 and dy == 1:
        gc = math.sqrt(2)
    else:
        gc = dx + dy
    gcost = fixed_node.G + gc  # gcost = move from start point to update_node
    return gcost


def boundary_and_obstacles(start, goal, lower_left, upper_right, user_polygons, path_width, spacing):
    """
    :param start: start coordinate
    :param goal: goal coordinate
    :param lower_left: lower left vertex coordinate of boundary
    :param upper_right: upper right vertex coordinate of boundary
    :param user_polygons: list of user-defined polygons
    :param path_width: width of the path
    :return: boundary_obstacle array, obstacle list
    """
    # Generate boundary only if lower_left and upper_right are provided
    if lower_left and upper_right:
        ay = list(range(lower_left[1], upper_right[1]))
        ax = [lower_left[0]] * len(ay)
        cy = ay
        cx = [upper_right[0]] * len(cy)
        bx = list(range(lower_left[0] + 1, upper_right[0]))
        by = [lower_left[1]] * len(bx)
        dx = [lower_left[0]] + bx + [upper_right[0]]
        dy = [upper_right[1]] * len(dx)

        # x y coordinate in certain order for boundary
        x = ax + bx + cx + dx
        y = ay + by + cy + dy
        bound = np.vstack((x, y)).T
    else:
        bound = np.array([])

    # Process user-defined polygon obstacles
    obstacle = convert_polygons_to_obstacles(user_polygons, path_width, spacing)

    # remove start and goal coordinate in obstacle list
    obstacle = [coor for coor in obstacle if coor != start and coor != goal]
    obs_array = np.array(obstacle)

    if bound.size > 0:
        bound_obs = np.vstack((bound, obs_array))
    else:
        bound_obs = obs_array
    
    return bound_obs, obstacle


def find_neighbor(node, ob, closed, initial_direction=None, initial_step=False):
    # generate neighbors in certain condition
    ob_list = ob.tolist()
    neighbor: list = []

    # Define all possible moves including diagonals
    moves_dict = {(-1, 0): [(-1, 0), (-1, 1), (-1, -1)],
                    (0, 1): [(0, 1), (1, 1), (-1, 1)],
                    (1, 0): [(1, 0), (1, 1), (1, -1)],
                    (0, -1): [(0, -1), (1, -1), (-1, -1)],
                    (-1, 1): [(-1, 1), (-1, 0), (0, 1)],
                    (1, 1): [(1, 1), (0, 1), (1, 0)],
                    (1, -1): [(1, -1), (1, 0), (0, -1)],
                    (-1, -1): [(-1, -1), (0, -1), (-1, 0)]}

    if initial_direction and initial_step:
        # Restrict to the initial direction for the first step
        allowed_moves = [initial_direction]
    else:
        current_direction = (
                node.coordinate[0] - node.parent.coordinate[0],
                node.coordinate[1] - node.parent.coordinate[1]
            )
        allowed_moves = moves_dict[current_direction]

    for move in allowed_moves:
        x, y = node.coordinate[0] + move[0], node.coordinate[1] + move[1]
        if [x, y] not in ob_list and [x, y] not in closed:
            neighbor.append([x, y])
    return neighbor


def find_node_index(coordinate, node_list):
    # find node index in the node list via its coordinate
    ind = 0
    for node in node_list:
        if node.coordinate == coordinate:
            target_node = node
            ind = node_list.index(target_node)
            break
    return ind


def find_path(open_list, closed_list, goal, obstacle, initial_direction=None, initial_step=False):
    # searching for the path, update open and closed list
    flag = len(open_list)
    for i in range(flag):
        node = open_list[0]
        open_coordinate_list = [node.coordinate for node in open_list]
        closed_coordinate_list = [node.coordinate for node in closed_list]
        temp = find_neighbor(node, obstacle, closed_coordinate_list, initial_direction, initial_step)
        for element in temp:
            if element in closed_list:
                continue
            elif element in open_coordinate_list:
                # if node in open list, update g value
                ind = open_coordinate_list.index(element)
                new_g = gcost(node, element)
                if new_g <= open_list[ind].G:
                    open_list[ind].G = new_g
                    open_list[ind].reset_f()
                    open_list[ind].parent = node
            else:  # new coordinate, create corresponding node
                ele_node = Node(coordinate=element, parent=node,
                                G=gcost(node, element), H=hcost(element, goal))
                open_list.append(ele_node)
        open_list.remove(node)
        closed_list.append(node)
        open_list.sort(key=lambda x: x.F)
    return open_list, closed_list


def node_to_coordinate(node_list):
    # convert node list into coordinate list and array
    coordinate_list = [node.coordinate for node in node_list]
    return coordinate_list


def find_surrounding(coordinate, obstacle):
    # find obstacles around node, help to draw the borderline
    boundary: list = []
    for x in range(coordinate[0] - 1, coordinate[0] + 2):
        for y in range(coordinate[1] - 1, coordinate[1] + 2):
            if [x, y] in obstacle:
                boundary.append([x, y])
    return boundary


def get_border_line(node_closed_ls, obstacle):
    # if no path, find border line which confine goal or robot
    border: list = []
    coordinate_closed_ls = node_to_coordinate(node_closed_ls)
    for coordinate in coordinate_closed_ls:
        temp = find_surrounding(coordinate, obstacle)
        border = border + temp
    border_ary = np.array(border)
    return border_ary


def get_path(org_list, coordinate):
    # get path from start to end
    path_org: list = []
    ind = find_node_index(coordinate, org_list)
    node = org_list[ind]
    while node != org_list[0]:
        path_org.append(node.coordinate)
        node = node.parent
    path_org.append(org_list[0].coordinate)
    path_org.reverse()
    path = np.array(path_org)
    return path

def draw(close_origin, start, end, bound):
    # plot the map
    plt.cla()
    plt.gcf().set_size_inches(8,6, forward=True)
    plt.axis('equal')
    plt.plot(close_origin[:, 0], close_origin[:, 1], 'oy')
    plt.plot(bound[:, 0], bound[:, 1], 'sk')
    plt.plot(end[0], end[1], '*b', label='Goal')
    plt.plot(start[0], start[1], '^b', label='Origin')
    plt.legend()
    plt.pause(0.0001)


def draw_control(org_closed, flag, start, end, bound, obstacle, show_animation=False):
    """
    control the plot process, evaluate if the searching finished
    flag == 0 : draw the searching process and plot path
    flag == 1 : start is blocked
    """
    stop_loop = 0  # stop sign for the searching
    org_closed_ls = node_to_coordinate(org_closed)
    org_array = np.array(org_closed_ls)
    path = None
    if show_animation:  # draw the searching process
        draw(org_array, start, end, bound)
    if flag == 0:
        if any(np.array_equal(node, end) for node in org_closed_ls):  # a path is found
            path = get_path(org_closed, end)
            stop_loop = 1
            if show_animation:  # draw the path
                print('Path found!')
                plt.plot(path[:, 0], path[:, 1], '-r')
                plt.title('Robot Arrived', size=20, loc='center')
                plt.pause(0.01)
                plt.show()
    elif flag == 1:  # start point blocked first
        stop_loop = 1
        if show_animation:
            print('There is no path to the goal! Start point is blocked!')
    if show_animation:  # blocked case, draw the border line
        info = 'There is no path to the goal!' \
               ' Robot&Goal are split by border' \
               ' shown in red \'x\'!'
        if flag == 1:
            border = get_border_line(org_closed, obstacle)
            plt.plot(border[:, 0], border[:, 1], 'xr')
            plt.title(info, size=14, loc='center')
            plt.pause(0.01)
            plt.show()
    return stop_loop, path


def searching_control(start, end, bound, obstacle, start_direction=None, show_animation=False):
    """manage the searching process, start searching from one side"""
    # initial origin node and end node
    origin = Node(coordinate=start, H=hcost(start, end))
    # list for searching from origin to goal
    origin_open: list = [origin]
    origin_close: list = []
    # initial target
    target_goal = end
    # flag = 0 (not blocked) 1 (start point blocked)
    flag = 0  # init flag
    path = None
    initial_step_start = True
    while True:
        # searching from start to end
        origin_open, origin_close = \
            find_path(origin_open, origin_close, target_goal, bound, start_direction, initial_step_start)
        initial_step_start = False  # Only apply the initial direction for the first step
        if not origin_open:  # no path condition
            flag = 1  # origin node is blocked
            draw_control(origin_close, flag, start, end, bound, obstacle, show_animation=show_animation)
            break

        # continue searching, draw the process
        stop_sign, path = draw_control(origin_close, flag, start, end, bound, obstacle, show_animation=show_animation)
        if stop_sign:
            break
    return path

def convert_polygons_to_obstacles(polygons, path_width, spacing):
    obstacles = set()
    
    for i, poly_coords in enumerate(polygons):
        raw_poly = np.array(poly_coords)/spacing
        polygon = Polygon(raw_poly)
        buffered_polygon = polygon.buffer(path_width)  # Buffer the polygon
        xmin, ymin, xmax, ymax = buffered_polygon.bounds
        for x in range(math.floor(xmin), math.ceil(xmax)+1):
            for y in range(math.floor(ymin), math.ceil(ymax)+1):
                if (x, y) not in obstacles:
                    point = Point(x, y)
                    if prep(buffered_polygon).contains(point):
                        obstacles.add((x, y))
    
    return np.array(list(obstacles)).tolist()

def main(start, end, user_polygons, path_width, spacing, start_direction=None, lower_left_bound=None, upper_right_bound=None, show_animation=False):
    # generate boundary and obstacles
    bound, obstacle = boundary_and_obstacles(start, end, lower_left_bound, upper_right_bound, user_polygons, path_width, spacing)
    
    path = searching_control(start, end, bound, obstacle, start_direction=start_direction, show_animation=show_animation)
    return path


if __name__ == '__main__':
    start = [10, 8]
    end = [103, 107]
    start_direction = (1, 0)  # Start moving right
    user_polygons = [
        [(10, 10), (15, 10), (15, 15), (10, 15)],  # Square polygon
        [(100, 100), (105, 100), (105, 105), (100, 105)]  # Another square polygon
    ]
    path_width = 4
    path = main(start, end, user_polygons, path_width, 1, start_direction=start_direction, show_animation=True)
    print(path)
