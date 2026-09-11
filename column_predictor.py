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
            +--> FUNCTION 2  read_wall_lines()      read the wall lines  (phase 2)
            +--> FUNCTION 3  find_grid_lines()      find the X/Y grid    (phase 3)
            +--> FUNCTION 4  suggest_columns()      place the columns    (phase 4)
            +--> FUNCTION 5  draw_result()          draw the picture     (phase 5)
            +--> FUNCTION 6  validate_columns()     (model goes here later)
 ---------------------------------------------------------------------
=======================================================================
"""

# Standard-library tools that come with Python (no install needed).
import os      # to check whether a file exists and read the DISPLAY setting
import sys     # to read a file path typed after the program name


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
#  run_pipeline()  --  THE CONDUCTOR
# ---------------------------------------------------------------------
#  Calls the numbered steps in order. Right now it can do STEP 1.
#  Later phases add steps 2..6 right below the last one.
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

    print("OK - the file we will analyse is:")
    print("   ", dxf_path)
    print("(Reading and analysing it comes in the next phases.)")


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
