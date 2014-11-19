These puppet manifests set up an ubuntu 14.04 headnode to pxe boot nodes into the CentOS 6.6
installer, with a kickstart file which will automate the install.

To use these manifests:

1. Create a headnode. The headnode must have a nic that will be recognized as eth1, which
   must be on a HaaS network that the nodes will pxe boot off of.
2. Download the CentOS 6.6 minimal ISO, verify the checksum, and then
   copy it to root's home directory:

    ./download_iso.sh
    sha256sum -c sha256sums.txt
    cp *.iso /root

3. Install puppet:

    apt-get install puppet

4. Git clone the haas to /root, cd into the examples/puppet_headnode/, and apply the manifests:

    cd /root
    git clone https://github.com/CCI-MOC/haas.git
    cd /haas/examples/puppet_headnode/manifests
    puppet apply site.pp

   Note that the haas repo *must* be located under /root; the puppet
   manifests hard-code paths to certain files.

5. Reboot the headnode.
