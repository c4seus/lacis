PYTHON ?= python
SYSTEM_PYTHON ?= /usr/bin/python3
SYSTEM_PATH := $(if $(VIRTUAL_ENV),$(subst $(VIRTUAL_ENV)/bin:,,$(PATH)),$(PATH))

.PHONY: install lint format types test coverage check icons desktop-metadata deb rpm

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .
	$(PYTHON) scripts/check_no_comments.py

format:
	ruff check --fix .
	ruff format .

types:
	mypy

test:
	QT_QPA_PLATFORM=offscreen pytest

coverage:
	QT_QPA_PLATFORM=offscreen pytest --cov --cov-report=term

check: lint types coverage

icons:
	QT_QPA_PLATFORM=offscreen $(PYTHON) scripts/build_icons.py

desktop-metadata:
	desktop-file-validate packaging/linux/io.github.c4seus.lacis.desktop
	appstreamcli validate --no-net --pedantic --strict packaging/linux/io.github.c4seus.lacis.metainfo.xml
	$(PYTHON) scripts/stage_desktop_files.py build/desktop-tree
	appstreamcli validate-tree --no-net --pedantic --strict build/desktop-tree

deb:
	$(SYSTEM_PYTHON) scripts/prepare_debian_source.py "$$($(SYSTEM_PYTHON) -m hatchling version)"
	env -u VIRTUAL_ENV PATH="$(SYSTEM_PATH)" \
		dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes
	mkdir -p dist
	mv ../lacis_*.deb ../lacis_*.buildinfo ../lacis_*.changes dist/
	lintian --fail-on error dist/lacis_*.deb

rpm:
	$(SYSTEM_PYTHON) scripts/prepare_rpm_spec.py "$$($(SYSTEM_PYTHON) -m hatchling version)"
	env -u VIRTUAL_ENV PATH="$(SYSTEM_PATH)" \
		rpmbuild -bb --build-in-place --define "_topdir $(CURDIR)/build/rpm" build/rpm/lacis.spec
	rpmlint build/rpm/RPMS/noarch/lacis-*.rpm build/rpm/lacis.spec
	mkdir -p dist
	cp build/rpm/RPMS/noarch/lacis-*.rpm dist/
