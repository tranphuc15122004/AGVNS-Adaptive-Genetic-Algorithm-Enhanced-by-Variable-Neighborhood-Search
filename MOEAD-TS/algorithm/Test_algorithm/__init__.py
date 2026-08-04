# Make Test_algorithm a regular package so Pylance indexes all modules.
# Note: do NOT eagerly import the moead_* modules here.  Re-exporting them
# from the package __init__ makes Pylance hit a self-referential resolution
# (resolving ``algorithm.Test_algorithm.moead_*`` re-enters this file), which
# reports the submodule as "could not be resolved".  The modules are imported
# by main.py / MOEAD_TS.py / tests directly, which keeps them indexed.
