# Note: in data directory, non French data have been sequestered to a subdirectory nonfra

sys1dev:
	python scripts/sys1dev.py -o
sys1test:
	python scripts/sys1test.py -to

sys2dev:
	python scripts/sys2dev.py -o
sys2test:
	python scripts/sys2test.py -to

sys3dev:
	python scripts/sys3dev.py -o
sys3test:
	python scripts/sys3test.py -to


# Run this to clean up the generated files
clean:
	/bin/rm -f out/*/*
