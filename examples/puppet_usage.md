This manifest is for creating a PXE booting puppet headnode. 

In order to use the manifest:

1) Run download_iso.sh to download the iso (to use for booting)

2) Check the iso with sha256sum -c sha256sum.txt

3) Share this folder with the virtual machine you want to make a PXE node

4) puppet apply --manifestdir /[path to this directory]/manifests --detailed-exitcodes /[path to this directory]/manifests/site.pp
