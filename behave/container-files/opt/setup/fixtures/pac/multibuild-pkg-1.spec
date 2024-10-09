%if %undefined flavor
%define flavor @BUILD_FLAVOR@%{nil}
%endif

# create own debug packages, because the auto-generated would get removed due to being empty
%undefine _debuginfo_subpackages


Name:           multibuild-pkg
Version:        1
Release:        1
License:        GPL-2.0
Summary:        Test package
URL:            https://example.com/test-package/


%description
desc


%prep


%build


%install




# no flavor
%if "%{flavor}" == "%{nil}"
%files


%package debuginfo
Summary:        Test debuginfo package

%description debuginfo
desc

%files debuginfo
%ghost /usr/lib/debug/multibuild-pkg.debug


%package debugsource
Summary:        Test debugsource package

%description debugsource
desc

%files debugsource
%ghost %{_prefix}/src/debug/%{name}-%{version}-%{release}.%{arch}/main.c
%endif


# flavor1
%if "%{flavor}" == "flavor1"
%package -n %{name}-%{flavor}
Summary:        Multibuild test package, flavor1

%description -n %{name}-%{flavor}
desc

%files -n %{name}-%{flavor}

%package -n %{name}-%{flavor}-debuginfo
Summary:        Test debuginfo package

%description -n %{name}-%{flavor}-debuginfo
desc

%files -n %{name}-%{flavor}-debuginfo
%ghost %{_prefix}/lib/debug/multibuild-pkg.debug
%endif


# flavor2
%if "%{flavor}" == "flavor2"
%package -n %{name}-%{flavor}
Summary:        Multibuild test package, flavor2

%description -n %{name}-%{flavor}
desc

%files -n %{name}-%{flavor}

%package -n %{name}-%{flavor}-debuginfo
Summary:        Test debuginfo package

%description -n %{name}-%{flavor}-debuginfo
desc

%files -n %{name}-%{flavor}-debuginfo
%ghost %{_prefix}/lib/debug/multibuild-pkg.debug
%endif


%changelog
