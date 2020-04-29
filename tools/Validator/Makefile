################### Makefile for All Tools ##########################

#### Creation Date: February 28, 2017
MAKE=make

check:
	(python3 -m unittest validatorUnitTest)
	(./finalcheck.sh)

render_readmes_to_html:
	(jupyter-nbconvert --to html ValidatorReadMe.ipynb)
