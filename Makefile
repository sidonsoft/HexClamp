.PHONY: test test-verbose test-fast

test:
	python3 -m unittest discover -s tests

test-verbose:
	python3 -m unittest discover -s tests -v

test-fast:
	python3 -m unittest tests.test_message_parser tests.test_planner tests.test_bootstrap tests.test_task_completion
