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
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-%{libname} = %{?epoch:%{epoch}:}%{version}-%{release}
BuildRequires:  systemd-rpm-macros

%description
Nmstate is a library with an accompanying command line tool that manages host
networking settings in a declarative manner and aimed to satisfy enterprise
needs to manage host networking through a northbound declarative API and multi
provider support on the southbound.


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

%build
%py3_build

%install
%py3_install

%files
%doc README.md
%doc examples/
%{_mandir}/man8/nmstatectl.8*
%{_mandir}/man8/nmstate-autoconf.8*
%{python3_sitelib}/nmstatectl
%{_bindir}/nmstatectl
%{_bindir}/nmstate-autoconf

%files -n python3-%{libname}
%license LICENSE
%{python3_sitelib}/%{srcname}-*.egg-info/
%{python3_sitelib}/%{libname}
%exclude %{python3_sitelib}/%{libname}/plugins/nmstate_plugin_*
%exclude %{python3_sitelib}/%{libname}/plugins/__pycache__/nmstate_plugin_*

%files -n nmstate-plugin-ovsdb
%{python3_sitelib}/%{libname}/plugins/nmstate_plugin_ovsdb*
%{python3_sitelib}/%{libname}/plugins/__pycache__/nmstate_plugin_ovsdb*

%changelog
@CHANGELOG@
- snapshot build
