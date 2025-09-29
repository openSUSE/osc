%if %{defined primary_python}
%define use_python     %(echo %{primary_python} | sed -e 's|python3|python3.|g')
%define use_python_pkg %{primary_python}
%else
%define use_python python3
%define use_python_pkg python3
%endif

%if 0%{?suse_version} && 0%{?suse_version} < 1500
# use python36 on SLE 12 and older
%define use_python python3.6
%define use_python_pkg python36
%endif

%define completion_dir_bash %{_datadir}/bash-completion/completions
%define completion_dir_csh %{_sysconfdir}/profile.d
%define completion_dir_fish %{_datadir}/fish/vendor_completions.d
%define completion_dir_zsh %{_datadir}/zsh/functions/Completion
%define osc_plugin_dir %{_prefix}/lib/osc-plugins
# need to override python_sitelib because it is not set as we would expect on many distros
%define python_sitelib %(RPM_BUILD_ROOT= %{use_python} -Ic "import sysconfig; print(sysconfig.get_path('purelib'))")

# generate manpages on distros where argparse-manpage >= 3 and python3-Sphinx are available
# please note that RHEL build requires packages from CRB and EPEL repositories
%if 0%{?suse_version} > 1500 || 0%{?fedora} >= 37 || 0%{?rhel} >= 9
%bcond_without man
%else
%bcond_with man
%endif

# whether to use fdupes to deduplicate python bytecode
%if 0%{?suse_version} || 0%{?fedora} || 0%{?rhel} >= 8 || 0%{?amzn}
%bcond_without fdupes
%else
%bcond_with fdupes
%endif

# the macro exists only on openSUSE based distros
%if %{undefined python3_fix_shebang}
%define python3_fix_shebang %nil
%endif

%define argparse_manpage_pkg argparse-manpage
%define obs_build_pkg obs-build
%define ssh_add_pkg openssh-clients
%define ssh_keygen_pkg openssh
%define sphinx_pkg %{use_python_pkg}-sphinx
%define yaml_pkg %{use_python_pkg}-ruamel-yaml

%if 0%{?suse_version}
%define argparse_manpage_pkg %{use_python_pkg}-argparse-manpage
%define obs_build_pkg build
%define ssh_keygen_pkg openssh-common
%define sphinx_pkg %{use_python_pkg}-Sphinx
%define yaml_pkg %{use_python_pkg}-ruamel.yaml
%endif

%if 0%{?suse_version} < 1600
# ruamel.yaml is not available on SLE 15, use PyYAML instead
%define use_pyyaml 1
%define yaml_pkg %{use_python_pkg}-PyYAML
%endif

Name:           osc
Version:        1.20.0
Release:        0
Summary:        Command-line client for the Open Build Service
License:        GPL-2.0-or-later
Group:          Development/Tools/Other
URL:            https://github.com/openSUSE/osc

Source:         https://github.com/openSUSE/osc/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz

%if 0%{?debian}
Source1:        debian.dirs
Source2:        debian.docs
%endif

BuildArch:      noarch
BuildRoot:      %{_tmppath}/%{name}-%{version}-build

%if %{with man}
BuildRequires:  %{argparse_manpage_pkg}
BuildRequires:  %{sphinx_pkg}
%endif
BuildRequires:  %{use_python_pkg}-cryptography
BuildRequires:  %{use_python_pkg}-devel >= 3.6
BuildRequires:  %{use_python_pkg}-rpm
BuildRequires:  %{use_python_pkg}-setuptools
BuildRequires:  %{use_python_pkg}-pip
BuildRequires:  %{use_python_pkg}-wheel
BuildRequires:  %{use_python_pkg}-urllib3
BuildRequires:  %{yaml_pkg}
BuildRequires:  diffstat
BuildRequires:  python-rpm-macros
%if %{with fdupes}
BuildRequires:  fdupes
%endif
# needed for git scm tests and directory ownership of /usr/libexec/git for git-obs symlink
BuildRequires:  git-core

Requires:       %{use_python_pkg}-cryptography
Requires:       %{use_python_pkg}-rpm
Requires:       %{use_python_pkg}-urllib3
Requires:       %{yaml_pkg}

# needed for git-obs completion
Recommends:     %{use_python_pkg}-argcomplete

# needed for showing download progressbars
Recommends:     %{use_python_pkg}-progressbar

# needed for setting the default editor by distro
Recommends:     %{use_python_pkg}-distro

# needed for storing credentials in kwallet/gnome-keyring
Recommends:     %{use_python_pkg}-keyring
Recommends:     %{use_python_pkg}-keyring-keyutils

# needed for opening control.tar.zst in debquery
Recommends:     %{use_python_pkg}-zstandard

Recommends:     %{obs_build_pkg}
# need support for --repos-directory option
Conflicts:      %{obs_build_pkg} < 20250206
Recommends:     ca-certificates
Recommends:     diffstat
Recommends:     powerpc32
Recommends:     sudo

# needed for building from git
Recommends:     git-core
Recommends:     git-lfs

# needed for osc co of a git package
Recommends:     obs-scm-bridge
Conflicts:      obs-scm-bridge < 0.7.3

# needed for `osc add <URL>`
Recommends:     obs-service-recompress
Recommends:     obs-service-download_files
Recommends:     obs-service-format_spec_file
Recommends:     obs-service-obs_scm
Recommends:     obs-service-set_version
Recommends:     obs-service-source_validator
# the older versions of obs-service-source_validator do not support .osc store 2.0
Conflicts:      obs-service-source_validator < 0.39
Recommends:     obs-service-tar_scm
Recommends:     obs-service-verify_file

# needed for ssh signature auth
Recommends:     %{ssh_add_pkg}
Recommends:     %{ssh_keygen_pkg}

# needed for `osc browse` that calls xdg-open
Recommends:     xdg-utils

Provides:       %{use_python_pkg}-osc = %{version}-%{release}
%if %{defined primary_python}
%if "%{use_python_pkg}" == "%{primary_python}"
Provides:       python3-osc = %{version}-%{release}
%endif
%endif
Provides:       git-obs = %{version}-%{release}

%description
openSUSE Commander is a command-line client for the Open Build Service.

See http://en.opensuse.org/openSUSE:OSC, as well as
http://en.opensuse.org/openSUSE:Build_Service_Tutorial
for a general introduction.

%prep
%autosetup -p1

%build

%if 0%{?use_pyyaml}
    # replace ruamel.yaml with PyYAML
    sed -i 's/ruamel\.yaml/PyYAML/g' setup.cfg
%endif

%{expand:%%%{use_python_pkg}_pyproject_wheel}

# write rpm macros
cat << EOF > macros.osc
%%osc_plugin_dir %{osc_plugin_dir}
EOF

# build man pages
%if %{with man}
PYTHONPATH=. argparse-manpage \
    --output=osc.1 \
    --format=single-commands-section \
    --module=osc.commandline \
    --function=argparse_manpage_get_parser \
    --project-name=osc \
    --prog=osc \
    --description="Command-line client for Open Build Service" \
    --author="Contributors to the osc project. See the project's GIT history for the complete list." \
    --url="https://github.com/openSUSE/osc/"

PYTHONPATH=. argparse-manpage \
    --output=git-obs.1 \
    --format=single-commands-section \
    --module=osc.commandline_git \
    --function=argparse_manpage_get_parser \
    --project-name=osc \
    --prog=git-obs \
    --description="Git based command-line client for Open Build Service" \
    --author="Contributors to the osc project. See the project's GIT history for the complete list." \
    --url="https://github.com/openSUSE/osc/"

sphinx-build -b man doc .
%endif

%install
%{expand:%%%{use_python_pkg}_pyproject_install}

# symlink /usr/bin/git-obs to /usr/libexec/git/obs
mkdir -p %{buildroot}%{_libexecdir}/git
ln -s %{_bindir}/git-obs %{buildroot}%{_libexecdir}/git/obs

# create plugin dirs
install -d %{buildroot}%{osc_plugin_dir}
install -d %{buildroot}%{_sharedstatedir}/osc-plugins

# install completions for osc
install -Dm0755 contrib/osc.complete %{buildroot}%{_datadir}/osc/complete
install -Dm0644 contrib/complete.csh %{buildroot}%{completion_dir_csh}/osc.csh
install -Dm0644 contrib/complete.sh %{buildroot}%{completion_dir_bash}/osc.bash
install -Dm0644 contrib/osc.fish %{buildroot}%{completion_dir_fish}/osc.fish
install -Dm0644 contrib/osc.zsh %{buildroot}%{completion_dir_zsh}/osc.zsh

# install completions for git-obs
install -Dm0644 contrib/git-obs-complete.bash %{buildroot}%{completion_dir_bash}/git-obs.bash
install -Dm0644 contrib/git-obs-complete.fish %{buildroot}%{completion_dir_fish}/git-obs.fish
install -Dm0644 contrib/git-obs-complete.zsh %{buildroot}%{completion_dir_zsh}/git-obs.zsh

# install rpm macros
install -Dm0644 macros.osc %{buildroot}%{_rpmmacrodir}/macros.osc

# install man page
%if %{with man}
install -Dm0644 git-obs-metadata.1 %{buildroot}%{_mandir}/man1/git-obs-metadata.1
install -Dm0644 git-obs-quickstart.1 %{buildroot}%{_mandir}/man1/git-obs-quickstart.1
install -Dm0644 osc.1 %{buildroot}%{_mandir}/man1/osc.1
install -Dm0644 git-obs.1 %{buildroot}%{_mandir}/man1/git-obs.1
install -Dm0644 oscrc.5 %{buildroot}%{_mandir}/man5/oscrc.5
%endif

%if %{with fdupes}
%fdupes %buildroot
%endif

%python3_fix_shebang

# inject argcomplete marker to the generated git-obs executable
sed -i '3i # PYTHON_ARGCOMPLETE_OK'  %{buildroot}%{_bindir}/git-obs

%check
%{use_python} -m unittest

%files
%defattr(-,root,root,-)

# docs
%license COPYING
%doc AUTHORS README.md NEWS
%if %{with man}
%{_mandir}/man*/git-obs*
%{_mandir}/man*/osc*
%endif

# executables
%{_bindir}/*
%{_libexecdir}/git/obs

# python modules
%{python_sitelib}/osc
%{python_sitelib}/osc-*-info

# rpm macros
%{_rpmmacrodir}/*

# plugins
%dir %{osc_plugin_dir}
%dir %{_sharedstatedir}/osc-plugins

# completions
%dir %{_datadir}/osc
%{_datadir}/osc/complete
%{completion_dir_bash}/*
%config %{completion_dir_csh}/*
%{completion_dir_fish}/*
%dir %{_datadir}/zsh
%dir %{_datadir}/zsh/functions
%dir %{_datadir}/zsh/functions/Completion
%{completion_dir_zsh}/*

# osc owns the dirs to avoid the "directories not owned by a package" build error
%dir %{_datadir}/fish
%dir %{_datadir}/fish/vendor_completions.d

%changelog
