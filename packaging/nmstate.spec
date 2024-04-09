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
Source1:        %{url}/releases/download/v1.4.5/%{srcname}-vendor-1.4.5.tar.xz
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-%{libname} = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
BuildRequires:  systemd-rpm-macros
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
Requires:       NetworkManager-libnm >= 1:1.26.0
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
Requires:       python3-nispor
BuildArch:      noarch

%package -n nmstate-plugin-ovsdb
Summary:        nmstate plugin for OVS database manipulation
Requires:       python3-%{libname} = %{?epoch:%{epoch}:}%{version}-%{release}
%if 0%{?rhel}
# The python-openvswitch rpm package is not in the same repo with nmstate, require only
# if openvswitch is installed. If not installed, then it is recommended.
Requires:       (python3dist(ovs) if openvswitch)
Recommends:     python3dist(ovs)
%else
Requires:       python3dist(ovs)
%endif

%description -n python3-%{libname}
This package contains the Python 3 library for Nmstate.

%description -n nmstate-plugin-ovsdb
This package contains the nmstate plugin for OVS database manipulation.

%prep
%setup -q
%cargo_prep -V 1

%preun
%systemd_preun nmstate-varlink.service

%build
%py3_build

%install
%py3_install
mkdir -p %{buildroot}%{_unitdir}
install -p -m 644 %{buildroot}%{python3_sitelib}/nmstatectl/nmstate-varlink.service \
         %{buildroot}%{_unitdir}/nmstate-varlink.service
pushd rust
env SKIP_PYTHON_INSTALL=1 PREFIX=%{_prefix} LIBDIR=%{_libdir} %make_install
popd

%post
%systemd_post nmstate-varlink.service

%files
%doc README.md
%doc examples/
%{_mandir}/man8/nmstatectl.8*
%{_mandir}/man8/nmstate-autoconf.8*
%{python3_sitelib}/nmstatectl
%{_bindir}/nmstatectl
%{_bindir}/nmstatectl-rust
%{_bindir}/nmstate-autoconf

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
%exclude %{python3_sitelib}/%{libname}/plugins/nmstate_plugin_*
%exclude %{python3_sitelib}/%{libname}/plugins/__pycache__/nmstate_plugin_*
%{_unitdir}/nmstate-varlink.service

%files -n nmstate-plugin-ovsdb
%{python3_sitelib}/%{libname}/plugins/nmstate_plugin_ovsdb*
%{python3_sitelib}/%{libname}/plugins/__pycache__/nmstate_plugin_ovsdb*

%post libs
/sbin/ldconfig

%postun libs
/sbin/ldconfig

%changelog
@CHANGELOG@
- snapshot build
