These puppet manifests set up an ubuntu 14.04 headnode to pxe boot nodes into the CentOS 6.6
installer, with a kickstart file which will automate the install.

To use these manifests:

1. Create a headnode. The headnode must have a nic that will be recognized as eth1, which
   must be on a HaaS network that the nodes will pxe boot off of.
2. Download the CentOS 6.6 minimal ISO into root's home directory:

     cd /root
     wget http://mirror.hmc.edu/centos/6.6/isos/x86_64/CentOS-6.6-x86_64-minimal.iso

3. Install puppet:

     apt-get install puppet

4. Git clone the haas to /root, cd into the examples/puppet_headnode/, and apply the manifests:

    cd /root
    git clone https://github.com/CCI-MOC/haas.git
    cd /haas/examples/puppet_headnode/manifests
    puppet apply site.pp

This is done in this location because of the static full path name must be inside the puppet manifest

5. Reboot machine to make sure the initrd is working 
