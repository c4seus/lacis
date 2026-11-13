PYTHON ?= python
SYSTEM_PYTHON ?= /usr/bin/python3
SYSTEM_PATH := $(if $(VIRTUAL_ENV),$(subst $(VIRTUAL_ENV)/bin:,,$(PATH)),$(PATH))

.PHONY: install lint format types test coverage check icons desktop-metadata deb rpm arch windows

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
	@test -n "$$(rpm --eval '%{?python3_sitelib}')" || { \
		echo "make rpm needs the Fedora RPM macros of python3-devel: run it on Fedora," \
			"or in a Fedora container"; \
		exit 1; \
	}
	$(SYSTEM_PYTHON) scripts/prepare_rpm_spec.py "$$($(SYSTEM_PYTHON) -m hatchling version)"
	env -u VIRTUAL_ENV PATH="$(SYSTEM_PATH)" \
		rpmbuild -bb --build-in-place --define "_topdir $(CURDIR)/build/rpm" build/rpm/lacis.spec
	rpmlint build/rpm/RPMS/noarch/lacis-*.rpm build/rpm/lacis.spec
	mkdir -p dist
	cp build/rpm/RPMS/noarch/lacis-*.rpm dist/

arch:
	@test -f /etc/arch-release || { \
		echo "make arch needs makepkg and namcap: run it on Arch Linux, or in an Arch Linux" \
			"container"; \
		exit 1; \
	}
	$(SYSTEM_PYTHON) scripts/prepare_arch_package.py "$$($(SYSTEM_PYTHON) -m hatchling version)"
	cd build/arch && env -u VIRTUAL_ENV PATH="$(SYSTEM_PATH)" makepkg --cleanbuild --force
	namcap build/arch/PKGBUILD build/arch/lacis-*.pkg.tar.zst > build/arch/namcap.txt
	cat build/arch/namcap.txt
	! grep -q " E: " build/arch/namcap.txt
	mkdir -p dist
	cp build/arch/lacis-*.pkg.tar.zst dist/

windows:
	@test "$(OS)" = Windows_NT || { \
		echo "make windows needs Nuitka, Visual Studio and Inno Setup 7: run it on Windows," \
			"from Git Bash"; \
		exit 1; \
	}
	$(PYTHON) scripts/build_windows_installer.py \
		"$$($(PYTHON) -c 'import lacis; print(lacis.__version__, end="")')"
