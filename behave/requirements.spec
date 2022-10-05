# This package is not meant to be built and installed.
# It is for installing the test suite dependencies.
#
# Please follow the instructions in README.md.


# packages needed to manage virtual machines
%bcond_without host_only_packages

# minimal required behave version
%define behave_version 1.2.6


Name:           osc-behave-requirements
Version:        1
Release:        0
Summary:        Requirements for the OSC Behave tests
License:        GPLv2


# don't install kanku inside a kanku VM
%if %{with host_only_packages}
BuildRequires:  kanku
%endif

# osc
BuildRequires:  osc

# behave
BuildRequires:  (python3dist(behave) >= %{behave_version} or python3-behave >= %{behave_version})

# needed by steps/kanku.py
BuildRequires:  (python3dist(ruamel.yaml) or python3-ruamel.yaml)

# fixes: ModuleNotFoundError: No module named 'pkg_resources'
BuildRequires:  (python3dist(setuptools) or python3-setuptools)


%description
%{summary}


%files


%changelog
