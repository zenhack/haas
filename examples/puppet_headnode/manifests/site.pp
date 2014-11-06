## Packages to be installed ##
package { [
    'isc-dhcp-server',
    'apache2',
    'tftpd-hpa',
    'inetutils-inetd']:
  ensure  => present,
}

## Mount the Ubuntu ISO and copy files ##
mount { "/mnt":
  device => "/vagrant/ubuntu-14.04.1-server-amd64.iso",
  fstype  => "iso9660",
  options  => "loop,ro",
  ensure  => mounted,
  atboot  => true,
}

## Files to be updated ##
file { '/etc/default/isc-dhcp-server':
  ensure  => present,
  source  => "/vagrant/manifests/static/isc-dhcp-server",
  require  => Package["isc-dhcp-server"]
}

file { '/etc/dhcp/dhcp.conf':
  ensure  => present,
  source  => "/vagrant/manifests/static/dhcp.conf",
  require  => Package["isc-dhcp-server"],
  notify  => Service["isc-dhcp-server"]
}

file { "/etc/default/tftpd-hpa":
  ensure  => present,
  require  => Package["tftpd-hpa"],
  source  => "/vagrant/manifests/static/tftpd-hpa",
}

file { "/etc/inetd.conf":
  ensure  => present,
  require  => Package["inetutils-inetd"],
  source  => "/vagrant/manifests/static/inetd.conf",
  notify  => Service["tftpd-hpa"]
}

file { "/var/lib/tftpboot/pxelinux.cfg/default":
  ensure  => present,
  source  => "/vagrant/manifests/static/pxelinux_cfg",
  require  => Package["tftpd-hpa"],
}

file { "/var/lib/tftpboot":
  ensure  => present,
  source  => "/mnt/install/netboot/",
  recurse  => true,
  require  => Mount["/mnt"]
}

file { "/var/www/ubuntu":
  ensure  => "directory",
  source  => "/mnt",
  recurse  => true,
  require  => Mount["/mnt"],
}


## Services to restart ##
service { 'isc-dhcp-server':
  ensure => running,
  enable => true,
}

service { 'tftpd-hpa':
  ensure => running,
  enable => true,
  path  => "/etc/init.d/tftpd-hpa"
}

