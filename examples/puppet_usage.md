This manifest is for creating a PXE booting puppet headnode. 

In order to use the manifest:

1) Run download_iso.sh to download the iso (to use for booting)

2) Check the iso with sha256sum -c sha256sum.txt

3) Share this folder with the virtual machine you want to make a PXE node

    i) add to xml:

        <filesystem type='mount' accessmode='mapped'>
            <source dir='/tmp/shared'/>
            <target dir='tag'/>
        </filesystem>

    ii) mount -t 9p -o trans=virtio,version=9p2000.L tag /mnt/[path to this directory]/

4) puppet apply --manifestdir /mnt/[path to this directory]/manifests --detailed-exitcodes /mnt/[path to this directory]/manifests/site.pp
