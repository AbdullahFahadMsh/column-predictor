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
            +--> FUNCTION 1  choose_dxf_file()      pick the .dxf file
            +--> FUNCTION 2  read_wall_lines()      read the wall lines
            +--> FUNCTION 3  find_grid_lines()      find the X/Y grid
            +--> FUNCTION 4  suggest_columns()      place the columns
            +--> FUNCTION 5  draw_result()          draw the picture
            +--> FUNCTION 6  validate_columns()     (model goes here later)
 ---------------------------------------------------------------------

 Right now this is the PHASE 0 skeleton: the map above is the plan, and
 each following phase (see `git log`) fills in one function.
=======================================================================
"""


# =====================================================================
#  run_pipeline()  --  THE CONDUCTOR
# ---------------------------------------------------------------------
#  This is the one function that calls all the numbered steps in order.
#  It is still empty; each phase will plug the next step in here so you
#  can watch it grow commit by commit.
# =====================================================================
def run_pipeline(given_path=None):
    print("Column Predictor - proof of concept")
    print("-----------------------------------")
    print("The step-by-step pipeline is built over the next phases.")
    print("See README.md (the phase table) or run: git log --oneline")


# =====================================================================
#  main()  --  WHERE THE PROGRAM STARTS
# ---------------------------------------------------------------------
#  Python runs the code under this `if` when you type
#      python column_predictor.py
#  We keep it tiny on purpose: it just starts the conductor.
# =====================================================================
def main():
    run_pipeline()


if __name__ == "__main__":
    main()
