"""
=======================================================================
 COLUMN PREDICTOR  (proof-of-concept)
=======================================================================
 Give it a floor-plan drawing (.dxf).  It finds the structural grid and
 suggests where the columns should go, using plain, explainable code.

 This file is meant to be read TOP TO BOTTOM by someone who does not
 write Python.  Every function is numbered and says who calls it and
 what it calls.  The functions run in this order:

 ---------------------------------------------------------------------
                        MAP OF THE PROGRAM
 ---------------------------------------------------------------------
   main()                      <- the program starts here (very bottom)
     |
     +--> run_pipeline(path)   <- the "conductor": calls 1..6 in order
            |
            +--> FUNCTION 1  choose_dxf_file()      pick the .dxf file   [done: phase 1]
            +--> FUNCTION 2  read_wall_lines()      read the wall lines  [done: phase 2]
            +--> FUNCTION 3  find_grid_lines()      find the X/Y grid    [done: phase 3]
            |        (uses small HELPER A and HELPER B, defined just above it)
            +--> FUNCTION 4  suggest_columns()      place the columns    [done: phase 4]
            |        (uses HELPER D to check a wall is really at that spot)
            +--> FUNCTION 5  draw_result()          draw the picture     [done: phase 5]
            +--> FUNCTION 6  validate_columns()     model seam           [done: phase 6]
                     (empty for now: the future model plugs in HERE)
 ---------------------------------------------------------------------

 A "wall line" in this program is just four numbers: (x1, y1, x2, y2) -
 the start point and the end point of one straight line.
=======================================================================
"""

# Standard-library tools that come with Python (no install needed).
import os      # to check whether a file exists and read the DISPLAY setting
import sys     # to read a file path typed after the program name

# Outside library (installed with: pip install -r requirements.txt).
import ezdxf   # reads and understands .dxf drawing files


# ---------------------------------------------------------------------
#  SETTINGS you can tweak. All are simple ratios, so they work no matter
#  whether the drawing is in millimetres, metres or feet.
# ---------------------------------------------------------------------
NEAR_AXIS_TOLERANCE = 0.02   # how straight a line must be to count as
                             #   perfectly vertical or horizontal (2% slope)
GRID_MERGE_FRACTION = 0.02   # wall lines whose position is within 2% of the
                             #   building size are treated as ONE grid line
                             #   (this merges the two faces of a wall together)
GRID_KEEP_FRACTION  = 0.15   # a grid line is kept only if the walls sitting on
                             #   it add up to at least 15% of the busiest grid
                             #   line's wall length (this drops tiny stray jogs)
COLUMN_ON_WALL_FRACTION = 0.03  # a grid crossing becomes a column only if a wall
                                #   passes within 3% of the building size of it
                                #   (so we never place a column in empty space)


# =====================================================================
#  FUNCTION 1 of 6 :  choose_dxf_file()
# ---------------------------------------------------------------------
#  WHAT IT DOES : gets the path of the .dxf file we should work on.
#                 On a normal computer it opens a small POP-UP window
#                 so the user can click and choose the file.
#                 On a server with no screen (our VM over SSH) there is
#                 no pop-up, so it falls back to the file path the user
#                 typed after the program name, or asks for one.
#  TAKES        : given_path - a path already typed on the command line
#                 (may be None if nothing was typed).
#  GIVES BACK   : the full path to a .dxf file, as text (a string).
#  CALLED BY    : run_pipeline()
#  CALLS        : the tkinter file-dialog (only if a screen is available)
# =====================================================================
def choose_dxf_file(given_path=None):

    # -- Case A: the user already told us the file on the command line.
    #            Example:  python column_predictor.py samples/sample_plan.dxf
    if given_path:
        print("Using the file given on the command line:", given_path)
        return given_path

    # -- Case B: try to open the graphical pop-up ("Open file") window.
    #            This only works when the computer has a screen. We wrap
    #            it in try/except so that, if there is no screen, the
    #            program does not crash - it just moves on to Case C.
    if os.environ.get("DISPLAY") or sys.platform.startswith("win") or sys.platform == "darwin":
        try:
            import tkinter                      # Python's built-in windows toolkit
            from tkinter import filedialog

            hidden_window = tkinter.Tk()        # create a window...
            hidden_window.withdraw()            # ...but keep it hidden; we only
                                                #    want the file-chooser dialog.
            chosen = filedialog.askopenfilename(
                title="Choose a DXF floor-plan",
                filetypes=[("DXF drawings", "*.dxf"), ("All files", "*.*")],
            )
            hidden_window.destroy()

            if chosen:                          # the user picked a file
                print("You chose:", chosen)
                return chosen
            print("No file was chosen in the pop-up.")
        except Exception as problem:
            # No screen, or tkinter is not installed. That is fine.
            print("(Pop-up not available here:", problem, ")")

    # -- Case C: no command-line file and no pop-up -> just ask by typing.
    typed = input("Type the path to a .dxf file (or press Enter to cancel): ").strip()
    if typed:
        return typed

    # Nothing worked: return None so the conductor can stop politely.
    return None


# =====================================================================
#  FUNCTION 2 of 6 :  read_wall_lines()
# ---------------------------------------------------------------------
#  WHAT IT DOES : opens the .dxf drawing and pulls out every straight
#                 wall line as four numbers (x1, y1, x2, y2).
#                 A drawing stores walls in two common shapes:
#                   * LINE        - one straight segment
#                   * LWPOLYLINE  - a chain of points (many segments)
#                 We turn both into a simple list of straight segments.
#  TAKES        : dxf_path - the path to the .dxf file.
#  GIVES BACK   : a list of segments, e.g. [(x1,y1,x2,y2), (x1,y1,x2,y2), ...]
#  CALLED BY    : run_pipeline()
#  CALLS        : ezdxf (to open and read the drawing)
# =====================================================================
def read_wall_lines(dxf_path):

    # Open the drawing. Some files are slightly broken; if the normal
    # open fails, ezdxf's "recover" mode fixes most problems for us.
    try:
        drawing = ezdxf.readfile(dxf_path)
    except Exception:
        from ezdxf import recover
        drawing, _ = recover.readfile(dxf_path)

    # "modelspace" is the main drawing area (where the plan lives).
    model_space = drawing.modelspace()

    wall_lines = []   # we will fill this list with (x1, y1, x2, y2) tuples

    # Look at every drawing object and keep the straight pieces.
    for entity in model_space:
        kind = entity.dxftype()

        if kind == "LINE":
            # One straight segment: it has a start point and an end point.
            start = entity.dxf.start
            end = entity.dxf.end
            wall_lines.append((start.x, start.y, end.x, end.y))

        elif kind == "LWPOLYLINE":
            # A chain of points. Each neighbouring pair of points is one
            # straight segment. get_points() gives (x, y, ...) for each.
            points = [(p[0], p[1]) for p in entity.get_points()]
            if entity.closed and len(points) > 1:
                points.append(points[0])   # closed shape: join last -> first
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                wall_lines.append((x1, y1, x2, y2))

        elif kind == "POLYLINE":
            # Older style of chained points; treated the same way.
            points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            if entity.is_closed and len(points) > 1:
                points.append(points[0])
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                wall_lines.append((x1, y1, x2, y2))

        # (Other drawing objects - text, arcs, hatching - are ignored
        #  on purpose. Walls in these plans are LINEs and LWPOLYLINEs.)

    return wall_lines


# ---------------------------------------------------------------------
#  HELPER A (used by FUNCTION 3) :  _describe_line()
#  Looks at one wall line and says whether it is vertical, horizontal,
#  or slanted ("other"). It also returns the line's length and the one
#  coordinate that stays constant (the X for a vertical line, the Y for
#  a horizontal line) - that constant number is where a grid line sits.
# ---------------------------------------------------------------------
def _describe_line(segment):
    x1, y1, x2, y2 = segment
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    length = (width * width + height * height) ** 0.5
    if length == 0:
        return ("other", 0.0, None)          # a dot, not a line
    if height <= NEAR_AXIS_TOLERANCE * length:
        return ("horizontal", length, (y1 + y2) / 2.0)   # sits at this Y
    if width <= NEAR_AXIS_TOLERANCE * length:
        return ("vertical", length, (x1 + x2) / 2.0)     # sits at this X
    return ("other", length, None)


# ---------------------------------------------------------------------
#  HELPER B (used by FUNCTION 3) :  _cluster_positions()
#  Takes many (position, weight) pairs that are close together and
#  merges them into a few grid lines. Positions within merge_tolerance
#  of each other become one line, placed at their weight-averaged spot.
#  ("weight" is the wall length: longer walls pull the line towards them.)
# ---------------------------------------------------------------------
def _cluster_positions(position_weight_pairs, merge_tolerance):
    if not position_weight_pairs:
        return []                                  # nothing to merge

    ordered = sorted(position_weight_pairs)        # sort by position (left->right)
    clusters = [[ordered[0]]]                      # start the first group

    for position, weight in ordered[1:]:
        last_position = clusters[-1][-1][0]
        if position - last_position <= merge_tolerance:
            clusters[-1].append((position, weight))   # close enough: same group
        else:
            clusters.append([(position, weight)])     # far away: new group

    # Turn each group into one (average_position, total_weight) result.
    merged = []
    for group in clusters:
        total_weight = sum(weight for _, weight in group)
        if total_weight > 0:
            average = sum(pos * weight for pos, weight in group) / total_weight
        else:
            average = sum(pos for pos, _ in group) / len(group)
        merged.append((average, total_weight))
    return merged


# =====================================================================
#  FUNCTION 3 of 6 :  find_grid_lines()
# ---------------------------------------------------------------------
#  WHAT IT DOES : works out the building's structural grid - the small
#                 set of vertical lines (X positions) and horizontal
#                 lines (Y positions) that the walls line up on.
#                 Idea: every vertical wall votes for an X grid line;
#                 every horizontal wall votes for a Y grid line; nearby
#                 votes are merged; weak lines are dropped.
#  TAKES        : wall_lines - the list from FUNCTION 2.
#  GIVES BACK   : two sorted lists  ->  (x_grid, y_grid)
#  CALLED BY    : run_pipeline()
#  CALLS        : HELPER A (_describe_line), HELPER B (_cluster_positions)
# =====================================================================
def find_grid_lines(wall_lines):

    # 1) How big is the drawing? We use its size to decide how close two
    #    lines must be before we treat them as the same grid line.
    all_x = [x for seg in wall_lines for x in (seg[0], seg[2])]
    all_y = [y for seg in wall_lines for y in (seg[1], seg[3])]
    width = max(all_x) - min(all_x)
    height = max(all_y) - min(all_y)
    building_size = min(width, height) or max(width, height)
    merge_tolerance = GRID_MERGE_FRACTION * building_size

    # 2) Every vertical wall votes for an X line; every horizontal wall
    #    votes for a Y line. The vote's weight is the wall's length.
    vertical_votes = []      # list of (x_position, length)
    horizontal_votes = []    # list of (y_position, length)
    for segment in wall_lines:
        orientation, length, position = _describe_line(segment)
        if orientation == "vertical":
            vertical_votes.append((position, length))
        elif orientation == "horizontal":
            horizontal_votes.append((position, length))

    # 3) Merge nearby votes into grid lines.
    x_lines = _cluster_positions(vertical_votes, merge_tolerance)
    y_lines = _cluster_positions(horizontal_votes, merge_tolerance)

    # 4) Keep only the strong grid lines (drop tiny stray ones).
    x_grid = _keep_strong_lines(x_lines)
    y_grid = _keep_strong_lines(y_lines)
    return x_grid, y_grid


# ---------------------------------------------------------------------
#  HELPER C (used by FUNCTION 3) :  _keep_strong_lines()
#  From the merged lines, keep only those carrying a fair share of wall
#  length compared with the busiest one. Returns their positions, sorted.
# ---------------------------------------------------------------------
def _keep_strong_lines(merged_lines):
    if not merged_lines:
        return []
    strongest_weight = max(weight for _, weight in merged_lines)
    kept = [position for position, weight in merged_lines
            if weight >= GRID_KEEP_FRACTION * strongest_weight]
    return sorted(kept)


# ---------------------------------------------------------------------
#  HELPER D (used by FUNCTION 4) :  is there a wall at this spot?
#  _distance_point_to_segment() measures the shortest distance from a
#  point to one wall line. _point_is_on_a_wall() says True if ANY wall
#  line passes within "tolerance" of the point.
# ---------------------------------------------------------------------
def _distance_point_to_segment(px, py, x1, y1, x2, y2):
    seg_dx = x2 - x1
    seg_dy = y2 - y1
    seg_length_squared = seg_dx * seg_dx + seg_dy * seg_dy
    if seg_length_squared == 0:
        # The "segment" is really a single point.
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    # How far along the line the nearest point is: 0 = start, 1 = end.
    t = ((px - x1) * seg_dx + (py - y1) * seg_dy) / seg_length_squared
    t = max(0.0, min(1.0, t))            # stay on the segment, not past its ends
    nearest_x = x1 + t * seg_dx
    nearest_y = y1 + t * seg_dy
    return ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5


def _point_is_on_a_wall(px, py, wall_lines, tolerance):
    for x1, y1, x2, y2 in wall_lines:
        if _distance_point_to_segment(px, py, x1, y1, x2, y2) <= tolerance:
            return True
    return False


# =====================================================================
#  FUNCTION 4 of 6 :  suggest_columns()
# ---------------------------------------------------------------------
#  WHAT IT DOES : goes to every crossing of an X grid line and a Y grid
#                 line and suggests a column there - BUT only if a wall
#                 actually passes through that crossing. This keeps
#                 columns on the structure and out of empty rooms.
#  TAKES        : x_grid, y_grid (from FUNCTION 3) and wall_lines (F2).
#  GIVES BACK   : a list of column points, e.g. [(x, y), (x, y), ...]
#  CALLED BY    : run_pipeline()
#  CALLS        : HELPER D (_point_is_on_a_wall)
# =====================================================================
def suggest_columns(x_grid, y_grid, wall_lines):
    # Work out how close a wall must be, based on the building size.
    all_x = [x for seg in wall_lines for x in (seg[0], seg[2])]
    all_y = [y for seg in wall_lines for y in (seg[1], seg[3])]
    width = max(all_x) - min(all_x)
    height = max(all_y) - min(all_y)
    building_size = min(width, height) or max(width, height)
    tolerance = COLUMN_ON_WALL_FRACTION * building_size

    columns = []
    for x in x_grid:                 # for every vertical grid line...
        for y in y_grid:             # ...and every horizontal grid line...
            if _point_is_on_a_wall(x, y, wall_lines, tolerance):
                columns.append((x, y))   # a wall is here: suggest a column
    return columns


# =====================================================================
#  FUNCTION 5 of 6 :  draw_result()
# ---------------------------------------------------------------------
#  WHAT IT DOES : draws a picture of the plan - the walls in grey, the
#                 grid as dashed blue lines, and each suggested column
#                 as a red square - then SAVES it to a .png file. If the
#                 computer has a screen it also opens a window to show it.
#  TAKES        : wall_lines, x_grid, y_grid, columns, and output_path
#                 (where to save the picture).
#  GIVES BACK   : nothing; it writes a picture file and maybe opens a window.
#  CALLED BY    : run_pipeline()
#  CALLS        : matplotlib (the drawing library)
# =====================================================================
def draw_result(wall_lines, x_grid, y_grid, columns, output_path):

    # Choose how matplotlib should work. With a screen we can SHOW a
    # window; without one (a server over SSH) we can still SAVE a file.
    import matplotlib
    has_screen = (bool(os.environ.get("DISPLAY"))
                  or sys.platform.startswith("win") or sys.platform == "darwin")
    if not has_screen:
        matplotlib.use("Agg")            # "save to a file only" mode
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(9, 9))

    # 1) the walls: plain grey lines.
    for x1, y1, x2, y2 in wall_lines:
        axes.plot([x1, x2], [y1, y2], color="0.45", linewidth=1.0)

    # 2) the grid: thin dashed blue lines spanning the whole drawing.
    all_x = [x for seg in wall_lines for x in (seg[0], seg[2])]
    all_y = [y for seg in wall_lines for y in (seg[1], seg[3])]
    for grid_x in x_grid:
        axes.plot([grid_x, grid_x], [min(all_y), max(all_y)],
                  color="#2f6db5", linewidth=0.8, linestyle="--", alpha=0.6)
    for grid_y in y_grid:
        axes.plot([min(all_x), max(all_x)], [grid_y, grid_y],
                  color="#2f6db5", linewidth=0.8, linestyle="--", alpha=0.6)

    # 3) the suggested columns: red squares on top of everything.
    if columns:
        column_x = [point[0] for point in columns]
        column_y = [point[1] for point in columns]
        axes.scatter(column_x, column_y, s=90, marker="s",
                     color="#c14545", zorder=5, label="suggested column")

    axes.set_aspect("equal")             # keep the plan's real proportions
    axes.set_title("Column Predictor  -  %d suggested columns" % len(columns))
    if columns:
        axes.legend(loc="upper right")
    figure.tight_layout()

    # SAVE the picture (this works on every computer).
    figure.savefig(output_path, dpi=130)
    print("Saved a picture of the result to:", output_path)

    # SHOW a window too, but only if the drawing backend can open one.
    # (On a server, or when no window toolkit is installed, matplotlib
    #  uses the file-only "Agg" backend, so we simply skip showing.)
    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    plt.close(figure)


# =====================================================================
#  FUNCTION 6 of 6 :  validate_columns()   --   THE MODEL SEAM
# ---------------------------------------------------------------------
#  WHAT IT DOES : this is the ONE place where the future machine-learning
#                 model will plug in. The model will look at each column
#                 the code suggested and mark it APPROVED or REJECTED.
#                 The model does not exist yet, so for now we approve
#                 every suggestion unchanged - that keeps the pipeline
#                 complete from start to finish today.
#  TAKES        : columns - the suggested list from FUNCTION 4.
#  GIVES BACK   : the approved columns (right now: all of them).
#  CALLED BY    : run_pipeline()
#  CALLS        : nothing yet (the model will be called here later)
# ---------------------------------------------------------------------
#  LATER, when the model exists, this step will run BEFORE FUNCTION 5
#  so the picture can colour approved vs rejected columns differently.
# =====================================================================
def validate_columns(columns):
    approved = []
    for (x, y) in columns:
        # LATER, replace this line with a real check, for example:
        #     if model.approves(x, y, surroundings): approved.append((x, y))
        approved.append((x, y))     # for now: keep every suggestion
    print("Model check: not built yet - approving all",
          len(approved), "suggestions for now.")
    return approved


# =====================================================================
#  run_pipeline()  --  THE CONDUCTOR
# ---------------------------------------------------------------------
#  Calls the numbered steps in order - the full STEP 1..6 pipeline.
# =====================================================================
def run_pipeline(given_path=None):
    print("Column Predictor - proof of concept")
    print("-----------------------------------")

    # STEP 1: find out which drawing we are working on.
    dxf_path = choose_dxf_file(given_path)
    if not dxf_path:
        print("No file selected - stopping. Nothing was changed.")
        return
    if not os.path.exists(dxf_path):
        print("That file does not exist:", dxf_path)
        return
    print("File:", dxf_path)

    # STEP 2: read the wall lines out of the drawing.
    wall_lines = read_wall_lines(dxf_path)
    print("Wall lines found:", len(wall_lines))
    if not wall_lines:
        print("No straight wall lines in this drawing - stopping.")
        return

    # STEP 3: work out the structural grid.
    x_grid, y_grid = find_grid_lines(wall_lines)
    print("Vertical grid lines (X positions):", len(x_grid))
    print("Horizontal grid lines (Y positions):", len(y_grid))
    print("   grid crossings (possible column spots):", len(x_grid) * len(y_grid))

    # STEP 4: keep only the crossings that actually sit on a wall.
    columns = suggest_columns(x_grid, y_grid, wall_lines)
    print("Columns suggested:", len(columns))

    # STEP 5: draw the plan with the suggested columns and save a picture.
    os.makedirs("outputs", exist_ok=True)
    file_stem = os.path.splitext(os.path.basename(dxf_path))[0]
    output_path = os.path.join("outputs", file_stem + "_columns.png")
    draw_result(wall_lines, x_grid, y_grid, columns, output_path)

    # STEP 6: the MODEL SEAM (a placeholder today).
    #   It currently approves every suggestion. When the model is built,
    #   this step will move ahead of STEP 5 so the drawing can show
    #   approved and rejected columns in different colours.
    approved_columns = validate_columns(columns)

    print("Done.  %d columns suggested, %d approved (model not built yet)."
          % (len(columns), len(approved_columns)))


# =====================================================================
#  main()  --  WHERE THE PROGRAM STARTS
# ---------------------------------------------------------------------
#  If the user typed a file path after the program name, we grab it
#  from sys.argv and hand it to the conductor. Otherwise we pass None
#  and the pop-up (or a typed prompt) will ask for the file.
# =====================================================================
def main():
    # sys.argv is the list of words typed on the command line.
    # sys.argv[0] is the program name; sys.argv[1] (if present) is the file.
    path_from_command_line = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(path_from_command_line)


if __name__ == "__main__":
    main()
