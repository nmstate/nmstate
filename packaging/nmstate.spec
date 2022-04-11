# Tmp workaround for Empty %files file debugsourcefiles.list problem
%global debug_package %{nil}

%?python_enable_dependency_generator
%define srcname nmstate
%define libname libnmstate

Name:           nmstate
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        Declarative network manager API
License:        LGPLv2+
URL:            https://github.com/%{srcname}/%{srcname}
Source0:        https://github.com/%{srcname}/%{srcname}/releases/download/v%{version}/%{srcname}-%{version}.tar.gz
BuildRequires:  python3-setuptools
BuildRequires:  python3-devel
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
%if 0%{?rhel}
BuildRequires:  rust-toolset
%else
BuildRequires:  rust cargo
%endif

%description
Nmstate is a library with an accompanying command line tool that manages host
networking settings in a declarative manner and aimed to satisfy enterprise
needs to manage host networking through a northbound declarative API and multi
provider support on the southbound.

%package libs
Summary:        C binding of nmstate
# Use Recommends for NetworkManager because only access to NM DBus is required,
# but NM could be running on a different host
Recommends:     NetworkManager
# Avoid automatically generated profiles
Recommends:     NetworkManager-config-server

%description libs
C binding of nmstate.

%package devel
Summary:        Development files for nmstate
Group:          Development/Libraries
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description devel
Development files of nmstate C binding.

%package -n python3-%{libname}
Summary:        nmstate Python 3 API library
# Use Recommends for NetworkManager because only access to NM DBus is required,
# but NM could be running on a different host
Recommends:     NetworkManager
# Avoid automatically generated profiles
Recommends:     NetworkManager-config-server
Recommends:     (nmstate-plugin-ovsdb if openvswitch)
# Use Suggests for NetworkManager-ovs and NetworkManager-team since it is only
# required for OVS and team support
Suggests:       NetworkManager-ovs
Suggests:       NetworkManager-team
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
BuildArch:      noarch
Provides:       nmstate-plugin-ovsdb = %{version}-%{release}
Obsoletes:      nmstate-plugin-ovsdb < 2.0-1

%description -n python3-%{libname}
This package contains the Python 3 library for Nmstate.

%prep
%setup -q

%build
pushd rust/src/python
%py3_build
popd

%install
pushd rust/src/python
%py3_install
popd
pushd rust
env SKIP_PYTHON_INSTALL=1 PREFIX=%{_prefix} LIBDIR=%{_libdir} %make_install
popd
ln -s nmstatectl-rust %{buildroot}/%{_bindir}/nmstatectl
install -D --mode 644 nmstatectl.8 \
    %{buildroot}/%{_mandir}/man8/nmstatectl.8
gzip %{buildroot}/%{_mandir}/man8/nmstatectl.8

%files
%doc README.md
%doc examples/
%{_mandir}/man8/nmstatectl.8*
%{_bindir}/nmstatectl
%{_bindir}/nmstatectl-rust

%files libs
%{_libdir}/libnmstate.so.*

%files devel
%{_libdir}/libnmstate.so
%{_includedir}/nmstate.h
%{_libdir}/pkgconfig/nmstate.pc

%files -n python3-%{libname}
%license LICENSE
%{python3_sitelib}/%{srcname}-*.egg-info/
%{python3_sitelib}/%{libname}

%post libs
/sbin/ldconfig

%postun libs
/sbin/ldconfig

%changelog
@CHANGELOG@
- snapshot build
