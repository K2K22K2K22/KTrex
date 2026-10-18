Name:           python-ktrex
Version:        0.3.0
Release:        1%{?dist}
Summary:        Interactive terminal-based directory structure builder

License:        MIT
URL:            https://github.com/K2K22K2K22/KTrex
# Tests' conftest.py is missing from the PyPI sdist, so we use the GitHub tag tarball
Source0:        %{url}/archive/v%{version}/KTrex-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-pytest

%global _description %{expand:
KTrex is an interactive terminal-based tool for building directory structures
from a text-based tree representation, with live preview, presets, and undo
support.}

%description %_description

%package -n ktrex
Summary:        %{summary}

%description -n ktrex %_description

%prep
%autosetup -n KTrex-%{version} -p1

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
# v0.3.0 tarball ships these files with an accidental exec bit
chmod 644 README.md %{buildroot}%{python3_sitelib}/ktrex/presets/ml_project.json
%pyproject_save_files -l ktrex
# shortcut: PyPI ships a duplicate capital-K entry point; Fedora requires lowercase names
rm %{buildroot}%{_bindir}/KTrex

%check
%pytest

%files -n ktrex -f %{pyproject_files}
%doc README.md
%{_bindir}/ktrex

%changelog
* Sun Oct 18 2026 AK <ak@fedoraproject.org> - 0.3.0-1
- Initial package
