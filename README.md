# Column Predictor (POC)

A **small, readable proof-of-concept**. You give it a floor-plan drawing (a
`.dxf` file), and it:

1. reads the drawing,
2. finds the **structural grid** (the lines the building is set out on),
3. **suggests where the columns go** — using plain, explainable code (no AI yet).

> A machine-learning model that *approves or rejects* each suggested column
> will be added later. For now, every column is a **code-based suggestion**.

This is the deliberately-simple sibling of the larger project (now called
**PCLv2**), which we have put on hold. The goal here is a codebase a
**non-Python developer can read top to bottom** and understand.

---

## How the program is built (read the commits!)

The whole point of this repo is that it was built **one phase at a time**, and
each phase is **one git commit**. Run `git log --oneline` and read from the
bottom up — you will watch the program grow function by function:

| Phase | Commit adds | Function |
|------:|-------------|----------|
| 0 | Project skeleton + this map | *(setup)* |
| 1 | Pick a `.dxf` file from a pop-up window | `FUNCTION 1` |
| 2 | Read the drawing and pull out the wall lines | `FUNCTION 2` |
| 3 | Find the structural grid (X and Y grid lines) | `FUNCTION 3` |
| 4 | Suggest columns where grid lines cross on a wall | `FUNCTION 4` |
| 5 | Draw the plan + the suggested columns to a picture | `FUNCTION 5` |
| 6 | Tidy the "conductor", add the (empty) model seam | `FUNCTION 6` |

Everything lives in **one file**, [`column_predictor.py`](column_predictor.py),
so you can read it straight through. Open it and look at the
**"MAP OF THE PROGRAM"** comment at the very top — it lists every function in
the order they run and says which function calls which.

---

## How to run it

```bash
# 1) make an isolated Python environment (once)
python3 -m venv .venv
source .venv/bin/activate

# 2) install the two libraries it needs (once)
pip install -r requirements.txt

# 3) run it
python column_predictor.py
```

**On a computer with a screen**, step 3 opens a small pop-up so you can pick a
`.dxf` file. A sample drawing is included in [`samples/`](samples/).

**On a server with no screen** (like our VM over SSH), there is no pop-up, so
just pass the file on the command line instead:

```bash
python column_predictor.py samples/sample_plan.dxf
```

Either way it prints what it found and saves a picture of the result into
`outputs/`.

---

## What it needs

* Python 3.8+
* [`ezdxf`](https://ezdxf.mozman.at/) — reads `.dxf` drawings
* [`matplotlib`](https://matplotlib.org/) — draws the result picture

(see [`requirements.txt`](requirements.txt))
