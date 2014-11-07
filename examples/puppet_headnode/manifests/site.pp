## Packages to be installed ##
package { [
    'isc-dhcp-server',
    'apache2',
    'tftpd-hpa',
    'inetutils-inetd',
    'python-flask',]:
  ensure  => present,
}

## Mount the Ubuntu ISO and copy files ##
mount { "/mnt/iso":
  device => "/root/CentOS-6.6-x86_64-minimal.iso",
  fstype  => "iso9660",
  options  => "loop,ro",
  ensure  => mounted,
  atboot  => true,
}

## Files to be updated ##

# set interface configuration
file { '/etc/networking/interfaces':
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/interfaces",
}

file { '/etc/default/isc-dhcp-server':
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/isc-dhcp-server",
  require  => Package["isc-dhcp-server"]
}

# dhcp configuration
file { '/etc/dhcp/dhcp.conf':
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/dhcp.conf",
  require  => Package["isc-dhcp-server"],
  notify  => Service["isc-dhcp-server"]
}

# tftp configuration
file { "/etc/default/tftpd-hpa":
  ensure  => present,
  require  => Package["tftpd-hpa"],
  source  => "/root/haas/examples/puppet_headnode/manifests/static/tftpd-hpa",
}

file { "/etc/inetd.conf":
  ensure  => present,
  require  => Package["inetutils-inetd"],
  source  => "/root/haas/examples/puppet_headnode/manifests/static/inetd.conf",
  notify  => Service["tftpd-hpa"]
}

# pxe configuration
file { "/var/lib/tftpboot/pxelinux.cfg/default":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/default",
  require  => Package["tftpd-hpa"],
}

file { "/var/lib/tftpboot/centos/pxelinux.cfg":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/centos_pxelinux_cfg",
  require  => Package["tftpd-hpa"],
}

file { "/var/lib/tftpboot/centos/vmlinuz":
  ensure  => present,
  source  => "/mnt/iso/isolinux/vmlinuz",
  require  => Mount["/mnt/iso"]
}

file { "/var/lib/tftpboot/centos/initrd.img":
  ensure  => present,
  source  => "/mnt/iso/isolinux/initrd.img",
  require  => Mount["/mnt/iso"]
}

file { "/var/lib/tftpboot/centos/ks.cfg":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/ks.cfg",
}

file { "/usr/local/bin/make_links":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/manifests/static/make_links",

file { "/usr/local/bin/boot_notify.py":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/boot_notify.py",
  mode  => 755,
}

file { "/etc/rc.local":
  ensure  => present,
  source  => "/root/haas/examples/puppet_headnode/rc.local",
  mode  => 755,
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

