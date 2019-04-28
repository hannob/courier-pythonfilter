%define expect_egg_info %(%{__python3} -c "import distutils.command.install_egg_info" > /dev/null 2>&1 && echo 1 || echo 0)

%define courier_user    %(. /etc/profile.d/courier.sh ; courier-config | grep ^mailuser | cut -f2 -d=)
%define courier_group   %(. /etc/profile.d/courier.sh ; courier-config | grep ^mailgroup | cut -f2 -d=)
%define courier_libexec %(. /etc/profile.d/courier.sh ; courier-config | grep ^libexecdir | cut -f2 -d=)

Name:      courier-pythonfilter
Version:   3.0
Release:   1%{?dist}
Summary:   Python filtering architecture for the Courier MTA.

Group:     Development/Libraries
License:   GPL
Url:       http://www.dragonsdawn.net/~gordon/courier-pythonfilter/
Source0:   %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArchitectures: noarch

BuildRequires:  courier
Requires:       courier
BuildRequires:  python%{python3_pkgversion}-devel
Requires:       python%{python3_pkgversion}

%description
Pythonfilter provides a framework for writing message filters in
Python, as well as a selection of common filters.


%prep
%setup -q


%build
%py3_build


%install
%py3_install
mkdir -p $RPM_BUILD_ROOT%{_localstatedir}/lib/pythonfilter/quarantine

mkdir -p ${RPM_BUILD_ROOT}%{courier_libexec}/filters
ln -s %{_bindir}/pythonfilter ${RPM_BUILD_ROOT}%{courier_libexec}/filters


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root)
%dir %{python3_sitelib}/pythonfilter
%{python3_sitelib}/pythonfilter/*
%dir %{python3_sitelib}/courier
%{python3_sitelib}/courier/*
%if %{expect_egg_info}
  %{python3_sitelib}/courier_pythonfilter-*-info
%endif
%{_bindir}/*
%config(noreplace) %{_sysconfdir}/*
%attr(0700,%{courier_user},%{courier_group}) %dir %{_localstatedir}/lib/pythonfilter
%dir %{_localstatedir}/lib/pythonfilter/quarantine
%{courier_libexec}/filters/pythonfilter
