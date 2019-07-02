%define srcname nmstate
%define libname libnmstate

Name:           nmstate
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        Declarative network manager API
License:        LGPLv2.1+
URL:            https://github.com/%{srcname}/%{srcname}
Source0:        https://github.com/%{srcname}/%{srcname}/archive/v%{version}/%{srcname}-%{version}.tar
BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
Requires:       python2-setuptools
Requires:       python2-%{libname} = %{?epoch:%{epoch}:}%{version}-%{release}

%description
Nmstate is a library with an accompanying command line tool that manages host
networking settings in a declarative manner and aimed to satisfy enterprise
needs to manage host networking through a northbound declarative API and multi
provider support on the southbound.


%package -n python2-%{libname}
Summary:        nmstate Python 2 API library
Requires:       NetworkManager-libnm >= 1:1.12
Requires:       python-gobject-base
Requires:       python2-six
Requires:       python-jsonschema
Requires:       python2-pyyaml
Requires:       dbus-python

%description -n python2-%{libname}
This package contains the Python 2 library for Nmstate.

%prep
%setup -q
sed -i -e '/^dbus-python$/d' requirements.txt

%build
%py2_build

%install
%py2_install

%files
%doc README.md
%doc examples/
%{python2_sitelib}/nmstatectl
%{_bindir}/nmstatectl

%files -n python2-%{libname}
%license LICENSE
%{python2_sitelib}/%{libname}
%{python2_sitelib}/%{srcname}-*.egg-info/

%changelog
@CHANGELOG@
- snapshot build
