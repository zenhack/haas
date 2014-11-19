These puppet manifests set up an ubuntu 14.04 headnode to pxe boot nodes into the CentOS 6.6
installer, with a kickstart file which will automate the install.

# Setup

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

# Use

The manifests install a script `make-links`, which expects a list of mac
addresses to be supplied on its standard input, one per line, e.g:

    01:23:45:67:89:ab
    cd:ef:01:23:45:67
    ...

Each of these should be the mac address off of which you expect a node
too boot. `make-links` will then make some symlinks, the effect of which
is that the corresponding nodes will boot into the CentOS installer on
their next boot (by default, they will chainload to the disk). You can
then use the HaaS API to force-reboot the nodes.

Upon completion of the install, the corresponding links will be deleted,
and the node will boot into the new OS for the first time. The default
root password is `r00tme`; You should change this as soon as possible.
