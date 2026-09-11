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
            +--> FUNCTION 3  find_grid_lines()      find the X/Y grid    (phase 3)
            +--> FUNCTION 4  suggest_columns()      place the columns    (phase 4)
            +--> FUNCTION 5  draw_result()          draw the picture     (phase 5)
            +--> FUNCTION 6  validate_columns()     (model goes here later)
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


# =====================================================================
#  run_pipeline()  --  THE CONDUCTOR
# ---------------------------------------------------------------------
#  Calls the numbered steps in order. Right now it does STEPS 1 and 2.
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
    print("(Finding the grid and placing columns come in the next phases.)")


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
